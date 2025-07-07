from pathlib import Path
import pandas as pd
from markupsafe import Markup
from sqlalchemy import text

from config import config
import functions as fn

DEBUG = False
params = config()


"""
import WA data from a spreadsheet file
"""


def extract_wa_data_from_spreadsheet(filename: str):
    """
    Extract and check data from a spreadsheet file (XLSX or ODS)
    """
    if Path(filename).suffix.upper() == ".XLSX":
        engine = "openpyxl"
    if Path(filename).suffix.upper() == ".ODS":
        engine = "odf"

    out: str = ""

    try:
        genetic_df = pd.read_excel(Path(params["upload_folder"]) / Path(filename), sheet_name=0, engine=engine)
    except Exception:
        return (True, fn.alert_danger("Error reading the file. Check your XLSX/ODS file"), {}, {})

    # replace _A by _a in column names
    genetic_df.columns = genetic_df.columns.str.lower()

    required_columns = (
        "WA code",
        "mtDNA",
        "quality_genotype",
        "Other ID",
        "Genotype ID",
        "record_status",
        "Sex ID",
        "Pack",
        "Note",
    )

    # check columns
    for column, column_lower in zip(required_columns, [x.lower() for x in required_columns]):
        if column_lower not in list(genetic_df.columns):
            return (True, fn.alert_danger(Markup(f"ERROR Column <b>{column}</b> is missing")), {}, {})

    # check if WA code are missing
    if genetic_df["wa code"].isnull().any():
        return (True, fn.alert_danger(Markup(f"{genetic_df['wa code'].isnull().sum()} WA code missing")), {}, {})

    # check if WA code duplicated in spreadsheet
    if genetic_df["wa code"].duplicated().any():
        si = genetic_df["wa code"]
        return (
            True,
            fn.alert_danger(
                Markup(f"Some tissue_id are duplicated: <pre> {genetic_df[si.isin(si[si.duplicated()])].sort_values('wa code')}</pre>")
            ),
            {},
            {},
        )

    # loci list
    with fn.conn_alchemy().connect() as con:
        rows = con.execute(
            text(
                "(SELECT CONCAT(name, '_a') AS n, position FROM loci WHERE name != 'SRY' UNION SELECT CONCAT(name, '_b') AS n, position FROM loci WHERE name != 'SRY') ORDER BY position, n "
            ),
        ).all()
        loci_list: list = [row[0] for row in rows]

    index = 0
    wa_results = {}
    wa_loci = {}
    for idx, row in genetic_df.iterrows():
        data: dict = {}

        data["wa_code"] = row["wa code"].strip()
        data["pack"] = row["pack"].strip() if not pd.isna(row["pack"]) else None
        data["notes"] = row["note"].strip() if not pd.isna(row["note"]) else None
        data["genotype_id"] = row["genotype id"].strip() if not pd.isna(row["genotype id"]) else None
        data["mtdna"] = row["mtdna"].strip() if not pd.isna(row["mtdna"]) else None
        data["sex_id"] = row["sex id"].strip() if not pd.isna(row["sex id"]) else None
        data["individual_id"] = row["other id"].strip() if not pd.isna(row["other id"]) else None

        # constraint on quality_genotype
        if pd.isna(row["quality_genotype"]):
            quality_genotype = "Yes"
        else:
            if row["quality_genotype"].upper() == "POOR DNA":
                quality_genotype = "Poor DNA"
            elif not pd.isna(row["mtdna"]) and row["mtdna"].upper() == "POOR DNA":
                quality_genotype = "Poor DNA"
            else:
                quality_genotype = row["quality_genotype"].capitalize()
        data["quality_genotype"] = quality_genotype

        wa_results[index] = dict(data)

        data: dict = {}
        data["wa_code"] = row["wa code"].strip()

        for locus, locus_lower in zip(loci_list, [x.lower() for x in loci_list]):
            if pd.isna(row[locus_lower]):
                return True, fn.alert_danger(Markup(f"{locus} for {row['wa code']} has a NaN value")), {}, {}
            data[locus] = str(row[locus_lower])

        wa_loci[index] = dict(data)

        index += 1

    return False, "", wa_results, wa_loci
