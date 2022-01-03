
import psycopg2
import psycopg2.extras
import functions as fn

import subprocess
import sys


connection = fn.get_connection()
cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

cursor.execute("select genotype_id, tmp_id from genotypes where status = 'temp' ")
rows = cursor.fetchall()
for row in rows:

    if row["tmp_id"]:
        #print(row["tmp_id"], row["genotype_id"])

        tmp_id = row["tmp_id"]
        genotype_id = row["genotype_id"]
        sql = f"UPDATE wa_results SET genotype_id = '{genotype_id}' WHERE genotype_id = '{tmp_id}'; "
        print(sql)

    #cursor.execute(sql, [d['region'] ,d['province_code'], d['municipality'], d['location'], row["scat_id"]])
    #connection.commit()



