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

# mode = sys.argv[2]  # INSERT / UPDATE

if Path(filename).suffix.upper() == ".XLSX":
    engine = "openpyxl"
if Path(filename).suffix.upper() == ".ODS":
    engine = "odf"


'''
if len(sys.argv) == 3:
    box_number = int(sys.argv[3])
else:
    box_number = "NULL"
'''


out: str = ""

scats_df = pd.read_excel(filename, sheet_name=0, engine=engine)

required_columns = [
    "scat_id",
    "date",
    "wa_code",
    "genotype_id",
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
    "box_number"
]

# check columns
for column in required_columns:
    if column not in list(scats_df.columns):
        print(f"ERROR Column {column} is missing", file=sys.stderr)
        sys.exit()

columns_list = list(scats_df.columns)


# check if scat id are missing
if scats_df["scat_id"].isnull().any():
    print(f'{scats_df["scat_id"].isnull().sum()} scat id missing', file=sys.stderr)
    sys.exit()

# check if date are missing
if scats_df["date"].isnull().any():
    print(f'{scats_df["date"].isnull().sum()} date missing', file=sys.stderr)
    sys.exit()


# check if sampling type are missing
if scats_df["sampling_type"].isnull().any():
    print(f'{scats_df["sampling_type"].isnull().sum()} sampling type missing', file=sys.stderr)

# check if coordinates are missing
if scats_df["coord_east"].isnull().any() or scats_df["coord_north"].isnull().any():
    print("coordinates missing", file=sys.stderr)

# check if scat_id duplicated
if scats_df["scat_id"].duplicated().any():
    print("scat id duplicated", file=sys.stderr)
    si = scats_df["scat_id"]
    print(scats_df[si.isin(si[si.duplicated()])].sort_values("scat_id"), file=sys.stderr)

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

'''
# TEST end
if mode != "UPDATE":
    print("exiting...")
    sys.exit()
'''


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

    data["coord_zone"] = "32N"

    # check if coordinates are OK
    try:
        _ = utm.to_latlon(int(data["coord_east"]), int(data["coord_north"]), 32, "N")
    except Exception:
        print(f'ERROR on {row["scat_id"]} for coordinates {data["coord_east"]= }   {data["coord_north"]=}', file=sys.stderr)
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

    # deposition
    data["deposition"] = str(data["deposition"]).capitalize().strip()
    if data["deposition"] == "Fresca":
        data["deposition"] = "Fresh"
    if data["deposition"] == "Vecchia":
        data["deposition"] = "Old"
    if data["deposition"] not in ["Fresh", "Old", ""]:
        out += f'The deposition value must be <b>Fresh</b>, <b>Old</b> or empty at row {index + 2}: found {data["deposition"]}'

    # matrix
    data["matrix"] = str(data["matrix"]).capitalize().strip()
    if data["matrix"] in ["Si", "Sì"]:
        data["matrix"] = "Yes"
    if data["matrix"] == "No":
        data["matrix"] = "No"
    if data["matrix"] not in ["Yes", "No", ""]:
        out += f'The matrix value must be <b>Yes</b> or <b>No</b> or empty at row {index + 2}: found {data["matrix"]}'

    # collected_scat
    data["collected_scat"] = str(data["collected_scat"]).capitalize().strip()
    if data["collected_scat"] in ["Si", "Sì"]:
        data["collected_scat"] = "Yes"
    if data["collected_scat"] == "No":
        data["collected_scat"] = "No"
    if data["collected_scat"] not in ["Yes", "No", ""]:
        out += f'The collected_scat value must be <b>Yes</b> or <b>No</b> or empty at row {index + 2}: found {data["collected_scat"]}'

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

    if data["scat_id"] in found_scat_list:
        # retrieve fields
        with conn_alchemy().connect() as con:
            scat = con.execute(text("SELECT * FROM scats WHERE scat_id = :scat_id "), {"scat_id": data["scat_id"]}).mappings().fetchone()
        
        update_list = []
        output = []
        for key in scat:
            #if (scat[key] is None or scat[key] == "") and (str(data.get(key, "nan")) not in ("nan", "")):
            
            db_val = scat[key] if scat[key] is not None else ''
            if key in required_columns and str(db_val) != str(data[key]):
                output.append([key,db_val,data[key]])
                #print(f"field '{key}'  current value: '{db_val}'   new value: '{data[key]}'")
                update_list.append(f" {key} = {quote(data[key])} ")

        if update_list:
            print(f"\nScat already in database: {scat["scat_id"]}")
            print(tabulate.tabulate(output, ['field', 'current value', 'new value'], tablefmt="pretty"))


            #print(",".join(update_list))
            print()
            print()

        print((f"""UPDATE scats SET {','.join(update_list)} WHERE scat_id = '{data["scat_id"]}';"""), file=f_out)

    else:
        print(
            (
                "INSERT INTO scats (scat_id, date, wa_code, sampling_season, sampling_type, location, "
                "municipality, province, region, deposition, matrix, collected_scat, genetic_sample, scalp_category, "
                "coord_east, coord_north, coord_zone, "
                "observer, institution, "
                "notes, box_number, geometry_utm"
                ") VALUES ("
                f"""'{data["scat_id"]}',"""
                f"""'{data["date"]}',"""
                f"""'{data["wa_code"]}',"""
                f"""'{sampling_season(data["date"])}',"""
                f"{quote(data['sampling_type'])}, "
                f"{quote(data['location'])}, "
                f"{quote(data['municipality'])}, "
                f"{quote(data['province'])}, "
                f"""(SELECT region FROM geo_info WHERE province_code='{data["province"]}'),"""
                f"{quote(data['deposition'])}, "
                f"{quote(data['matrix'])}, "
                f"{quote(data['collected_scat'])}, "
                f"{quote(data['genetic_sample'])}, "
                f"{quote(data['scalp_category'])}, "
                f"{data['coord_east']}, "
                f"{data['coord_north']}, "
                f"'{data['coord_zone']}', "
                f"{quote(data['operator'])}, "
                f"{quote(data['institution'])}, "
                f"{quote(data['notes'])}, "
                f"{data['box_number']}, "
                f"'SRID=32632;POINT({data['coord_east']} {data['coord_north']})'"
                ");"
            ),
            file=f_out,
        )

print("SET session_replication_role = DEFAULT;", file=f_out)
print("CALL refresh_materialized_views();", file=f_out)

f_out.close()
