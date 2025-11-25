"""
import genetic data
"""

from sqlalchemy import text
import pathlib as pl
import pandas as pd
import functions as fn
from config import config
import json
import redis

params = config()
# db wolf -> db 0
rdis = redis.Redis(db=(0 if params["database"] == "wolf" else 1))


def extract_genotypes_data_from_xlsx(filename, loci_list):
    """
    Extract and check data from a XLSX file
    """

    def test_nan(v):
        if str(v) == "NaT":
            return True
        return isinstance(v, float) and str(v) == "nan"

    if pl.Path(filename).suffix == ".XLSX":
        engine = "openpyxl"
    if pl.Path(filename).suffix == ".ODS":
        engine = "odf"

    try:
        df = pd.read_excel(
            pl.Path(params["upload_folder"]) / pl.Path(filename),
            sheet_name=0,
            engine=engine,
        )
    except Exception:
        return (
            True,
            fn.alert_danger("Error reading the file. Check your XLSX/ODS file"),
            {},
        )

    # convert all dataframe columns to upper
    df.columns = [x.upper() for x in df.columns]

    expected_columns: tuple = (
        "genotype_id",
        "tmp_id",
        "date",
        "record_status",
        "sex",
        "mtdna",
        "pack",
        "status",
        "status_first_capture",
        "age_first_capture",
        "dispersal",
        # "changed_status",
        # "n_recaptures",
        "dead_recovery",
        "hybrid",
        "notes",
    )

    mandatory_columns: tuple = ("genotype_id", "record_status")

    accepted_values: dict = {"record_status": ["OK", "temp"], "sex": ("F", "M", "")}

    for column in expected_columns:
        if column.upper() not in list(df.columns):
            return True, fn.alert_danger(f"Column {column.lower()} is missing"), {}

    all_data: dict = {}
    problems: list = []
    for index, row in df.iterrows():
        data: dict = {}
        for column in expected_columns:
            col_up = column.upper()
            if col_up == "DATE":
                if str(row[col_up]) in ("nan", "NaT"):
                    data[column] = None
                else:
                    data[column] = str(row[col_up]).strip()
            else:
                # check if value present for mandatory column

                if col_up in [x.upper() for x in mandatory_columns] and str(
                    row[col_up]
                ) in ("nan", "NaT"):
                    problems.append(f"Row {index + 2}: the {column} value is mandatory")

                value = (
                    ""
                    if str(row[col_up]).strip() in ("nan", "NaT")
                    else str(row[col_up]).strip()
                )
                if column in accepted_values:
                    if value not in accepted_values[column]:
                        problems.append(
                            f"Row {index + 2}: the value for {column} must be {' or '.join(accepted_values[column])}"
                        )

                data[column] = value

        loci_dict: dict = {}
        for locus in loci_list:
            if locus in row:
                if test_nan(row[locus]):
                    problems.append(
                        f"For <b>{data['genotype_id']}</b> the value for allele <b>a</b> for locus <b>{locus}</b> cannot be empty (choose 0 or -)"
                    )

                loci_dict[locus] = {}
                if test_nan(row[locus]) or str(row[locus]).strip() == "-":
                    loci_dict[locus]["a"] = None
                else:
                    try:
                        int(row[locus])
                        loci_dict[locus]["a"] = row[locus]
                    except Exception:
                        problems.append(
                            f"For <b>{data['genotype_id']}</b> the value for allele <b>a</b> for locus <b>{locus}</b> ({row[locus]}) is wrong"
                        )

            if loci_list[locus] == 2:
                if locus + ".1" in row:
                    if test_nan(row[locus]):
                        problems.append(
                            f"For <b>{data['genotype_id']}</b> the value for allele <b>b</b> for locus <b>{locus}</b> cannot be empty (choose 0 or -)"
                        )
                    if (
                        test_nan(row[locus + ".1"])
                        or str(row[locus + ".1"]).strip() == "-"
                    ):
                        loci_dict[locus]["b"] = None
                    else:
                        try:
                            int(row[locus + ".1"])
                            loci_dict[locus]["b"] = row[locus + ".1"]
                        except Exception:
                            problems.append(
                                f"For <b>{data['genotype_id']}</b> the value for allele <b>b</b> for locus <b>{locus}</b> is wrong"
                            )

                    # loci_dict[locus]["b"] = row[locus + ".1"] if not test_nan(row[locus + ".1"]) else None

        all_data[index] = {**data, **loci_dict}

    if problems:
        return (
            True,
            fn.alert_danger(f"Check the input file!<br><br>{'<br>'.join(problems)}"),
            {},
        )

    return 0, "OK", all_data


