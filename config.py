"""
WolfDB
Read configuration file (config.ini)
"""

from pathlib import Path
from configparser import ConfigParser

def config():

    if (Path(__file__).parent / "DEV").is_file():
        service_name = "wolfdb_dev"
    else:
        service_name = "wolfdb"

    config_filename = Path.home() / ".config" / service_name / "config.ini"

    if not config_filename.is_file():
        print("config.ini not found")
        return {}

    parser = ConfigParser()
    parser.read(config_filename)
    db: str = {}
    for section in parser.sections():
        params = parser.items(section)
        for param in params:
            db[param[0]] = param[1]

    # add config dir
    db["config_dir"] = config_filename.parent

    return db


