import os
import yaml
import logging
from schema import config_schema

# Environment variable configuration
STORAGE_PATH = os.environ.get('ONENVR_STORAGE', '/storage')
CONFIG_PATH = os.environ.get('ONENVR_CONFIG', '/config/config.yaml')


def setup_logging():
    """Configure application logging."""
    level = logging.DEBUG if os.environ.get('DEBUG') == 'true' else logging.INFO

    # Clear existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers = []

    # Configure logging
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

    # Specifically suppress werkzeug logs
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    return logger


def load_config(config_path=None):
    """
    Load and validate configuration from YAML file.

    Args:
        config_path: Path to config file. If None, uses CONFIG_PATH env var or default.

    Returns:
        Validated configuration dictionary
    """
    logger = logging.getLogger(__name__)

    if config_path is None:
        config_path = CONFIG_PATH

    logger.debug(f"Loading configuration from: {config_path}")

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        raise
    except yaml.YAMLError as e:
        logger.error(f"Invalid YAML in configuration file: {str(e)}")
        raise

    # Validate config
    try:
        config = config_schema(config)
    except Exception as e:
        logger.error(f"Configuration validation failed: {str(e)}")
        raise

    # Log configuration details if DEBUG is enabled
    if os.environ.get('DEBUG') == 'true':
        logger.debug("======== OneNVR Configuration ========")
        logger.debug(f"Storage path: {STORAGE_PATH}")
        logger.debug(f"Videos retention period: {config['retention_days']} day(s)")
        logger.debug(f"Concatenation mode: {'Enabled' if config['concatenation'] else 'Disabled'}")
        if config['concatenation']:
            logger.debug(f"Daily concatenation time: {config['concatenation_time']}")
        logger.debug(f"Cleanup time: {config['deletion_time']}")
        logger.debug(f"Configured cameras ({len(config['cameras'])}):")
        for camera in config['cameras']:
            logger.debug(f"  - {camera['name']}:")
            logger.debug(f"      RTSP URL: {camera['rtsp_url']}")
            logger.debug(f"      Codec: {camera['codec']}")
            logger.debug(f"      Segment interval: {camera['interval']} seconds")
        logger.debug("======================================")

    return config