def import_definitive_genotypes(filename):
    # loci list
    loci_list = fn.get_loci_list()

    _, _, data = extract_genotypes_data_from_xlsx(filename, loci_list)

    insert_sql = text(
        "INSERT INTO genotypes ("
        "genotype_id,"
        "date,"
        "record_status,"
        "pack,"
        "sex,"
        "age_first_capture,"
        "status_first_capture,"
        "dispersal,"
        "dead_recovery,"
        "status,"
        "tmp_id,"
        "notes,"
        # "changed_status,"
        "hybrid,"
        "mtdna"
        ") VALUES ("
        ":genotype_id,"
        ":date,"
        ":record_status,"
        ":pack,"
        ":sex,"
        ":age_first_capture,"
        ":status_first_capture,"
        ":dispersal,"
        ":dead_recovery,"
        ":status,"
        ":tmp_id,"
        ":notes,"
        # ":changed_status,"
        ":hybrid,"
        ":mtdna"
        ") "
        "ON CONFLICT (genotype_id) DO UPDATE "
        "SET "
        "date = EXCLUDED.date,"
        "record_status = EXCLUDED.record_status,"
        "pack = EXCLUDED.pack,"
        "sex = EXCLUDED.sex,"
        "age_first_capture = EXCLUDED.age_first_capture,"
        "status_first_capture = EXCLUDED.status_first_capture,"
        "dispersal = EXCLUDED.dispersal,"
        "dead_recovery = EXCLUDED.dead_recovery,"
        "status = EXCLUDED.status,"
        "tmp_id = EXCLUDED.tmp_id,"
        "notes = EXCLUDED.notes,"
        # "changed_status = EXCLUDED.changed_status,"
        "hybrid = EXCLUDED.hybrid,"
        "mtdna = EXCLUDED.mtdna"
    )

    with fn.conn_alchemy().connect() as con:
        # check if genotype_id already in DB
        genotypes_list = "','".join([data[idx]["genotype_id"] for idx in data])
        sql = text(
            f"SELECT genotype_id FROM genotypes WHERE genotype_id IN ('{genotypes_list}')"
        )
        genotypes_to_update = [
            row["genotype_id"] for row in con.execute(sql).mappings().all()
        ]

        for idx in data:
            values = dict(data[idx])

            print()
            print(values)
            print()
            print(loci_list)

            if values["genotype_id"] in genotypes_to_update:
                for field in values:
                    if field in loci_list or field.replace(".1", "") in loci_list:
                        continue
                    if not values[field]:
                        continue

                    print(
                        f"UPDATE genotypes SET {field} = '{values[field]}' WHERE genotype_id = '{values['genotype_id']}'"
                    )

                    sql = text(
                        f"UPDATE genotypes SET {field} = :value WHERE genotype_id = :genotype_id_"
                    )
                    con.execute(
                        sql,
                        {"value": values[field], "genotype_id_": values["genotype_id"]},
                    )

            else:  # insert new
                con.execute(insert_sql, values)

            # insert loci
            for locus in loci_list:
                sql_loci = text(
                    "INSERT INTO genotype_locus (genotype_id, locus, allele, val, timestamp) VALUES (:genotype_id, :locus, :allele, :val, NOW())"
                )
                for allele in ("a", "b"):
                    if allele in values[locus]:
                        con.execute(
                            sql_loci,
                            {
                                "genotype_id": values["genotype_id"],
                                "locus": locus,
                                "allele": allele,
                                "val": values[locus][allele],
                            },
                        )

            # update redis
            rdis.set(
                values["genotype_id"],
                json.dumps(
                    fn.get_genotype_loci_values(values["genotype_id"], loci_list)
                ),
            )

        con.execute(text("REFRESH MATERIALIZED VIEW genotypes_list_mat"))
        con.execute(text("REFRESH MATERIALIZED VIEW wa_genetic_samples_mat"))
