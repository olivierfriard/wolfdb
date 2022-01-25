"""
update cache with genotypes loci values

This script is required by wolfdb.py

"""

import psycopg2
import psycopg2.extras
import functions as fn

import json
#import sys


connection = fn.get_connection()
cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

def get_loci_value(genotype_id, loci_list):
    """
    get genotype loci values
    """

    loci_values = {}
    for locus in loci_list:
        loci_values[locus] = {}
        loci_values[locus]['a'] = {"value": "-", "notes": "" }
        loci_values[locus]['b'] = {"value": "-", "notes": "" }

    for locus in loci_list:

        cursor.execute(("SELECT val, allele, notes, extract(epoch from timestamp)::integer AS epoch "
                        "FROM genotype_locus "
                        "WHERE genotype_id = %(genotype_id)s AND locus = %(locus)s AND allele = 'a' "
                        "UNION "
                        "SELECT val, allele, notes, extract(epoch from timestamp)::integer AS epoch "
                        "FROM genotype_locus "
                        "WHERE genotype_id = %(genotype_id)s AND locus = %(locus)s AND allele = 'b' "
                        ),
                        {"genotype_id": genotype_id, "locus": locus})

        locus_val = cursor.fetchall()

        for row2 in locus_val:
            val = row2["val"] if row2["val"] is not None else "-"
            notes = row2["notes"] if row2["notes"] is not None else ""
            epoch = row2["epoch"] if row2["epoch"] is not None else ""

            loci_values[locus][row2["allele"]] = {"value": val, "notes": notes, "epoch": epoch}

    return loci_values


cursor.execute("CREATE TABLE  IF NOT EXISTS cache (key varchar(50), val text, updated timestamp)")
connection.commit()
cursor.execute("DROP INDEX  IF EXISTS cache_key ")
connection.commit()
cursor.execute("CREATE UNIQUE index cache_key ON cache (key)")
connection.commit()


# loci list
loci_list = {}
cursor.execute("SELECT name, n_alleles FROM loci ORDER BY position ASC")
for row in cursor.fetchall():
    loci_list[row["name"]] = row["n_alleles"]

cursor.execute(("SELECT genotype_id FROM genotypes"))
results = cursor.fetchall()

for row in results:

    cursor.execute("DELETE FROM cache WHERE key = %s ", [row["genotype_id"]])
    connection.commit()
    cursor.execute("INSERT INTO cache (key, val, updated) VALUES (%s, %s, NOW()) ",
                [row["genotype_id"], json.dumps(get_loci_value(row['genotype_id'], loci_list))])
    connection.commit()




