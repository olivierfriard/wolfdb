"""
update redis with genotypes loci values

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

def get_loci_value(genotype_id, loci_list):
    """
    get genotype loci values
    """

    loci_values = {}
    for locus in loci_list:
        loci_values[locus] = {}
        loci_values[locus]['a'] = {"value": "-", "notes": "", "user_id": "" }
        loci_values[locus]['b'] = {"value": "-", "notes": "", "user_id": "" }

    for locus in loci_list:

        cursor.execute(("SELECT val, allele, notes, user_id, extract(epoch from timestamp)::integer AS epoch "
                        "FROM genotype_locus "
                        "WHERE genotype_id = %(genotype_id)s AND locus = %(locus)s AND allele = 'a' "
                        "UNION "
                        "SELECT val, allele, notes, user_id, extract(epoch from timestamp)::integer AS epoch "
                        "FROM genotype_locus "
                        "WHERE genotype_id = %(genotype_id)s AND locus = %(locus)s AND allele = 'b' "
                        ),
                        {"genotype_id": genotype_id, "locus": locus})

        locus_val = cursor.fetchall()

        for row2 in locus_val:
            val = row2["val"] if row2["val"] is not None else "-"
            notes = row2["notes"] if row2["notes"] is not None else ""
            user_id = row2["user_id"] if row2["user_id"] is not None else ""
            epoch = row2["epoch"] if row2["epoch"] is not None else ""

            loci_values[locus][row2["allele"]] = {"value": val, "notes": notes, "epoch": epoch, "user_id": user_id}

    return loci_values


# loci list
loci_list = {}
cursor.execute("SELECT name, n_alleles FROM loci ORDER BY position ASC")
for row in cursor.fetchall():
    loci_list[row["name"]] = row["n_alleles"]

cursor.execute(("SELECT genotype_id FROM genotypes"))
results = cursor.fetchall()

for idx, row in enumerate(results):

    print(f"{idx=}")
    rdis.set(row["genotype_id"], json.dumps(get_loci_value(row['genotype_id'], loci_list)))