import os
from configparser import ConfigParser


def config():

    if os.environ['WOLF_WS_MODE'] == 'prod':
        filename = 'database.ini'
    else:
        filename = 'database_dev.ini'

    parser = ConfigParser()
    # read config file
    parser.read(filename)

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


