"""
update redis with WA loci values

This script is required by wolfdb.py

"""

from sqlalchemy import text

import functions as fn
import json
import redis

from config import config

params = config()

# dev version use db 0
rdis = redis.Redis(db=(0 if params["database"] == "wolf" else 1))


# loci list
loci_list: dict = fn.get_loci_list()

print(f"{loci_list=}")


with fn.conn_alchemy().connect() as con:
    sql = text("SELECT wa_code FROM wa_scat_dw_mat WHERE UPPER(mtdna) not like '%POOR DNA%' ")

    for row in con.execute(sql).mappings().all():
        print(f'{row["wa_code"]=}')
        rdis.set(row["wa_code"], json.dumps(fn.get_wa_loci_values(row["wa_code"], loci_list)[0]))
