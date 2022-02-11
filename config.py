import os
from configparser import ConfigParser


def config():

    config_filename = "config.ini"

    parser = ConfigParser()
    # read config file
    parser.read(config_filename)

    db = {}
    if parser.has_section('postgresql'):
        params = parser.items('postgresql')
        for param in params:
            db[param[0]] = param[1]
    else:
        raise Exception("Section postgresql not found")

    if parser.has_section("web_service"):
        params = parser.items("web_service")
        for param in params:
            db[param[0]] = param[1]
    else:
        raise Exception("Section web_service not found")

    return db


