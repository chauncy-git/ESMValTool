"""Script to download Duveiller2018 from its webpage."""
import logging

from esmvaltool.cmorizers.data.downloaders.wget import WGetDownloader

logger = logging.getLogger(__name__)


# pylint: disable=invalid-name
def download_dataset(config, dataset, _, __, overwrite):
    """Download dataset.

    Parameters
    ----------
    config : dict
        ESMValTool's user configuration
    dataset : str
        Name of the dataset
    start_date : datetime
        Start of the interval to download
    end_date : datetime
        End of the interval to download
    overwrite : bool
        Overwrite already downloaded files
    """
    downloader = WGetDownloader(
        config=config,
        dataset=dataset,
        overwrite=overwrite,
    )
    downloader.download_file(
        'https://s3-eu-west-1.amazonaws.com/pstorage-npg-968563215/'
        '9969496/albedo_IGBPgen.nc',
        wget_options=[])
