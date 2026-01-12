"""
update redis with WA loci values

This script is required by wolfdb.py

"""

import sys
from sqlalchemy import text
from sqlalchemy import text, bindparam
from sqlalchemy.dialects.postgresql import JSONB
import functions as fn

# import json
import time
from datetime import datetime

from config import config

params = config()
if not params:
    print("Parameters not found")
    sys.exit(1)


def update_db_wa_loci():
    """
    update Redis with loci values of WA codes
    from PostgreSQL
    """

    print("Updating DB with WA codes loci")
    t0 = time.time()
    # dev version use db #1

    # loci list
    loci_list: dict = fn.get_loci_list()

    with fn.conn_alchemy().connect() as con:
        sql = text("SELECT DISTINCT wa_code FROM wa_scat_dw_mat ")

        wa_list = [row["wa_code"] for row in con.execute(sql).mappings().all()]

        for wa_code in wa_list:
            # wa_loci_values = json.dumps(fn.get_wa_loci_values(wa_code, loci_list)[0])

            _ = con.execute(
                text(
                    "INSERT INTO wa_loci_values (wa_code, loci_values) "
                    "VALUES (:wa_code, :loci_values) "
                    "ON CONFLICT (wa_code) "
                    "DO UPDATE "
                    "SET loci_values = EXCLUDED.loci_values; "
                ).bindparams(bindparam("loci_values", type_=JSONB)),
                {
                    "wa_code": wa_code,
                    "loci_values": fn.get_wa_loci_values(wa_code, loci_list)[0],
                },
            )
            # new_id = result.scalar_one()

            # rdis.set(
            #    row["wa_code"],
            #    json.dumps(fn.get_wa_loci_values(row["wa_code"], loci_list)[0]),
            # )

    print(f"DB updated with WA codes loci in {round(time.time() - t0, 1)} seconds")


if __name__ == "__main__":
    update_db_wa_loci()
