"""
WolfDB
Read configuration file (config.ini)
"""

from configparser import ConfigParser


def config():

    config_filename = "config.ini"

    parser = ConfigParser()
    # read config file
    parser.read(config_filename)

    db = {}
    for section in parser.sections():
        params = parser.items(section)
        for param in params:
            db[param[0]] = param[1]

    return db
