"""
update postgresql db with WA loci values

CREATE TABLE wa_loci_values (
    wa_code character varying(100) NOT NULL,
    values JSONB
);

CREATE UNIQUE INDEX wa_loci_values_idx ON wa_loci_values USING btree (wa_code);


"""

from sqlalchemy import text

import functions as fn
import json

from config import config

params = config()

# loci list
loci_list: dict = fn.get_loci_list()

print(f"{loci_list=}")


with fn.conn_alchemy().connect() as con:
    sql = text("SELECT wa_code FROM wa_scat_dw_mat WHERE UPPER(mtdna) not like '%POOR DNA%' ")

    for row in con.execute(sql).mappings().all():
        print(f'{row["wa_code"]=}')
        con.execute(
            text(
                "INSERT INTO wa_loci_values "
                "(wa_code, values) "
                "VALUES (:wa_code, :values) "
                "ON CONFLICT (wa_code) DO UPDATE "
                "SET values = :values "
            ),
            {"wa_code": row["wa_code"], "values": json.dumps(fn.get_wa_loci_values(row["wa_code"], loci_list)[0])},
        )
