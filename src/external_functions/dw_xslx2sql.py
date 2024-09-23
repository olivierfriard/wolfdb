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
mode = sys.argv[2]  # INSERT / UPDATE

if Path(filename).suffix.upper() == ".XLSX":
    engine = "openpyxl"
if Path(filename).suffix.upper() == ".ODS":
    engine = "odf"


if len(sys.argv) == 4:
    box_number = int(sys.argv[3])
else:
    box_number = "NULL"

out: str = ""

dw_df = pd.read_excel(filename, sheet_name=0, engine=engine)
print(dw_df.columns)

# check columns
for column in (
    "tissue_id",
    "date",
    "wa_code",
    "genotype_id",
    "sampling_type",
    "location",
    "municipality",
    "province",
    "coord_east",
    "coord_north",
    "coord_zone",
    "operator",
    "institution",
    "notes",
):
    if column not in list(dw_df.columns):
        print(f"ERROR Column {column} is missing", file=sys.stderr)
        sys.exit()

columns_list = list(dw_df.columns)


# check if tissue_id are missing
if dw_df["tissue_id"].isnull().any():
    print(f'{dw_df["tissue_id"].isnull().sum()} scat id missing', file=sys.stderr)
    sys.exit()

# check if date are missing
if dw_df["date"].isnull().any():
    print(f'{dw_df["date"].isnull().sum()} date missing', file=sys.stderr)
    sys.exit()

# check if sampling type are missing
if dw_df["sampling_type"].isnull().any():
    print(f'{dw_df["sampling_type"].isnull().sum()} sampling type missing', file=sys.stderr)

# check if coordinates are missing
if dw_df["coord_east"].isnull().any() or dw_df["coord_north"].isnull().any():
    print("coordinates missing", file=sys.stderr)

# check if tissue_id duplicated
if dw_df["tissue_id"].duplicated().any():
    print("tissue_id duplicated", file=sys.stderr)
    si = dw_df["tissue_id"]
    print(dw_df[si.isin(si[si.duplicated()])].sort_values("tissue_id"), file=sys.stderr)

# check if SCALP category != C1
if "scalp_category" in dw_df.columns:
    for scalp in dw_df["scalp_category"]:
        if scalp != "C1":
            print(f"SCALP category is {scalp} (should be C1)", file=sys.stderr)

# check if tissue_id is not already present in DB
with conn_alchemy().connect() as con:
    results = con.execute(text("SELECT tissue_id FROM dead_wolves")).mappings().all()
    tissue_id_list = [x["tissue_id"] for x in results]
    found_tissue_id_list: list = []
    for tissue_id in dw_df["tissue_id"]:
        if tissue_id in tissue_id_list:
            found_tissue_id_list.append(tissue_id)

    if found_tissue_id_list:
        for tissue_id in found_tissue_id_list:
            print(f"tissue_id {tissue_id} is already in wolfDB", file=sys.stderr)
        print(f"Total number: {len(found_tissue_id_list)} tissue(s).\n", file=sys.stderr)


# check if genotype id already present in DB (must be)
with conn_alchemy().connect() as con:
    results = con.execute(text("SELECT genotype_id FROM genotypes")).mappings().all()
    genotype_id_list = [x["genotype_id"] for x in results]
    # print(genotype_id_list)
    flag_not_found = False
    for genotype_id in dw_df["genotype_id"]:
        if str(genotype_id) == "nan":
            continue
        if genotype_id.strip() not in genotype_id_list:
            print(f"Genotype ID #{genotype_id.strip()}# not found in wolfDB", file=sys.stderr)
            flag_not_found = True


# check date
for idx, date in enumerate(dw_df["date"]):
    if isinstance(date, dt.datetime):
        date = date.strftime("%Y-%m-%d")
    try:
        dt.datetime.strptime(date, "%Y-%m-%d")
    except Exception:
        print(f"{date} is not a date at row {idx+1}", file=sys.stderr)

# check province code
for idx, province in enumerate(dw_df["province"]):
    if isinstance(province, int):
        province = f"{province:02}"
    if province not in italian_regions.province_codes:
        print(f"Province {province} not found {idx}", file=sys.stderr)


# TEST end
if mode != "UPDATE":
    print("exiting...")
    sys.exit()

# create output file
output_dir = Path(filename).parent / Path(filename).stem
output_dir.mkdir(parents=True, exist_ok=True)
f_out = open(output_dir / "tissues.sql", "w")

print("SET session_replication_role = replica;", file=f_out)

