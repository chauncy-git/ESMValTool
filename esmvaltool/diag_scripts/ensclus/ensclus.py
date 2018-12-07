"""Ensemble Clustering Diagnostics.

Author: Irene Mavilia (ISAC-CNR, Italy)
Copernicus C3S 34a lot 2 (MAGIC)

Description
    Cluster analysis tool based on the k-means algorithm
    for ensembles of climate model simulations
Modification history
    20181202-hard_jo: cleanup, style and finalising
    20181002-arno_en: updating to version2_develpment (recipe/dataset)
    20170710-mavi_ir: Routines written.
"""

import os
import logging
from esmvaltool.diag_scripts.shared import group_metadata, run_diagnostic

# Import user diagnostic routines
from ens_anom import ens_anom
from ens_eof_kmeans import ens_eof_kmeans
from ens_plots import ens_plots

logger = logging.getLogger(os.path.basename(__file__))


def main(cfg):
    """Ensemble Clustering Diagnostics."""
    out_dir = cfg['work_dir']
    write_plots = cfg['write_plots']

#    input_files = get_input_files(cfg)
#    os.makedirs(cfg['plot_dir'], exist_ok=True)
#    os.makedirs(cfg['work_dir'], exist_ok=True)

    my_files_dict = group_metadata(cfg['input_data'].values(), 'dataset')
    numens = len(my_files_dict)
    print("numens ", numens)
    # Building the name of output files
    element = list(my_files_dict.values())[0][0]
    print(element)
    name_outputs = (element['short_name'] + '_' + str(numens) +
                    'ens_' + cfg['season'] + '_' + cfg['area'] +
                    '_' + element['project'] + '_' + element['exp'])
    logger.info('The name of the output files will be <variable>_%s.txt',
                name_outputs)
    variable_name = element['short_name']

    filenames_cat = []
    for key, value in my_files_dict.items():
        logger.info("Processing file %s", value[0]['filename'])
        filenames_cat.append(value[0]['filename'])

    # ###################### PRECOMPUTATION #######################
    # ____________run ens_anom as a module
    ens_anom(filenames_cat, out_dir, name_outputs, variable_name,
             numens, cfg['season'], cfg['area'], cfg['extreme'])

    # ###################### EOF AND K-MEANS ANALYSES #######################
    # ____________run ens_eof_kmeans as a module
    ens_eof_kmeans(out_dir, name_outputs, numens, cfg['numpcs'],
                   cfg['perc'], cfg['numclus'])

    # ###################### PLOT AND SAVE FIGURES ##########################
    # ____________run ens_plots as a module
    if write_plots:
        ens_plots(out_dir, cfg['plot_dir'], name_outputs, cfg['numclus'],
                  'anomalies', cfg['output_file_type'])

    logger.info('\n>>>>>>>>>>>> ENDED SUCCESSFULLY!! <<<<<<<<<<<<\n')


if __name__ == '__main__':
    with run_diagnostic() as config:
        main(config)
