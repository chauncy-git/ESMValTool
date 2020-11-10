# ESA CCI LST Diagnostic


import os

# to manipulate iris cubes
import iris
import cartopy.crs as ccrs
import matplotlib.pyplot as plt
from matplotlib.ticker import (MultipleLocator, FormatStrFormatter,
                               AutoMinorLocator)

import numpy as np

import logging

# import internal esmvaltool modules here
from esmvaltool.diag_scripts.shared import group_metadata, run_diagnostic
from esmvalcore.preprocessor import area_statistics
#from esmvaltool.diag_scripts.shared.plot import quickplot#, save_figure

logger = logging.getLogger(__name__) # from OC example, dont know what this does!

def get_input_cubes(metadata):
    # This is from 
    # https://github.com/ESMValGroup/ESMValTool/blob/master/esmvaltool/diag_scripts/hydrology/lisflood.py
    """Create a dict with all (preprocessed) input files."""
    inputs = {}
    ancestors = {}
    for attributes in metadata:
        short_name = attributes['short_name']
        #if short_name in inputs:
        #    raise ValueError(f"Multiple input files found for variable "
        #                     f"'{short_name}'.")
        filename = attributes['filename']
        logger.info("Loading variable %s", short_name)
        cube = iris.load_cube(filename)
        cube.attributes.clear()
        inputs[short_name] = cube
        ancestors[short_name] = [filename]

    return inputs, ancestors

def make_plots(lst_diff_data,lst_diff_data_low,lst_diff_data_high, config):
    # Make a timeseries plot of the difference OBS-MODEL

    fig,ax = plt.subplots(figsize=(15,15))


    ax.plot(lst_diff_data.data, color='black', linewidth=4)
    ax.plot(lst_diff_data_low.data,'--', color='blue', linewidth=3)
    ax.plot(lst_diff_data_high.data,'--', color='blue', linewidth=3)
    ax.fill_between(range(len(lst_diff_data.data)), lst_diff_data_low.data,lst_diff_data_high.data,
                    color='blue',alpha=0.25)

    # make X ticks
    x_tick_list = []
    time_list = lst_diff_data.coord('time').units.num2date(lst_diff_data.coord('time').points)
    for item in time_list:
        if item.month == 1:
            x_tick_list.append(item.strftime('%Y %b'))
        elif item.month == 7:
            x_tick_list.append(item.strftime('%b'))
        else:
            x_tick_list.append('')

    ax.set_xticks(range(len(lst_diff_data.data)))
    ax.set_xticklabels(x_tick_list, fontsize=18, rotation = 45)


    # make Y ticks
    Y_lower = np.floor(lst_diff_data_low.data.min())
    Y_upper = np.ceil(lst_diff_data_high.data.max())

#    ax.yaxis.set_major_locator(MultipleLocator(2))
#    ax.xaxis.set_major_formatter(FormatStrFormatter('%d'))

    # For the minor ticks, use no labels; default NullFormatter.
#    ax.yaxis.set_minor_locator(MultipleLocator(0.5))

    ax.set_yticks(np.arange(Y_lower,Y_upper+0.1,2))
    ax.set_yticklabels(np.arange(Y_lower,Y_upper+0.1,0.5), fontsize=18)

    
    ax.set_ylim((Y_lower-0.1,Y_upper+0.1))

    ax.set_xlabel('Date', fontsize = 20)
    ax.set_ylabel('Difference / K', fontsize = 20)

    ax.grid()

    lons = lst_diff_data.coord('longitude').bounds
    lats = lst_diff_data.coord('latitude').bounds

    ax.set_title('Area: lon %s lat %s' % (lons[0], lats[0]), fontsize=22)

    fig.suptitle('ESACCI LST - CMIP6 Historical Ensemble Mean', fontsize=24)

    plt.savefig('%s/timeseries.png' % config['plot_dir'])

    plt.close('all')

    # fig = plt.figure()
    # ax = plt.axes(projection=ccrs.PlateCarree())
    # ax.stock_img()

    


    return None

def diagnostic(config):
    

    logger.info("Robs text 1") # marker to see where this work appears in the log

    # this function is from the hydrology py above
    input_metadata = config['input_data'].values()
    logger.info(input_metadata)
    logger.info(group_metadata(input_metadata, 'dataset').items())
    loaded_data = {}
    for dataset, metadata in group_metadata(input_metadata, 'dataset').items():
        cubes, ancestors = get_input_cubes(metadata)
        loaded_data[dataset] = cubes

    logger.info('Robs text 2 ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ')
    logger.info(loaded_data)

    # loaded data is a nested dictionary
    # KEY1 model ESACCI-LST or something else
    # KEY2 is ts, the surface temperature
    # ie loaded_data['ESACCI-LST']['ts'] is the CCI cube
    #    loaded_data['MultiModelMean']['ts'] is CMIP6 data, emsemble means, see preprocessor

    ##### The Diagnostic uses CCI - MODEL

    # CMIP data had 360 day calendar, CCI data has 365 day calendar
    # Assume the loaded data is all the same shape !!!!
    loaded_data['MultiModelMean']['ts'].remove_coord('time')
    loaded_data['MultiModelMean']['ts'].add_dim_coord(loaded_data['ESACCI-LST']['ts'].coord('time'),0)
    loaded_data['MultiModelStd']['ts'].remove_coord('time')
    loaded_data['MultiModelStd']['ts'].add_dim_coord(loaded_data['ESACCI-LST']['ts'].coord('time'),0)

    # Make a cube of the LST difference
    lst_diff_cube = loaded_data['ESACCI-LST']['ts'] - loaded_data['MultiModelMean']['ts']
    lst_diff_cube_low = loaded_data['ESACCI-LST']['ts'] - (loaded_data['MultiModelMean']['ts']+loaded_data['MultiModelStd']['ts'])
    lst_diff_cube_high = loaded_data['ESACCI-LST']['ts'] - (loaded_data['MultiModelMean']['ts']-loaded_data['MultiModelStd']['ts'])
    logger.info('qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq')
    logger.info(lst_diff_cube_low)
    logger.info(lst_diff_cube_low.data)

    # plotting
    make_plots(lst_diff_cube,lst_diff_cube_low,lst_diff_cube_high, config)

    return None

if __name__ == '__main__':
    # always use run_diagnostic() to get the config (the preprocessor
    # nested dictionary holding all the needed information)
    with run_diagnostic() as config:
        # list here the functions that need to run
        diagnostic(config)


