"""
import scats from XLSX file
"""

from config import config
import functions as fn


import pathlib as pl
import pandas as pd
import datetime as dt
import utm
from sqlalchemy import text
from markupsafe import Markup

DEBUG = False
params = config()


def extract_data_from_xlsx(filename: str) -> (bool, str, dict, dict, dict):
    """
    Extract and check data from a XLSX file
    """

    if pl.Path(filename).suffix.upper() == ".XLSX":
        engine = "openpyxl"
    if pl.Path(filename).suffix.upper() == ".ODS":
        engine = "odf"

    out: str = ""

    try:
        scats_df = pd.read_excel(pl.Path(params["upload_folder"]) / pl.Path(filename), sheet_name=0, engine=engine)
    except Exception:
        if DEBUG:
            raise
        try:
            scats_df = pd.read_excel(filename, sheet_name=0, engine=engine)
        except Exception:
            return True, fn.alert_danger("Error reading the file. Check your XLSX/ODS file"), {}, {}, {}

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
            return True, fn.alert_danger(Markup(f"Column <b>{column}</b> is missing")), {}, {}, {}

    columns_list = list(scats_df.columns)

    # check if scat id are missing
    if scats_df["scat_id"].isnull().any():
        return True, fn.alert_danger(f"{scats_df['scat_id'].isnull().sum()} scat id missing"), {}, {}, {}

    # check if date are missing
    if scats_df["date"].isnull().any():
        return True, fn.alert_danger(f"{scats_df['date'].isnull().sum()} date missing"), {}, {}, {}

    # check if sampling type are missing
    """
    if scats_df["sampling_type"].isnull().any():
        return True, fn.alert_danger(f"{scats_df['sampling_type'].isnull().sum()} sampling type missing"), {}, {}, {}
    """

    # check if coordinates are missing
    if scats_df["coord_east"].isnull().any() or scats_df["coord_north"].isnull().any():
        return True, fn.alert_danger("coordinates missing"), {}, {}, {}

    # check if scat_id duplicated
    if scats_df["scat_id"].duplicated().any():
        si = scats_df["scat_id"]
        return (
            True,
            fn.alert_danger(
                Markup(f"Some scat_id are duplicated: <pre> {scats_df[si.isin(si[si.duplicated()])].sort_values('scat_id')}</pre>")
            ),
            {},
            {},
            {},
        )

    # check if scat id is not already present in DB
    """
    with fn.conn_alchemy().connect() as con:
        results = con.execute(text("SELECT scat_id FROM scats")).mappings().all()
        scat_id_list = [x["scat_id"] for x in results]
        found_scat_list: list = []
        for scat_id in scats_df["scat_id"]:
            if scat_id in scat_id_list:
                found_scat_list.append(scat_id)
    if found_scat_list:
        return True, fn.alert_danger(f"Scat id already in DB: {found_scat_list}"), {}, {}, {}
    """

    # check if genotype id already present in DB (should be)
    """
    with fn.conn_alchemy().connect() as con:
        results = con.execute(text("SELECT genotype_id FROM genotypes")).mappings().all()
        genotype_id_list = [x["genotype_id"] for x in results]
        not_found_genotypes: list = []
        for genotype_id in scats_df["genotype_id"]:
            if str(genotype_id) == "nan":
                continue
            if genotype_id.strip() not in genotype_id_list:
                not_found_genotypes.append(genotype_id.strip())

    if not_found_genotypes:
       return True, fn.alert_danger(f"Genotypes not found in DB: {not_found_genotypes}"), {}, {}, {}
    """

    # check date
    for idx, date in enumerate(scats_df["date"]):
        if isinstance(date, dt.datetime):
            date = date.strftime("%Y-%m-%d")
        try:
            dt.datetime.strptime(date, "%Y-%m-%d")
        except Exception:
            return True, fn.alert_danger(f"'{date}' is not a valid date at row {idx + 2} (check date format)"), {}, {}, {}

    # check province code
    for idx, province in enumerate(scats_df["province"]):
        if isinstance(province, int):
            province = f"{province:02}"
        if province not in fn.province_code_list():
            return True, fn.alert_danger(f"Province '{province}' not found at row {idx + 2}"), {}, {}, {}

    scats_data: dict = {}
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

        # date
        """
        try:
            year = int(row.scat_id[1 : 2 + 1]) + 2000
            month = int(row.scat_id[3 : 4 + 1])
            day = int(row.scat_id[5 : 6 + 1])
            date = f"{year}-{month:02}-{day:02}"

            try:
                dt.datetime.strptime(date, "%Y-%m-%d")
            except Exception:
                out += fn.alert_danger(
                    f"Row {index + 2}: the date ({date}) of the scat ID {row.scat_id} is not valid. Use the YYMMDD format"
                )
        except Exception:
            if DEBUG:
                raise
            out += fn.alert_danger(f"Row {index + 2}: The scat ID is not valid: {row.scat_id}")
        """

        # check date
        date = str(row["date"]).split(" ")[0].strip()
        data["date"] = date

        # path_id
        if str(row["transect_id"]) != "nan":
            path_id = fn.get_path_id(row["transect_id"], date)
            data["path_id"] = path_id
        else:
            data["path_id"] = None

        # check box number
        if not isinstance(row["box_number"], float):
            out += fn.alert_danger(Markup(f"Row {index + 2}: ERROR on box number <b>{row['box_number']}</b>. Must be an integer"))
        else:
            if str(row["box_number"]).upper() == "NAN":
                data["box_number"] = None
            else:
                data["box_number"] = int(row["box_number"])

        # add region from province code
        data["region"] = fn.province_code2region(data["province"])

        # UTM coord conversion
        # check zone
        data["coord_zone"] = data["coord_zone"].upper().strip()

        if len(data["coord_zone"]) != 3:
            out += fn.alert_danger(f"ERROR on coordinates zone {row['coord_zone']}. Must be 3 characters")

        hemisphere = data["coord_zone"][-1]
        if hemisphere not in ("S", "N"):
            out += fn.alert_danger(
                Markup(
                    f"Row {index + 2}: the hemisphere of the UTM zone <b>{data['coord_zone']}</b> is not correct. Must be <b>N</b> or <b>S</b>'"
                )
            )

        try:
            zone = int(row["coord_zone"][:2])
        except Exception:
            out += fn.alert_danger(Markup(f"Row {index + 2}: Check the UTM coordinates zone <b>{data['coord_zone']}</b>"))

        # check if coordinates are OK
        try:
            _ = utm.to_latlon(int(data["coord_east"]), int(data["coord_north"]), zone, hemisphere)
        except Exception:
            out += fn.alert_danger(
                f'Row {index + 2}: Check the UTM coordinates. East: "{data["coord_east"]}" North: "{data["coord_north"]} Zone: {data["coord_zone"]}"'
            )

        srid = zone + (32600 if hemisphere == "N" else 32700)
        data["geometry_utm"] = f"ST_GeomFromText('POINT({data['coord_east']} {data['coord_north']})', {srid})"

        # sampling_type
        data["sampling_type"] = str(data["sampling_type"]).capitalize().strip()
        if data["sampling_type"] == "" or isinstance(data["sampling_type"], float):
            data["sampling_type"] = None

        if data["sampling_type"] not in ["Opportunistic", "Systematic", None]:
            out += fn.alert_danger(
                Markup(
                    f"Row {index + 2}: Sampling type must be <b>Opportunistic</b>, <b>Systematic</b> or empty: found <b>{data['sampling_type']}</b>"
                )
            )

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
            data["path_id"] = None

        # deposition
        data["deposition"] = str(data["deposition"]).capitalize().strip()
        if data["deposition"] == "Fresca":
            data["deposition"] = "Fresh"
        if data["deposition"] == "Vecchia":
            data["deposition"] = "Old"
        if data["deposition"] not in ["Fresh", "Old", ""]:
            out += fn.alert_danger(
                f"The deposition value must be <b>Fresh</b>, <b>Old</b> or empty at row {index + 2}: found {data['deposition']}"
            )

        # matrix
        data["matrix"] = str(data["matrix"]).capitalize().strip()
        if data["matrix"] in ["Si", "Sì"]:
            data["matrix"] = "Yes"
        if data["matrix"] == "No":
            data["matrix"] = "No"
        if data["matrix"] not in ["Yes", "No", ""]:
            out += fn.alert_danger(f"The matrix value must be <b>Yes</b> or <b>No</b> or empty at row {index + 2}: found {data['matrix']}")

        # collected_scat
        data["collected_scat"] = str(data["collected_scat"]).capitalize().strip()
        if data["collected_scat"] in ["Si", "Sì"]:
            data["collected_scat"] = "Yes"
        if data["collected_scat"] == "No":
            data["collected_scat"] = "No"
        if data["collected_scat"] not in ["Yes", "No", ""]:
            out += fn.alert_danger(
                f"The collected_scat value must be <b>Yes</b> or <b>No</b> or empty at row {index + 2}: found {data['collected_scat']}"
            )

        # scalp_category
        data["scalp_category"] = str(data["scalp_category"]).capitalize().strip()
        if data["scalp_category"] not in ["C1", "C2", "C3", "C4", ""]:
            out += fn.alert_danger(
                f"The scalp category value must be <b>C1, C2, C3, C4</b> or empty at row {index + 2}: found {data['scalp_category']}"
            )

        # genetic_sample
        data["genetic_sample"] = str(data["genetic_sample"]).capitalize().strip()
        if data["genetic_sample"] in ["Si", "Sì"]:
            data["genetic_sample"] = "Yes"
        if data["genetic_sample"] == "No":
            data["genetic_sample"] = "No"
        if data["genetic_sample"] not in ["Yes", "No", ""]:
            out += fn.alert_danger(
                f"The genetic_sample value must be <b>Yes</b>, <b>No</b> or empty at row {index + 2}: found {data['genetic_sample']}"
            )

        # notes
        data["notes"] = str(data["notes"]).strip()

        data["operator"] = str(data["operator"]).strip()
        data["institution"] = str(data["institution"]).strip()

        scats_data[index] = dict(data)
        # print(scats_data[index])

        index += 1

    if out:
        return True, out, {}, {}, {}

    # extract paths
    all_paths: dict = {}

    # extract tracks
    all_tracks: dict = {}

    return False, "", scats_data, all_paths, all_tracks
