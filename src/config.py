"""
WolfDB
Read configuration from .env
"""

import json
from pathlib import Path

from dotenv import dotenv_values


def config() -> dict:
    config_filename = Path(__file__).with_name(".env")

    if not config_filename.is_file():
        print(".env not found")
        return {}

    db = dotenv_values(config_filename)

    # convert from str to list
    db["excel_allowed_extensions"] = json.loads(db["excel_allowed_extensions"])

    # add config dir
    db["config_dir"] = Path(config_filename).parent

    return db
