import logging
import os

import cartopy
import matplotlib.pyplot as plt
import yaml
from iris.analysis import MEAN
from mapgenerator.plotting.timeseries import PlotSeries

import esmvaltool.diag_scripts.shared.names as n

logger = logging.getLogger(__name__)


class MonitorBase(object):
    def __init__(self, config):
        self.cfg = config
        self.plots_path = '/esarchive/exp/ecearth'
        self.plots = config.get('plots', {})
        default_config = os.path.join(os.path.dirname(__file__),
                                      "monitor_config.yml")
        cartopy.config['data_dir'] = '/esarchive/scratch/Earth/jvegas/cartopy'
        with open(config.get('config_file', default_config)) as config_file:
            self.config = yaml.safe_load(config_file)

    def _get_proj_options(self, map_name):
        return self.config['maps'][map_name]

    def _get_variable_options(self, variable_group, map_name):
        options = self.config['variables'].get(
            variable_group, self.config['variables']['default'])
        if 'default' not in options:
            variable_options = options
        else:
            variable_options = options['default']
            if map_name in options:
                variable_options = {**variable_options, **options[map_name]}

        if 'bounds' in variable_options:
            if not isinstance(variable_options['bounds'], str):
                variable_options['bounds'] = [
                    float(n) for n in variable_options['bounds']
                ]
        logger.debug(variable_options)
        return variable_options

    def plot_timeseries(self, cube, var_info, type='', **kwargs):
        if 'xlimits' not in kwargs:
            kwargs['xlimits'] = 'auto'
        length = cube.coord("year").points.max() - cube.coord(
            "year").points.min()
        filename = self.get_plot_path(f'timeseries{type}', var_info, None)
        if length < 10 or length * 11 > cube.coord("year").shape[0]:
            self.plot_cube(cube, filename, **kwargs)
        elif length < 70:
            self.plot_cube(cube,
                           filename,
                           linestyle=':',
                           labels=False,
                           **kwargs)
            plt.gca().set_prop_cycle(None)
            self.plot_cube(cube.rolling_window('time', MEAN, 12), filename,
                           **kwargs)
        else:
            self.plot_cube(cube.rolling_window('time', MEAN, 12),
                           filename,
                           linestyle=':',
                           labels=False,
                           **kwargs)
            plt.gca().set_prop_cycle(None)
            self.plot_cube(cube.rolling_window('time', MEAN, 120), filename,
                           **kwargs)

    @staticmethod
    def plot_cube(cube, filename, linestyle='-', labels=True, **kwargs):
        plotter = PlotSeries()
        plotter.filefmt = 'svg'
        plotter.img_template = filename
        region_coords = ('shape_id', 'region')

        for region_coord in region_coords:
            if cube.coords(region_coord):
                if cube.coord(region_coord).shape[0] > 1:
                    plotter.multiplot_cube(cube, 'time', region_coord,
                                           **kwargs)
                    return
        plotter.plot_cube(cube, linestyle=linestyle, **kwargs)

    def get_plot_path(self, plot_type, var_info, file_type='svg'):
        return os.path.join(self.get_plot_folder(var_info),
                            self.get_plot_name(plot_type, var_info, file_type))

    def get_plot_folder(self, var_info):
        folder = os.path.join(self.plots_path, var_info['expid'], 'plots',
                              var_info['modeling_realm'][0],
                              self._real_name(var_info['variable_group']))
        if not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)
        return folder

    def get_plot_name(self, plot_type, var_info, file_type='svg'):
        file_name = '_'.join([
            plot_type,
            self._real_name(var_info['variable_group']), var_info[n.DATASET],
            var_info['mip'], var_info[n.EXP], var_info[n.ENSEMBLE]
        ])
        if file_type:
            file_name += '.' + file_type
        return file_name

    @staticmethod
    def _real_name(variable_group):
        for subfix in ('Ymean', 'Ysum', 'mean', 'sum'):
            if variable_group.endswith(subfix):
                variable_group = variable_group.replace(subfix, '')
        return variable_group