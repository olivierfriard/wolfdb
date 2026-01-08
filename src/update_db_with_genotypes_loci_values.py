"""
update redis with genotypes loci values

This script is required by wolfdb.py

"""

import sys
from sqlalchemy import text
from sqlalchemy import text, bindparam
from sqlalchemy.dialects.postgresql import JSONB
import functions as fn
import json
import time
from datetime import datetime

from config import config

params = config()
if not params:
    print("Parameters not found")
    sys.exit(1)


def update_db_genotypes_loci():
    """
    update Redis with loci values of WA codes
    from PostgreSQL
    """

    print("Updating DB with genotypes loci")
    t0 = time.time()


    # loci list
    loci_list: dict = fn.get_loci_list()

    with fn.conn_alchemy().connect() as con:
        
        genotypes_list = [row["genotype_id"] for row in (
            con.execute(text("SELECT genotype_id FROM genotypes")).mappings().all()
        )]
        
        for genotype_id in genotypes_list:
            # print(f'{row["genotype_id"]=}')

            _ = con.execute(
                            text(
                                "INSERT INTO genotype_loci_values (genotype_id, loci_values) "
                                "VALUES (:genotype_id, :loci_values) "
                                "ON CONFLICT (genotype_id) "
                                "DO UPDATE "
                                "SET loci_values = EXCLUDED.loci_values; "
                            ).bindparams(bindparam("loci_values", type_=JSONB)),
                            {
                                "genotype_id": genotype_id,
                                "loci_values": fn.get_genotype_loci_values(genotype_id, loci_list),
                            },
                        )

    print(f"DB updated with genotypes loci in {round(time.time() - t0, 1)} seconds")


if __name__ == "__main__":
    update_db_genotypes_loci()
