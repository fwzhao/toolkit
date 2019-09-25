from setuptools_scm import get_version as _get_version

__version__ = _get_version(root='..', relative_to=__file__)


def setup_logger(level="INFO", logfile=None):
    """
    Set up a logger for the library.

    Parameters
    ----------

    level : :obj:`str`, optional
        Level of logging to display.
        See possible levels here:
        https://docs.python.org/2/library/logging.html#levels

        Defaults to "INFO".

    logfile : :obj:`str`, optional
        File to write log to.

        Defaults to ``~/.ngs_toolkit.log.txt``.

    Returns
    -------
    :class:`logging.Logger`
        A logger called "ngs_toolkit".
    """
    import logging
    import os

    _LOGGER = logging.getLogger("ngs_toolkit")
    _LOGGER.setLevel(logging.DEBUG)
    # create file handler which logs even debug messages
    if logfile is None:
        logfile = os.path.join(os.path.expanduser("~"), ".ngs_toolkit.log.txt")
    fh = logging.FileHandler(logfile)
    fh.setLevel(logging.DEBUG)
    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.getLevelName(level))
    # create formatter and add it to the handlers
    fmt = "ngs_toolkit.v{}:%(module)s:L%(lineno)d ".format(__version__)
    fmt += "(%(funcName)s) [%(levelname)s] %(asctime)s > %(message)s"
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")
    fh.setFormatter(formatter)
    # fmt = "[%(levelname)s] > %(message)s"
    fmt = "ngs_toolkit:%(module)s:L%(lineno)d (%(funcName)s) [%(levelname)s]"
    fmt += " > %(message)s"
    formatter = logging.Formatter(fmt)
    ch.setFormatter(formatter)
    # add the handlers to the logger
    _LOGGER.addHandler(fh)
    _LOGGER.addHandler(ch)

    _LOGGER.debug(
        "This is ngs_toolkit (http://ngs-toolkit.rtfd.io), version: {}"
        .format(__version__)
    )
    return _LOGGER


def setup_config(custom_yaml_config=None):
    """
    Set up global library configuration.

    It reads ngs_toolkit's package data to load a default configuration,
    tries to update it by reading a file in ``~/.ngs_toolkit.config.yaml``
    if present, and lastly, updates it by reading a possible passed yaml file
    ``custom_yaml_config``.
    Non-exisiting fields will maintain the previous values, so that the user
    needs only to specify the section(s) as needed.

    Parameters
    ----------
    custom_yaml_config : :obj:`str`, optional
        Path to YAML file with configuration.
        To see the structure of the YAML file, see
        https://github.com/afrendeiro/toolkit/blob/master/ngs_toolkit/config/default.yaml

        Defaults to :obj:`None`.

    Returns
    -------
    dict
        Dictionary with configurations.
    """
    import pkg_resources
    import os
    import yaml

    default_config_path = "config/default.yaml"
    default_config_path = pkg_resources.resource_filename(
        __name__, default_config_path)
    _LOGGER.debug(
        "Reading default configuration file distributed"
        " with package from '{}'.".format(
            default_config_path
        )
    )
    try:
        _CONFIG = yaml.safe_load(open(default_config_path, "r"))
        _LOGGER.debug("Default config: {}".format(_CONFIG))
    except IOError:
        _LOGGER.error(
            "Couldn't read configuration file from '{}'."
            .format(default_config_path)
        )
        _CONFIG = dict()

    user_config_path = os.path.join(
        os.path.expanduser("~"), ".ngs_toolkit.config.yaml")
    if os.path.exists(user_config_path):
        # Read up
        _LOGGER.debug("Found custom user config: {}".format(user_config_path))
        try:
            custom_config = yaml.safe_load(open(user_config_path, "r"))
            _LOGGER.debug("Custom user config: {}".format(custom_config))
            # Update config
            _LOGGER.debug(
                "Updating configuration with custom file from '{}'."
                .format(user_config_path)
            )
            _CONFIG.update(custom_config)
            _LOGGER.debug("Current config: {}".format(custom_config))
        except IOError:
            _LOGGER.error(
                "Configuration file from '{}' exists but is not readable."
                " Ignoring."
                .format(user_config_path)
            )
    else:
        _LOGGER.debug(
            "To use custom configurations including paths to static files,"
            " create a '{}' file.".format(user_config_path)
        )

    if custom_yaml_config is not None:
        # Read up
        try:
            custom_config = yaml.safe_load(open(custom_yaml_config, "r"))
            _LOGGER.debug("Custom passed config: {}".format(custom_config))
            # Update config
            _LOGGER.debug(
                "Updating configuration with custom file from '{}'.".format(
                    custom_yaml_config
                )
            )
            _CONFIG.update(custom_config)
            _LOGGER.debug("Current config: {}".format(custom_config))
        except IOError as e:
            _LOGGER.error(
                "Passed configuration from '{}' exists but is not readable."
                .format(custom_yaml_config)
            )
            raise e

    return _CONFIG


def setup_graphic_preferences():
    """
    Set up graphic preferences.

    It uses the values under "preferences:graphics:matplotlib:rcParams"
    and "preferences:graphics:seaborn:parameters" to matplotlib
    and seaborn respectively.
    """
    import matplotlib
    import seaborn as sns

    graphics = _CONFIG["preferences"]["graphics"]
    # matplotlib
    rc_params = graphics["matplotlib"]["rcParams"]
    matplotlib.rcParams.update(rc_params)
    matplotlib.rcParams["svg.fonttype"] = "none"
    matplotlib.rc("text", usetex=False)

    # seaborn
    seaborn_params = graphics["seaborn"]["parameters"]
    sns.set(**seaborn_params)


def clear_log():
    import os

    logfile = os.path.join(os.path.expanduser("~"), ".ngs_toolkit.log.txt")
    open(logfile, "w")


def setup_timestamping():
    if _CONFIG["preferences"]["report"]["record_csv"]:
        from ngs_toolkit.decorators import (
            read_csv_timestamped,
            to_csv_timestamped)
        import pandas as pd

        pd.io.parsers.TextFileReader = read_csv_timestamped(
            pd.io.parsers.TextFileReader)
        pd.DataFrame.to_csv = to_csv_timestamped(
            pd.DataFrame.to_csv,
            exclude_functions=["from_dataframe"])


def check_bedtools_version():
    import pybedtools

    version = pybedtools.helpers.settings.bedtools_version
    # not existing
    v = ".".join(
        [str(x) for x in version])
    msg = "Bedtools does not seem to be installed or is not in $PATH."
    if v == '':
        raise Exception(msg)

    # too low version
    msg = "Bedtools version '{}' is smaller than 2.26.".format(v)
    msg += " Please upgrade to newer version."
    if (version[0] < 2) or (version[1] < 26):
        raise Exception(msg)


# setup
_LOGGER = setup_logger()
_CONFIG = setup_config()
check_bedtools_version()
setup_graphic_preferences()
setup_timestamping()


# easier API
from ngs_toolkit.analysis import Analysis
from ngs_toolkit.atacseq import ATACSeqAnalysis
from ngs_toolkit.chipseq import ChIPSeqAnalysis
from ngs_toolkit.cnv import CNVAnalysis
from ngs_toolkit.rnaseq import RNASeqAnalysis
