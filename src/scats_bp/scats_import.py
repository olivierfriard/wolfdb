"""
import scats from XLSX file
"""

from config import config
import functions as fn


import pathlib as pl
import pandas as pd
import datetime
import utm

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

    """
    if "Scats" not in df.keys():
        return True, fn.alert_danger(f"Scats sheet not found in workbook"), {}, {}, {}
    scats_df = df["Scats"]
    """

    # check columns
    for column in [
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
    ]:
        if column not in list(scats_df.columns):
            return True, fn.alert_danger(f"Column {column} is missing"), {}, {}, {}

    columns_list = list(scats_df.columns)

    province_code_list = fn.province_code_list()
    prov_name2prov_code = fn.province_name2code_dict()
    prov_code2region = fn.province_code2region_dict()

    scats_data = {}
    index = 0
    for row in scats_df.itertuples(index=False):
        data: dict = {}

        for idx, column in enumerate(columns_list):
            data[column] = row[idx]
            if isinstance(data[column], float) and str(data[column]) == "nan":
                data[column] = ""

        # date
        try:
            year = int(row.scat_id[1 : 2 + 1]) + 2000
            month = int(row.scat_id[3 : 4 + 1])
            day = int(row.scat_id[5 : 6 + 1])
            date = f"{year}-{month:02}-{day:02}"

            try:
                datetime.datetime.strptime(date, "%Y-%m-%d")
            except Exception:
                out += fn.alert_danger(
                    f"Row {index + 2}: the date ({date}) of the scat ID {row.scat_id} is not valid. Use the YYMMDD format"
                )
        except Exception:
            if DEBUG:
                raise
            out += fn.alert_danger(f"Row {index + 2}: The scat ID is not valid: {row.scat_id}")

        # check date
        try:
            date_from_file = str(row.date).split(" ")[0].strip()
        except Exception:
            date_from_file = ""

        if date != date_from_file:
            out += fn.alert_danger(f"Row {index + 2}: the scat ID {row.scat_id} and the date {date_from_file} are not compatible")

        data["date"] = date_from_file

        # path_id
        path_id = fn.get_path_id(row.transect_id, date)
        data["path_id"] = path_id

        # check province code
        if row.province.upper() in province_code_list:
            province = row.province.upper()
        else:
            province = prov_name2prov_code.get(row.province.upper(), None)
            if province is None:
                out += fn.alert_danger(f"Row {index + 2}: the province '{row.province}' was not found")
        data["province"] = province

        # add region from province code
        data["region"] = prov_code2region.get(data["province"], "")

        # UTM coord conversion
        # check zone
        data["coord_zone"] = data["coord_zone"].upper().strip()

        if data["coord_zone"][-1] not in ("S", "N"):
            out += fn.alert_danger(f"Row {index + 2}: the UTM zone is not correct. File contains: '{data['coord_zone']}'")

        hemisphere = data["coord_zone"][-1]

        data["coord_zone"] = data["coord_zone"].replace(hemisphere, "")

        # check if coordinates are OK
        try:
            _ = utm.to_latlon(int(data["coord_east"]), int(data["coord_north"]), data["coord_zone"], hemisphere)
        except Exception:
            out += fn.alert_danger(
                f'Row {index + 2}: Check the UTM coordinates. East: "{data["coord_east"]}" North: "{data["coord_north"]} Zone: {data["coord_zone"]}"'
            )

        srid = int(data["coord_zone"]) + (32600 if hemisphere == "N" else 32700)
        data["geometry_utm"] = f"ST_GeomFromText('POINT({data['coord_east']} {data['coord_north']})', {srid})"

        # sampling_type
        data["sampling_type"] = str(data["sampling_type"]).capitalize().strip()
        if data["sampling_type"] not in ["Opportunistic", "Systematic", ""]:
            out += fn.alert_danger(
                f'Row {index + 2}: Sampling type must be <b>Opportunistic</b>, <b>Systematic</b> or empty: found "{data["sampling_type"]}"'
            )

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
