"""
update redis with WA loci values

This script is required by wolfdb.py

"""

import sys

# import json
import time
from datetime import datetime

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB

import functions as fn
from config import config

params = config()
if not params:
    print("Parameters not found")
    sys.exit(1)


def update_db_wa_loci():
    """
    update db with loci values of WA codes
    """

    print("Updating DB with WA codes loci")
    t0 = time.time()
    # dev version use db #1

    # loci list
    loci_list: dict = fn.get_loci_list()

    with fn.conn_alchemy().connect() as con:
        sql = text("SELECT wa_code, laboratory_acronym FROM wa_results")

        wa_list = con.execute(sql).mappings().all()

        for row in wa_list:
            _ = con.execute(
                text(
                    "INSERT INTO wa_loci_values (wa_code, laboratory_acronym, loci_values) "
                    "VALUES (:wa_code, :laboratory, :loci_values) "
                    "ON CONFLICT (wa_code, laboratory_acronym) "
                    "DO UPDATE "
                    "SET loci_values = EXCLUDED.loci_values; "
                ).bindparams(bindparam("loci_values", type_=JSONB)),
                {
                    "wa_code": row["wa_code"],
                    "laboratory": row["laboratory_acronym"],
                    "loci_values": fn.get_wa_loci_values_by_lab(
                        row["laboratory_acronym"], row["wa_code"], loci_list, con=con
                    )[0],
                },
            )

    print(f"DB updated with WA codes loci in {round(time.time() - t0, 1)} seconds")


if __name__ == "__main__":
    update_db_wa_loci()
