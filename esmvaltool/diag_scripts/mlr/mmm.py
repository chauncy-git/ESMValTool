#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Use simple multi-model mean for predictions.

Description
-----------
This diagnostic calculates the (unweighted) mean over all given datasets for a
given target variable.

Author
------
Manuel Schlund (DLR, Germany)

Project
-------
CRESCENDO

Configuration options in recipe
-------------------------------
collapse_over : str, optional (default: 'dataset')
    Dataset attribute to collapse over.
convert_units_to : str, optional
    Convert units of the input data. Can also be given as dataset option.
ignore : list of dict, optional
    Ignore specific datasets by specifying multiple :obj:`dict`s of metadata.
mlr_model_name : str, optional
    Human-readable name of the MLR model instance (e.g used for labels).
pattern : str, optional
    Pattern matched against ancestor file names.
prediction_name : str, optional
    Default ``prediction_name`` of output cubes if no 'prediction_reference'
    dataset is given.

"""

import logging
import os
from pprint import pformat

import iris
import numpy as np
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import LeaveOneOut

import esmvaltool.diag_scripts.shared.iris_helpers as ih
from esmvaltool.diag_scripts import mlr
from esmvaltool.diag_scripts.shared import (get_diagnostic_filename,
                                            group_metadata, io, run_diagnostic,
                                            select_metadata)

logger = logging.getLogger(os.path.basename(__file__))


def _add_dataset_attributes(cube, datasets, cfg):
    """Add dataset-related attributes to cube."""
    dataset_names = list({d['dataset'] for d in datasets})
    projects = list({d['project'] for d in datasets})
    start_years = list({d['start_year'] for d in datasets})
    end_years = list({d['end_year'] for d in datasets})
    cube.attributes['dataset'] = '|'.join(dataset_names)
    cube.attributes['description'] = 'MMM prediction'
    cube.attributes['end_year'] = min(end_years)
    cube.attributes['mlr_model_name'] = cfg.get('mlr_model_name', 'MMM')
    cube.attributes['mlr_model_type'] = 'mmm'
    cube.attributes['project'] = '|'.join(projects)
    cube.attributes['start_year'] = min(start_years)
    cube.attributes['var_type'] = 'prediction_output'


def add_general_attributes(cube, **kwargs):
    """Add general attributes to cube."""
    for (key, val) in kwargs.items():
        if val is not None:
            cube.attributes[key] = val


def convert_units(cfg, cube, data):
    """Convert units if desired."""
    cfg_settings = cfg.get('convert_units_to')
    data_settings = data.get('convert_units_to')
    if cfg_settings or data_settings:
        units_to = cfg_settings
        if data_settings:
            units_to = data_settings
        logger.info("Converting units from '%s' to '%s'", cube.units, units_to)
        cube.convert_units(units_to)


def get_error_cube(cfg, datasets):
    """Estimate prediction error using cross-validation."""
    loo = LeaveOneOut()
    datasets = select_metadata(datasets, var_type='label')
    datasets = np.array(datasets)
    errors = []
    for (train_idx, test_idx) in loo.split(datasets):
        ref_cube = get_mm_cube(cfg, datasets[test_idx])
        mm_cube = get_mm_cube(cfg, datasets[train_idx])

        # Apply mask
        mask = np.ma.getmaskarray(ref_cube.data).ravel()
        mask |= np.ma.getmaskarray(mm_cube.data).ravel()

        y_true = ref_cube.data.ravel()[~mask]
        y_pred = mm_cube.data.ravel()[~mask]
        weights = mlr.get_all_weights(ref_cube).ravel()[~mask]

        # Calculate mean squared error
        error = mean_squared_error(y_true, y_pred, sample_weight=weights)
        errors.append(error)

    # Get error cube
    error_cube = get_mm_cube(cfg, datasets)
    error_array = np.empty(error_cube.shape).ravel()
    mask = np.ma.getmaskarray(error_cube.data).ravel()
    error_array[mask] = np.nan
    error_array[~mask] = np.mean(errors)
    error_array = np.ma.masked_invalid(error_array)
    error_cube.data = error_array.reshape(error_cube.shape)

    # Cube metadata
    error_cube.attributes['squared'] = 1
    error_cube.attributes['var_type'] = 'prediction_output_error'
    error_cube.var_name += '_squared_mmm_error_estim'
    error_cube.long_name += ' (squared MMM error estimation using CV)'
    error_cube.units = mlr.units_power(error_cube.units, 2)
    return error_cube


def get_grouped_data(cfg, input_data=None):
    """Get input files."""
    if input_data is None:
        logger.debug("Loading input data from 'cfg' argument")
        input_data = mlr.get_input_data(cfg,
                                        pattern=cfg.get('pattern'),
                                        ignore=cfg.get('ignore'))
    else:
        logger.debug("Loading input data from 'input_data' argument")
        if not mlr.datasets_have_mlr_attributes(input_data, log_level='error'):
            raise ValueError("At least one input dataset does not have valid "
                             "MLR attributes")
    if not input_data:
        raise ValueError("No input data found")
    paths = [d['filename'] for d in input_data]
    logger.debug("Found files")
    logger.debug(pformat(paths))

    # Extract necessary data
    label_data = select_metadata(input_data, var_type='label')
    prediction_reference_data = select_metadata(
        input_data, var_type='prediction_reference')
    extracted_data = label_data + prediction_reference_data
    logger.debug("Found 'label' data")
    logger.debug(pformat([d['filename'] for d in label_data]))
    logger.debug("Found 'prediction_reference' data")
    logger.debug(pformat([d['filename'] for d in prediction_reference_data]))

    # Return grouped data
    return group_metadata(extracted_data, 'tag')


def get_mm_cube(cfg, datasets):
    """Extract data."""
    cubes = iris.cube.CubeList()
    cube_labels = []
    for dataset in select_metadata(datasets, var_type='label'):
        path = dataset['filename']
        cube_label = dataset[cfg.get('collapse_over', 'dataset')]
        cube = iris.load_cube(path)
        convert_units(cfg, cube, dataset)
        ih.preprocess_cube_before_merging(cube, cube_label)
        cubes.append(cube)
        cube_labels.append(cube_label)
    mm_cube = cubes.merge_cube()
    if len(cube_labels) > 1:
        mm_cube = mm_cube.collapsed(['cube_label'], iris.analysis.MEAN)
    _add_dataset_attributes(mm_cube, datasets, cfg)
    return mm_cube


def get_reference_dataset(datasets, tag):
    """Get ``prediction_reference`` dataset."""
    ref_datasets = select_metadata(datasets, var_type='prediction_reference')
    if not ref_datasets:
        logger.warning(
            "Calculating residuals for '%s' not possible, no "
            "'prediction_reference' dataset given", tag)
        return (None, None)
    if len(ref_datasets) > 1:
        filenames = [d['filename'] for d in ref_datasets]
        raise ValueError(
            f"Expected at most one 'prediction_reference' dataset for "
            f"'{tag}', got {len(ref_datasets):d}:\n{pformat(filenames)}")
    return (ref_datasets[0], ref_datasets[0].get('prediction_name'))


def get_residual_cube(mm_cube, ref_cube):
    """Calculate residuals."""
    if mm_cube.shape != ref_cube.shape:
        raise ValueError(
            f"Expected identical shapes for 'label' and "
            f"'prediction_reference' datasets, got {mm_cube.shape} and "
            f"{ref_cube.shape}, respectively")
    res_cube = mm_cube.copy()
    res_cube.data -= ref_cube.data
    res_cube.attributes['residuals'] = 'true minus predicted values'
    res_cube.attributes['var_type'] = 'prediction_residual'
    res_cube.var_name += '_residual'
    res_cube.long_name += ' (residual)'
    return res_cube


def main(cfg, input_data=None, description=None):
    """Run the diagnostic."""
    grouped_data = get_grouped_data(cfg, input_data=input_data)
    description = '' if description is None else f'_for_{description}'
    if not grouped_data:
        logger.error("No input data found")
        return

    # Loop over all tags
    for (tag, datasets) in grouped_data.items():
        logger.info("Processing label '%s'", tag)

        # Get reference dataset if possible
        (ref_dataset, pred_name) = get_reference_dataset(datasets, tag)
        if pred_name is None:
            pred_name = cfg.get('prediction_name')

        # Calculate multi-model mean
        logger.info("Calculating multi-model mean")
        mm_cube = get_mm_cube(cfg, datasets)
        add_general_attributes(mm_cube, tag=tag, prediction_name=pred_name)
        mm_path = get_diagnostic_filename(f"mmm_{tag}_prediction{description}",
                                          cfg)
        io.iris_save(mm_cube, mm_path)

        # Estimate prediction error using cross-validation
        if len(datasets) < 2:
            logger.warning(
                "Estimating prediction error using cross-validation not "
                "possible, at least 2 datasets are needed, only %i is given",
                len(datasets))
        else:
            logger.info("Estimating prediction error using cross-validation")
            err_cube = get_error_cube(cfg, datasets)
            add_general_attributes(err_cube,
                                   tag=tag,
                                   prediction_name=pred_name)
            err_path = mm_path.replace('_prediction',
                                       '_squared_prediction_error')
            io.iris_save(err_cube, err_path)

        # Calculate residuals
        if ref_dataset is None:
            continue
        logger.info("Calculating residuals")
        ref_cube = iris.load_cube(ref_dataset['filename'])
        res_cube = get_residual_cube(mm_cube, ref_cube)
        add_general_attributes(res_cube, tag=tag, prediction_name=pred_name)
        res_path = mm_path.replace('_prediction', '_prediction_residual')
        io.iris_save(res_cube, res_path)


# Run main function when this script is called
if __name__ == '__main__':
    with run_diagnostic() as config:
        main(config)