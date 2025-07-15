"""
import wa genetic data from XLSX file
"""

import sys
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy import text


def conn_alchemy():
    with open(Path.home() / ".pgpass", "r") as f_in:
        for line in f_in:
            if "localhost:5432:wolf:" in line:
                host, port, database, user, password = line.strip().split(":")
                break

    return create_engine(
        f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}",
        isolation_level="AUTOCOMMIT",
    )


def sampling_season(date: str) -> str:
    """
    Extract sampling season from date in ISO 8601 format
    """
    try:
        month = int(date[5 : 6 + 1])
        year = int(date[0 : 3 + 1])
        if 5 <= month <= 12:
            return f"{year}-{year + 1}"
        if 1 <= month <= 4:
            return f"{year - 1}-{year}"
    except Exception:
        return f"Error {date}"


def quote(s):
    if "'" in s:
        return f"""'{s.strip().replace("'", "''")}'"""
    else:
        return f"'{s.strip()}'"


# read arguments
filename = sys.argv[1]

"""
# disabled because record status is included in the spreadsheet
if RECORD_STATUS not in ("OK", "temp"):
    print("record_status must be OK or temp")
    sys.exit()
"""

if Path(filename).suffix.upper() == ".XLSX":
    engine = "openpyxl"
elif Path(filename).suffix.upper() == ".ODS":
    engine = "odf"
else:
    print("error on input file")
    sys.exit()

genetic_df = pd.read_excel(filename, sheet_name=0, engine=engine)  # .convert_dtypes()

new_columns = []
for column in genetic_df.columns:
    if column.endswith("_a") or column.endswith("_b"):
        new_columns.append(column.upper().replace("_A", "_a").replace("_B", "_b"))
    else:
        new_columns.append(column)

genetic_df.columns = new_columns

# print(genetic_df.columns)

loci_list = [
    "CPH5_a",
    "CPH5_b",
    "U250_a",
    "U250_b",
    "FH2088_a",
    "FH2088_b",
    "FH2096_a",
    "FH2096_b",
    "FH2137_a",
    "FH2137_b",
    "FH2054_a",
    "FH2054_b",
    "FH2140_a",
    "FH2140_b",
    "FH2161_a",
    "FH2161_b",
    "PEZ17_a",
    "PEZ17_b",
    "CPH2_a",
    "CPH2_b",
    "CPH4_a",
    "CPH4_b",
    "CPH8_a",
    "CPH8_b",
    "CPH12_a",
    "CPH12_b",
    "U253_a",
    "U253_b",
    "FH2004_a",
    "FH2004_b",
    "FH2079_a",
    "FH2079_b",
    "MSY34A_a",
    "MSY34A_b",
    "MSY34B_a",
    "MSY34B_b",
    "MSY41A_a",
    "MSY41A_b",
    "MSY41B_a",
    "MSY41B_b",
    "K-LOCUS_a",
    "K-LOCUS_b",
    # "SRY",
]

columns_names = [
    "WA code",
    "mtDNA",
    "quality_genotype",
    "Other ID",
    "Genotype ID",
    "record_status",
    "Sex ID",
    "Pack",
    "Note",
]

# check columns
for column in columns_names + loci_list:
    if column not in [x for x in genetic_df.columns]:
        print(f"ERROR Column {column} is missing from {genetic_df.columns}")
        sys.exit()

columns_list = list(genetic_df.columns)

# check if wa code is already present in DB
not_found_wa = []
with conn_alchemy().connect() as con:
    results = con.execute(text("SELECT wa_code FROM scats")).mappings().all()
    wa_code_list = [x["wa_code"] for x in results]
    flag_not_found = False
    for wa_code in genetic_df["WA code"]:
        if str(wa_code) == "nan":
            continue

        if wa_code not in wa_code_list:
            not_found_wa.append(wa_code)

    if not_found_wa:
        for wa_code in not_found_wa:
            print(f"New WA code: {wa_code}", file=sys.stderr)


# check if genotype id already present in DB (must be)
with conn_alchemy().connect() as con:
    results = con.execute(text("SELECT genotype_id FROM genotypes")).mappings().all()
    genotype_id_list = [x["genotype_id"] for x in results]
    # print(genotype_id_list)
    not_found_genotypes: list = []
    for genotype_id in genetic_df["Genotype ID"]:
        if str(genotype_id) == "nan":
            continue
        if genotype_id.strip() not in genotype_id_list:
            not_found_genotypes.append(genotype_id.strip())

    if not_found_genotypes:
        for genotype_id in not_found_genotypes:
            print(f"New genotype: {genotype_id}", file=sys.stderr)


# create output files
output_dir = Path(filename).parent / Path(filename).stem
output_dir.mkdir(parents=True, exist_ok=True)

f_genotype = open(output_dir / "genotypes.sql", "w")
f_genotype_loci = open(output_dir / "genotypes-loci.sql", "w")
f_wa_results = open(output_dir / "wa-results.sql", "w")
f_wa_loci = open(output_dir / "wa-loci.sql", "w")

for handle in (f_genotype, f_genotype_loci, f_wa_results, f_wa_loci):
    print("SET session_replication_role = replica;", file=handle)


