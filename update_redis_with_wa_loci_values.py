"""
update redis with WA loci values

This script is required by wolfdb.py

"""

import psycopg2
import psycopg2.extras


import functions as fn
import json
import redis

from config import config

params = config()

# dev version use db 0
rdis = redis.Redis(db=(0 if params["database"] == "wolf" else 1))

connection = fn.get_connection()
cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)


# loci list
loci_list = {}
cursor.execute("SELECT name, n_alleles FROM loci ORDER BY position ASC")
for row in cursor.fetchall():
    loci_list[row["name"]] = row["n_alleles"]


sql = "SELECT wa_code " "FROM wa_scat_dw " "WHERE UPPER(mtdna) not like '%POOR DNA%' "


cursor.execute(sql)
results = cursor.fetchall()

for idx, row in enumerate(results):

    print(row["wa_code"])
    rdis.set(row["wa_code"], json.dumps(fn.get_wa_loci_values(row["wa_code"], loci_list)[0]))
