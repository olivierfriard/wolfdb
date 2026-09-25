"""
update redis with genotypes loci values

This script is required by wolfdb.py

"""

import json
import sys
import time
from datetime import datetime

import redis
from sqlalchemy import text

import functions as fn
from config import config

params = config()
if not params:
    print("Parameters not found")
    sys.exit(1)


def update_redis_genotypes_loci():
    """
    update Redis with loci values of WA codes
    from PostgreSQL
    """

    print("Updating REDIS with genotypes loci")
    t0 = time.time()

    # dev version use db #1
    rdis = redis.Redis(
        host=params["redis_host"], port=params["redis_port"], db=int(params["redis_db"])
    )

    # loci list
    loci_list: dict = fn.get_loci_list()

    with fn.conn_alchemy().connect() as con:
        for row in (
            con.execute(text("SELECT genotype_id FROM genotypes")).mappings().all()
        ):
            # print(f'{row["genotype_id"]=}')
            rdis.set(
                row["genotype_id"],
                json.dumps(fn.get_genotype_loci_values(row["genotype_id"], loci_list)),
            )

    rdis.set("UPDATE GENOTYPES LOCI", datetime.now().isoformat())

    print(f"REDIS updated with genotypes loci in {round(time.time() - t0, 1)} seconds")


if __name__ == "__main__":
    update_redis_genotypes_loci()
