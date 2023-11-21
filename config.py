"""
WolfDB
Read configuration file (config.ini)
"""

import os
import json
from pathlib import Path
from configparser import ConfigParser


def config() -> dict:
    config_filename = os.environ.get("WOLFDB_CONFIG_PATH")

    if config_filename is None:
        print("environment variable WOLFDB_CONFIG_PATH not set")
        return {}

    if not Path(config_filename).is_file():
        print("config.ini not found")
        return {}

    parser = ConfigParser()
    parser.read(config_filename)
    db: str = {}
    for section in parser.sections():
        params = parser.items(section)
        for param in params:
            db[param[0]] = param[1]

    # convert from str to list
    db["excel_allowed_extensions"] = json.loads(db["excel_allowed_extensions"])

    # add config dir
    db["config_dir"] = Path(config_filename).parent

    return db
