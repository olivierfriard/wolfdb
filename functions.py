"""
WolfDB web service
(c) Olivier Friard

functions module

"""


from flask import Flask, request
import psycopg2
import psycopg2.extras
from config import config


params = config()

def get_connection():
    return psycopg2.connect(user=params["user"],
                            password=params["password"],
                            host=params["host"],
                            #port="5432",
                            database=params["database"])



def all_transect_id():
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT transect_id FROM transect ORDER BY transect_id")
    return [x[0].strip() for x in cursor.fetchall()]

def all_path_id():
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT CONCAT(transect_id, ' ',  date) FROM paths ORDER BY date DESC")
    return [x[0].strip() for x in cursor.fetchall()]


def all_snow_tracks_id():
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT snowtrack_id FROM snow_tracks ORDER BY snowtrack_id")
    return [x[0].strip() for x in cursor.fetchall()]


def sampling_season(date):
    try:
        month = int(request.form['date'][5:6+1])
        year = int(request.form['date'][0:3+1])
        if 5 <= month <= 12:
            return f"{year}-{year + 1}"
        if 1 <= month <= 4:
            return f"{year - 1}-{year}"
    except Exception:
        return "Error"