index = 0
for _, row in dw_df.iterrows():
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

    data["coord_zone"] = "32N"

    # check if coordinates are OK
    try:
        _ = utm.to_latlon(int(data["coord_east"]), int(data["coord_north"]), 32, "N")
    except Exception:
        print(f'ERROR on {row["tissue_id"]} for coordinates {data["coord_east"]= }   {data["coord_north"]=}', file=sys.stderr)
        # sys.exit()

    data["geometry_utm"] = f"SRID=32632;POINT({data['coord_east']} {data['coord_north']})"

    # sampling_type
    data["sampling_type"] = str(data["sampling_type"]).capitalize().strip()
    if data["sampling_type"] not in ["Opportunistic", "Systematic", ""]:
        print(
            f'Row {index + 2}: Sampling type must be <b>Opportunistic</b>, <b>Systematic</b> or empty: found {data["sampling_type"]}',
            file=sys.stderr,
        )
        sys.exit()

    # no path ID if scat is opportunistc
    if data["sampling_type"] == "Opportunistic":
        data["path_id"] = ""

    # scalp_category
    data["scalp_category"] = str(data["scalp_category"]).capitalize().strip()
    if data["scalp_category"] not in ("C1", "C2", "C3", "C4", ""):
        out += f'The scalp category value must be <b>C1, C2, C3, C4</b> or empty at row {index + 2}: found {data["scalp_category"]}'

    # genetic_sample
    data["genetic_sample"] = str(data["genetic_sample"]).capitalize().strip()
    if data["genetic_sample"] in ("Si", "Sì"):
        data["genetic_sample"] = "Yes"
    if data["genetic_sample"] == "No":
        data["genetic_sample"] = "No"
    if data["genetic_sample"] not in ["Yes", "No", ""]:
        out += f'The genetic_sample value must be <b>Yes</b>, <b>No</b> or empty at row {index + 2}: found {data["genetic_sample"]}'

    # notes
    data["notes"] = str(data["notes"]).strip()

    data["operator"] = str(data["operator"]).strip()
    data["institution"] = str(data["institution"]).strip()

    index += 1

    if data["tissue_id"] in found_tissue_id_list:
        # retrieve fields
        with conn_alchemy().connect() as con:
            tissue = (
                con.execute(text("SELECT * FROM dead_wolves WHERE tissue_id = :tissue_id "), {"tissue_id": data["tissue_id"]})
                .mappings()
                .fetchone()
            )
        print(f"{tissue["tissue_id"]=}")
        update_list = []
        for key in tissue:
            if (tissue[key] is None or tissue[key] == "") and (str(data.get(key, "nan")) not in ("nan", "")):
                print(f"{key=}  {data[key]=}")
                update_list.append(f" {key} = {quote(data[key])} ")

        # print(",".join(update_list))
        # print("-" * 80)
        if update_list:
            print((f"""UPDATE dead_wolves SET {','.join(update_list)} WHERE tissue_id = '{data["tissue_id"]}';"""), file=f_out)

    else:
        print(
            (
                "INSERT INTO dead_wolves (tissue_id, genotype_id, discovery_date, wa_code, "
                "location, municipality, province, region, "
                "utm_east, utm_north, utm_zone, "
                "geometry_utm"
                ") VALUES ("
                f"""'{data["tissue_id"]}',"""
                f"""'{data["genotype_id"]}',"""
                f"""'{data["date"]}',"""
                f"""'{data["wa_code"]}',"""
                f"{quote(data['location'])}, "
                f"{quote(data['municipality'])}, "
                f"{quote(data['province'])}, "
                f"""(SELECT region FROM geo_info WHERE province_code='{data["province"]}'),"""
                f"{data['coord_east']}, "
                f"{data['coord_north']}, "
                f"'{data['coord_zone']}', "
                f"'SRID=32632;POINT({data['coord_east']} {data['coord_north']})'"
                ");"
            ),
            file=f_out,
        )

        # field not in dead_wolves
        # data collector (#88, operator)
        if quote(data["operator"]):
            print(
                f"INSERT INTO dead_wolves_values (id, field_id, val) VALUES ((SELECT MAX(id) FROM dead_wolves), 88, {quote(data['operator'])});",
                file=f_out,
            )

        # sampling season #10
        if data["date"]:
            print(
                f"INSERT INTO dead_wolves_values (id, field_id, val) VALUES ((SELECT MAX(id) FROM dead_wolves), 10, '{sampling_season(data["date"])}');",
                file=f_out,
            )

        # generic notes #220
        if data["notes"]:
            print(
                f"INSERT INTO dead_wolves_values (id, field_id, val) VALUES ((SELECT MAX(id) FROM dead_wolves), 220, {quote(data['notes'])});",
                file=f_out,
            )

        # SCALP category #230
        print(
            "INSERT INTO dead_wolves_values (id, field_id, val) VALUES ((SELECT MAX(id) FROM dead_wolves), 230, 'C1');",
            file=f_out,
        )


print("SET session_replication_role = DEFAULT;", file=f_out)
print("CALL refresh_materialized_views();", file=f_out)

f_out.close()
