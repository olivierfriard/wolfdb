"""
import wa code from a spreadsheet file (XLSX/ODS) in the wolfDB
"""

import sys
import datetime as dt
from pathlib import Path
import pandas as pd
import utm
from sqlalchemy import create_engine
from sqlalchemy import text
from psycopg import sql
import tabulate
import italian_regions


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
    if not isinstance(s, str):
        return s
    if s == "":
        return "NULL"
    try:
        if "'" in s:
            return f"""'{s.strip().replace("'", "''")}'"""
        else:
            return f"'{s.strip()}'"
    except Exception:
        print(f"ERROR on {s}")


filename = sys.argv[1]

if Path(filename).suffix.upper() == ".XLSX":
    engine = "openpyxl"
if Path(filename).suffix.upper() == ".ODS":
    engine = "odf"


out: str = ""

scats_df = pd.read_excel(filename, sheet_name=0, engine=engine)

required_columns = [
    "scat_id",
    "date",
    "wa_code",
    # "genotype_id",
    "sampling_type",
    "transect_id",
    "snowtrack_id",
    "location",
    "municipality",
    "province",
    "deposition",
    "matrix",
    "collected_scat",
    "scalp_category",
    "genetic_sample",
    "coord_east",
    "coord_north",
    "coord_zone",
    "operator",
    "institution",
    "notes",
    "box_number",
]

# check columns
for column in required_columns:
    if column not in list(scats_df.columns):
        print(f"ERROR Column {column} is missing", file=sys.stderr)
        sys.exit()

columns_list = list(scats_df.columns)


# check if scat id are missing
if scats_df["scat_id"].isnull().any():
    print(f"{scats_df['scat_id'].isnull().sum()} scat id missing", file=sys.stderr)
    sys.exit()

# check if date are missing
if scats_df["date"].isnull().any():
    print(f"{scats_df['date'].isnull().sum()} date missing", file=sys.stderr)
    sys.exit()


# check if sampling type are missing
if scats_df["sampling_type"].isnull().any():
    print(f"{scats_df['sampling_type'].isnull().sum()} sampling type missing", file=sys.stderr)

# check if coordinates are missing
if scats_df["coord_east"].isnull().any() or scats_df["coord_north"].isnull().any():
    print("coordinates missing", file=sys.stderr)

# check if scat_id duplicated
if scats_df["scat_id"].duplicated().any():
    print("scat id duplicated", file=sys.stderr)
    si = scats_df["scat_id"]
    print(scats_df[si.isin(si[si.duplicated()])].sort_values("scat_id")["scat_id"], file=sys.stderr)

# check if scat id is not already present in DB
with conn_alchemy().connect() as con:
    results = con.execute(text("SELECT scat_id FROM scats")).mappings().all()
    scat_id_list = [x["scat_id"] for x in results]
    found_scat_list: list = []
    for scat_id in scats_df["scat_id"]:
        if scat_id in scat_id_list:
            found_scat_list.append(scat_id)

    if found_scat_list:
        for scat_id in found_scat_list:
            print(f"Scat id {scat_id} is already in wolfDB", file=sys.stderr)
        print(f"Total number: {len(found_scat_list)} scat(s).\n", file=sys.stderr)


# check if genotype id already present in DB (must be)
"""
with conn_alchemy().connect() as con:
    results = con.execute(text("SELECT genotype_id FROM genotypes")).mappings().all()
    genotype_id_list = [x["genotype_id"] for x in results]
    # print(genotype_id_list)
    flag_not_found = False
    for genotype_id in scats_df["genotype_id"]:
        if str(genotype_id) == "nan":
            continue
        if genotype_id.strip() not in genotype_id_list:
            print(f"Genotype ID #{genotype_id.strip()}# not found in wolfDB", file=sys.stderr)
            flag_not_found = True
"""

# check date
for idx, date in enumerate(scats_df["date"]):
    if isinstance(date, dt.datetime):
        date = date.strftime("%Y-%m-%d")
    try:
        dt.datetime.strptime(date, "%Y-%m-%d")
    except Exception:
        print(f"'{date}' is not a valid date at row {idx + 2} (check date format)", file=sys.stderr)

# check province code
for idx, province in enumerate(scats_df["province"]):
    if isinstance(province, int):
        province = f"{province:02}"
    if province not in italian_regions.province_codes:
        print(f"Province '{province}' not found at row {idx + 2}", file=sys.stderr)


