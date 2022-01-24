"""
check if path id contains 2 underscores

"""


import psycopg2
import psycopg2.extras
import functions as fn

import subprocess
import sys


connection = fn.get_connection()
cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

cursor.execute("SELECT path_id FROM paths ")
rows = cursor.fetchall()
for row in rows:

    if row["path_id"].count("_") > 1:
        print(row["path_id"])