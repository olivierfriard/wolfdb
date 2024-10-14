"""
update redis with WA loci values

This script is required by wolfdb.py

"""

import sys
from sqlalchemy import text
import functions as fn
import json
import redis
import time
from datetime import datetime

from config import config

params = config()
if not params:
    print("Parameters not found")
    sys.exit(1)


def update_redis_wa_loci():
    """
    update Redis with loci values of WA codes
    from PostgreSQL
    """

    print("Updating REDIS with WA codes loci")
    t0 = time.time()
    # dev version use db #1
    rdis = redis.Redis(db=(0 if params["database"] == "wolf" else 1))

    # loci list
    loci_list: dict = fn.get_loci_list()

    with fn.conn_alchemy().connect() as con:
        sql = text("SELECT wa_code FROM wa_scat_dw_mat WHERE UPPER(mtdna) not like '%POOR DNA%' ")

        for row in con.execute(sql).mappings().all():
            print(f'{row["wa_code"]=}')

            rdis.set(row["wa_code"], json.dumps(fn.get_wa_loci_values(row["wa_code"], loci_list)[0]))

    rdis.set("UPDATE WA LOCI", datetime.now().isoformat())

    print(f"REDIS updated with WA codes loci in {time.time() - t0}")


if __name__ == "__main__":
    update_redis_wa_loci()