# create output file
output_dir = Path(filename).parent / Path(filename).stem
output_dir.mkdir(parents=True, exist_ok=True)
f_out = open(output_dir / "scats.sql", "w")

print("SET session_replication_role = replica;", file=f_out)

index = 0
for _, row in scats_df.iterrows():
    data: dict = {}

    for column in columns_list:
        if column == "province" and isinstance(row[column], int):
            data[column] = f"{row[column]:02}"
        else:
            data[column] = row[column]
        if isinstance(data[column], float) and str(data[column]) == "nan":
            data[column] = ""

    # remove time if any
    if " " in str(data["date"]):
        data["date"] = str(data["date"]).split(" ")[0]

    # data["genotype_id"] = data["genotype_id"].split(" ")[0]

    # path_id
    data["path_id"] = row["transect_id"]

    if len(row["coord_zone"].strip()) != 3:
        print(f"ERROR on coordonates zone {row['coord_zone']}. Must be 3 characters", file=sys.stderr)
        sys.exit()

    if row["coord_zone"].strip()[-1].upper() not in ("N", "S"):
        print(f"ERROR on coordinates zone {row['coord_zone']}. Must end with N or S", file=sys.stderr)
        sys.exit()

    data["coord_zone"] = row["coord_zone"].strip()

    # check box number
    if not isinstance(row["box_number"], float):
        print(
            f"ERROR on box number {row['box_number']}. Must be an integer",
            file=sys.stderr,
        )
        sys.exit()
    else:
        if str(row["box_number"]).upper() == "NAN":
            data["box_number"] = None
        else:
            data["box_number"] = int(row["box_number"])

    # check if coordinates are OK
    try:
        hemisphere = row["coord_zone"][-1].upper()
        zone = int(row["coord_zone"][:2])
        _ = utm.to_latlon(int(data["coord_east"]), int(data["coord_north"]), zone, hemisphere)
    except Exception:
        print(
            f"ERROR on {row['scat_id']} for coordinates {data["coord_east"]= }   {data["coord_north"]=}  {data["coord_zone"]=}",
            file=sys.stderr,
        )

    srid = zone + (32600 if hemisphere == "N" else 32700)

    data["geometry_utm"] = f"SRID={srid};POINT({data['coord_east']} {data['coord_north']})"

    # sampling_type
    data["sampling_type"] = str(data["sampling_type"]).capitalize().strip()
    if data["sampling_type"] not in ["Opportunistic", "Systematic", ""]:
        print(
            f"Row {index + 2}: Sampling type must be <b>Opportunistic</b>, <b>Systematic</b> or empty: found {data['sampling_type']}",
            file=sys.stderr,
        )
        sys.exit()

    # check if sample_type column is present
    if "sample_type" in row:
        if not isinstance(row["sample_type"], float):
            data["sample_type"] = row["sample_type"]
        else:
            data["sample_type"] = None
    else:
        data["sample_type"] = None

    # no path ID if scat is opportunistc
    if data["sampling_type"] == "Opportunistic":
        data["path_id"] = ""

    # deposition
    data["deposition"] = str(data["deposition"]).capitalize().strip()
    if data["deposition"] == "Fresca":
        data["deposition"] = "Fresh"
    if data["deposition"] == "Vecchia":
        data["deposition"] = "Old"
    if data["deposition"] not in ["Fresh", "Old", ""]:
        out += f"The deposition value must be <b>Fresh</b>, <b>Old</b> or empty at row {index + 2}: found {data['deposition']}"

    # matrix
    data["matrix"] = str(data["matrix"]).capitalize().strip()
    if data["matrix"] in ["Si", "Sì"]:
        data["matrix"] = "Yes"
    if data["matrix"] == "No":
        data["matrix"] = "No"
    if data["matrix"] not in ["Yes", "No", ""]:
        out += f"The matrix value must be <b>Yes</b> or <b>No</b> or empty at row {index + 2}: found {data['matrix']}"

    # collected_scat
    data["collected_scat"] = str(data["collected_scat"]).capitalize().strip()
    if data["collected_scat"] in ["Si", "Sì"]:
        data["collected_scat"] = "Yes"
    if data["collected_scat"] == "No":
        data["collected_scat"] = "No"
    if data["collected_scat"] not in ["Yes", "No", ""]:
        out += f"The collected_scat value must be <b>Yes</b> or <b>No</b> or empty at row {index + 2}: found {data['collected_scat']}"

    # scalp_category
    data["scalp_category"] = str(data["scalp_category"]).capitalize().strip()
    if data["scalp_category"] not in ("C1", "C2", "C3", "C4", ""):
        out += f"The scalp category value must be <b>C1, C2, C3, C4</b> or empty at row {index + 2}: found {data['scalp_category']}"

    # genetic_sample
    data["genetic_sample"] = str(data["genetic_sample"]).capitalize().strip()
    if data["genetic_sample"] in ("Si", "Sì"):
        data["genetic_sample"] = "Yes"
    if data["genetic_sample"] == "No":
        data["genetic_sample"] = "No"
    if data["genetic_sample"] not in ["Yes", "No", ""]:
        out += f"The genetic_sample value must be <b>Yes</b>, <b>No</b> or empty at row {index + 2}: found {data['genetic_sample']}"

    # notes
    data["notes"] = str(data["notes"]).strip()

    data["operator"] = str(data["operator"]).strip()
    data["institution"] = str(data["institution"]).strip()

    index += 1

    if data["scat_id"] in found_scat_list:
        # retrieve fields
        with conn_alchemy().connect() as con:
            scat = con.execute(text("SELECT * FROM scats WHERE scat_id = :scat_id "), {"scat_id": data["scat_id"]}).mappings().fetchone()

        update_list = []
        output = []
        for key in scat:
            db_val = scat[key] if scat[key] is not None else ""
            if key in required_columns and str(db_val) != str(data[key]):
                output.append([key, db_val, data[key]])
                # print(f"field '{key}'  current value: '{db_val}'   new value: '{data[key]}'")
                update_list.append(f" {key} = {quote(data[key])} ")

        if update_list:
            print(f"\nScat already in database: {scat['scat_id']}")
            print(tabulate.tabulate(output, ["field", "current value", "new value"], tablefmt="pretty"))

            # print(",".join(update_list))
            print()
            print()

        print((f"""UPDATE scats SET {",".join(update_list)} WHERE scat_id = '{data["scat_id"]}';"""), file=f_out)

    else:
        query = sql.SQL(
            (
                "INSERT INTO scats (scat_id, date, wa_code, sampling_season, sampling_type, location, "
                "municipality, province, region, deposition, matrix, collected_scat, genetic_sample, scalp_category, "
                "coord_east, coord_north, coord_zone, "
                "observer, institution, "
                "notes, box_number, geometry_utm, sample_type"
                ") VALUES ("
                "{},"
                "{},"
                "{},"
                "{},"
                "{},"
                "{},"
                "{},"
                "{},"
                "(SELECT region FROM geo_info WHERE province_code={}),"
                "{},"
                "{},"
                "{},"
                "{},"
                "{},"
                "{},"
                "{},"
                "{},"
                "{},"
                "{},"
                "{},"
                "{},"
                "'SRID={};POINT({} {})',"
                "{}"
                ");"
            )
        ).format(
            sql.Literal(data["scat_id"]),
            sql.Literal(data["date"]),
            sql.Literal(data["wa_code"]),
            sql.Literal(sampling_season(data["date"])),
            sql.Literal(data["sampling_type"]),
            sql.Literal(data["location"]),
            sql.Literal(data["municipality"]),
            sql.Literal(data["province"]),
            sql.Literal(data["province"]),
            sql.Literal(data["deposition"]),
            sql.Literal(data["matrix"]),
            sql.Literal(data["collected_scat"]),
            sql.Literal(data["genetic_sample"]),
            sql.Literal(data["scalp_category"]),
            sql.Literal(data["coord_east"]),
            sql.Literal(data["coord_north"]),
            sql.Literal(data["coord_zone"]),
            sql.Literal(data["operator"]),
            sql.Literal(data["institution"]),
            sql.Literal(data["notes"]),
            sql.Literal(data["box_number"]),
            sql.Literal(zone + (32600 if hemisphere == "N" else 32700)),
            sql.Literal(data["coord_east"]),
            sql.Literal(data["coord_north"]),
            sql.Literal(data["sample_type"]),
        )

        print(query.as_string(), file=f_out)

print("SET session_replication_role = DEFAULT;", file=f_out)
print("CALL refresh_materialized_views();", file=f_out)

f_out.close()
