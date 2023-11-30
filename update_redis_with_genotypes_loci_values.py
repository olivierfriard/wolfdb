"""
update redis with genotypes loci values

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

with fn.conn_alchemy().connect() as con:
    # loci list
    loci_list = fn.get_loci_list()

    results = con.execute(text("SELECT genotype_id FROM genotypes")).mappings().all()
    for idx, row in enumerate(results):
        print(f"{idx=}")
        rdis.set(row["genotype_id"], json.dumps(fn.get_loci_value(row["genotype_id"], loci_list)))