index = 0
for idx, row in genetic_df.iterrows():
    # check if wa code
    if genetic_df["WA code"].isnull().values[idx]:
        continue

    # constraint on quality_genotype
    quality_genotype = str(row["quality_genotype"])
    if quality_genotype == "nan":
        quality_genotype = "'Yes'"
    else:
        if quality_genotype.upper() == "POOR DNA":
            quality_genotype = quote("Poor DNA")
        elif str(row["mtDNA"]).upper() == "POOR DNA":
            quality_genotype = quote("Poor DNA")
        else:
            quality_genotype = quote(quality_genotype.capitalize())

    # print(f"{quality_genotype=}", file=sys.stderr)

    # insert into wa_results
    print(
        (
            "INSERT INTO wa_results (wa_code, mtdna, quality_genotype, genotype_id, sex_id, notes) VALUES ("
            f"{quote(str(row['WA code']))},"
            f"{quote(str(row['mtDNA']))},"
            f"{quality_genotype},"
            f"{quote(str(row['Genotype ID'] if row['Genotype ID'] == row['Genotype ID'] else ''))},"
            f"{quote(str(row['Sex ID'] if row['Sex ID'] == row['Sex ID'] else ''))},"
            f"{quote(str(row['Note'] if row['Note'] == row['Note'] else ''))}"
            ") "
            " ON CONFLICT (wa_code) "
            " DO UPDATE SET "
            "mtdna = EXCLUDED.mtdna,"
            "quality_genotype = EXCLUDED.quality_genotype,"
            "genotype_id = EXCLUDED.genotype_id,"
            "sex_id = EXCLUDED.sex_id,"
            "notes = EXCLUDED.notes;"
        ),
        file=f_wa_results,
    )

    # insert into genotypes
    if str(row["Genotype ID"]) != "nan":
        if str(row["Genotype ID"]) in not_found_genotypes:
            print(
                (
                    "INSERT INTO genotypes (genotype_id, pack, sex, mtdna, tmp_id, record_status, notes) VALUES ("
                    f"{quote(str(row['Genotype ID']))},"
                    f"{quote(str(row['Pack'])) if row['Pack'] == row['Pack'] else 'NULL'},"
                    f"{quote(str(row['Sex ID']))},"
                    f"{quote(str(row['mtDNA']))},"
                    f"{quote(str(row['Other ID'] if row['Other ID'] == row['Other ID'] else 'NULL'))},"
                    f"{quote(str(row['record_status']))},"
                    f"{quote(str(row['Note'])) if row['Note'] == row['Note'] else 'NULL'}"
                    "); "
                    # " ON CONFLICT (genotype_id) "
                    # " DO UPDATE SET "
                    # "pack = EXCLUDED.pack,"
                    # "sex = EXCLUDED.sex,"
                    # "mtdna = EXCLUDED.mtdna,"
                    # "tmp_id = EXCLUDED.tmp_id,"
                    # "notes = EXCLUDED.notes;"
                ),
                file=f_genotype,
            )
        else:  # genotype already in table
            print(file=sys.stderr)
            print(f"Genotype {str(row['Genotype ID'])} already in DB", file=sys.stderr)

    data: dict = {}

    for column in columns_list:
        data[column] = row[column]
        if isinstance(data[column], float) and str(data[column]) == "nan":
            data[column] = ""

    # print(data)

    for column in loci_list:
        data[column] = row[column]
        if isinstance(data[column], float) and str(data[column]) == "nan":
            data[column] = ""

    for column in loci_list:
        # DO NOT user and definitive columns !
        print(
            (
                f"INSERT INTO wa_locus (wa_code, locus, allele, val, timestamp) VALUES ("
                f"{quote(data['WA code'])}, "
                f"{quote(column.split('_')[0])}, "  # locus
                f"{quote(column.split('_')[1])}, "  # allele
                f"{data[column] if data[column] not in ('', '-') else 'NULL'}, "  # value
                "NOW()"
                ");"
            ),
            file=f_wa_loci,
        )

        if str(row["Genotype ID"]) != "nan":
            if str(row["Genotype ID"]) in not_found_genotypes:
                # DO NOT user and validated columns !
                print(
                    (
                        f"INSERT INTO genotype_locus (genotype_id, locus, allele, val, timestamp) VALUES ("
                        f"{quote(data['Genotype ID'])}, "
                        f"{quote(column.split('_')[0])}, "
                        f"{quote(column.split('_')[1])}, "
                        f"{data[column] if data[column] not in ('', '-') else 'NULL'}, "  # value
                        "NOW()"
                        ");"
                    ),
                    file=f_genotype_loci,
                )
            else:
                # check if genotype loci are the same
                with conn_alchemy().connect() as con:
                    genotype_loci = (
                        con.execute(
                            text(
                                "SELECT * FROM genotype_locus WHERE genotype_id = :genotype_id and allele = :allele and UPPER(locus) = :locus"
                            ),
                            {
                                "genotype_id": row["Genotype ID"].strip(),
                                "allele": column.split("_")[1],
                                "locus": column.split("_")[0].upper(),
                            },
                        )
                        .mappings()
                        .fetchone()
                    )
                    if genotype_loci is None:
                        print(
                            f"SELECT * FROM genotype_locus WHERE genotype_id = '{row['Genotype ID'].strip()}' and allele = '{column.split('_')[1]}' and UPPER(locus) = '{column.split('_')[0].upper()}'",
                            file=sys.stderr,
                        )

                    if (
                        genotype_loci["val"] != data[column]
                        and not (genotype_loci["val"] is None and data[column] == "-")
                        and (genotype_loci["val"] is not None)
                    ):
                        print(
                            (
                                f"{row['Genotype ID']} {genotype_loci['locus']} {genotype_loci['allele']}  "
                                f"db value: {genotype_loci['val']}  "
                                f"xlsx value: {data[column]} "
                                "ERROR"
                            ),
                            file=sys.stderr,
                        )

    index += 1

    # print(file=sys.stderr)

for handle in (f_genotype, f_genotype_loci, f_wa_results, f_wa_loci):
    print(
        "SET session_replication_role = DEFAULT;CALL refresh_materialized_views();",
        file=handle,
    )
    handle.close()
