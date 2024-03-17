"""
update redis with WA loci values

This script is required by wolfdb.py

"""

import sys
from sqlalchemy import text
import functions as fn
import json
from datetime import datetime

from config import config

params = config()
if not params:
    print("Parameters not found")
    sys.exit()

# loci list
loci_list: dict = fn.get_loci_list()

data = {}

with fn.conn_alchemy().connect() as con:
    sql = text("SELECT * FROM wa_locus ORDER BY wa_code,locus,allele,timestamp")
    wa_codes = con.execute(sql).mappings().all()
    for r in wa_codes:
        # print(f'{r["wa_code"]=}')

        # sql = text("SELECT * FROM wa_locus WHERE wa_code = :wa_code ORDER BY locus, allele, timestamp")
        # loci = con.execute(sql, {"wa_code": row["wa_code"]}).mappings().all()

        if (r["wa_code"], r["locus"], r["allele"]) not in data:
            data[(r["wa_code"], r["locus"], r["allele"])] = []
        data[(r["wa_code"], r["locus"], r["allele"])] = (r["timestamp"].strftime("%s"), r["notes"], r["user_id"])

# print(data)

for wla in data:
    wa_code, locus, allele = wla
    timestamp, notes, user_id = data[wla]
    if notes is not None or user_id is not None:
        print(wa_code, locus, allele, timestamp, notes, user_id)
