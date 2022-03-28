"""
import scats from XLSX file
"""

import pathlib as pl
import pandas as pd
import datetime
import utm

from config import config
import functions as fn

params = config()


def extract_data_from_xlsx(filename):
    """
    Extract and check data from a XLSX file
    """

    if pl.Path(filename).suffix == ".XLSX":
        engine = "openpyxl"
    if pl.Path(filename).suffix == ".ODS":
        engine = "odf"

    out = ""

    try:
        df = pd.read_excel(pl.Path(params["upload_folder"]) / pl.Path(filename), sheet_name=None, engine=engine)
    except Exception:
        raise
        return True, fn.alert_danger(f"Error reading the file. Check your XLSX/ODS file"), {}, {}, {}

    if "Scats" not in df.keys():
        return True, fn.alert_danger(f"Scats sheet not found in workbook"), {}, {}, {}

    scats_df = df["Scats"]

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

    scats_data = {}
    for index, row in scats_df.iterrows():
        data = {}
        for column in list(scats_df.columns):
            data[column] = row[column]
            if isinstance(data[column], float) and str(data[column]) == "nan":
                data[column] = ""

        # date
        try:
            year = int(data["scat_id"][1 : 2 + 1]) + 2000
            month = int(data["scat_id"][3 : 4 + 1])
            day = int(data["scat_id"][5 : 6 + 1])
            date = f"{year}-{month:02}-{day:02}"

            try:
                datetime.datetime.strptime(date, "%Y-%m-%d")
            except Exception:
                out += fn.alert_danger(
                    f'Row {index + 2}: the date ({date}) of the scat ID {data["scat_id"]} is not valid. Use the YYMMDD format'
                )
        except Exception:
            out += fn.alert_danger(f"The scat ID is not valid at row {index + 2}: {data['scat_id']}")

        # check date
        try:
            date_from_file = str(data["date"]).split(" ")[0].strip()
        except Exception:
            date_from_file = ""

        if date != date_from_file:
            out += fn.alert_danger(
                f"Check the scat ID and the date at row {index + 2}: {data['scat_id']}  {date_from_file}"
            )

        data["date"] = date_from_file

        # path_id
        path_id = fn.get_path_id(data["transect_id"], date)
        data["path_id"] = path_id

        # check province code
        province = fn.check_province_code(data["province"])
        if province is None:
            # check province name
            province = fn.province_name2code(data["province"])
            if province is None:
                out += fn.alert_danger(f"Row {index + 2}: The province {data['province']} was not found")
        data["province"] = province

        # add region from province code
        scat_region = fn.province_code2region(data["province"])
        data["region"] = scat_region

        # UTM coord conversion
        # check zone
        if data["coord_zone"].upper() != "32N":
            out += fn.alert_danger(
                f"The UTM zone is not 32N. Only WGS 84 / UTM zone 32N are accepted (row {index + 2}): found {data['coord_zone']}"
            )

        # check if coordinates are OK
        try:
            _ = utm.to_latlon(int(data["coord_east"]), int(data["coord_north"]), 32, "N")
        except Exception:
            out += fn.alert_danger(
                f'Check the UTM coordinates at row {index + 2}: {data["coord_east"]} {data["coord_north"]} {data["coord_zone"]}'
            )

        data["geometry_utm"] = f"SRID=32632;POINT({data['coord_east']} {data['coord_north']})"

        # sampling_type
        data["sampling_type"] = str(data["sampling_type"]).capitalize().strip()
        if data["sampling_type"] not in ["Opportunistic", "Systematic"]:
            out += fn.alert_danger(
                f'Sampling type must be <b>Opportunistic</b>, <b>Systematic</b>  at row {index + 2}: found {data["sampling_type"]}'
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
                f'The deposition value must be <b>Fresh</b>, <b>Old</b> or empty at row {index + 2}: found {data["deposition"]}'
            )

        # matrix
        data["matrix"] = str(data["matrix"]).capitalize().strip()
        if data["matrix"] in ["Si", "Sì"]:
            data["matrix"] = "Yes"
        if data["matrix"] == "No":
            data["matrix"] = "No"
        if data["matrix"] not in ["Yes", "No", ""]:
            out += fn.alert_danger(
                f'The matrix value must be <b>Yes</b> or <b>No</b> or empty at row {index + 2}: found {data["matrix"]}'
            )

        # collected_scat
        data["collected_scat"] = str(data["collected_scat"]).capitalize().strip()
        if data["collected_scat"] in ["Si", "Sì"]:
            data["collected_scat"] = "Yes"
        if data["collected_scat"] == "No":
            data["collected_scat"] = "No"
        if data["collected_scat"] not in ["Yes", "No", ""]:
            out += fn.alert_danger(
                f'The collected_scat value must be <b>Yes</b> or <b>No</b> or empty at row {index + 2}: found {data["collected_scat"]}'
            )

        # scalp_category
        data["scalp_category"] = str(data["scalp_category"]).capitalize().strip()
        if data["scalp_category"] not in ["C1", "C2", "C3", "C4", ""]:
            out += fn.alert_danger(
                f'The scalp category value must be <b>C1, C2, C3, C4</b> or empty at row {index + 2}: found {data["scalp_category"]}'
            )

        # genetic_sample
        data["genetic_sample"] = str(data["genetic_sample"]).capitalize().strip()
        if data["genetic_sample"] in ["Si", "Sì"]:
            data["genetic_sample"] = "Yes"
        if data["genetic_sample"] == "No":
            data["genetic_sample"] = "No"
        if data["genetic_sample"] not in ["Yes", "No", ""]:
            out += fn.alert_danger(
                f'The genetic_sample value must be <b>Yes</b>, <b>No</b> or empty at row {index + 2}: found {data["genetic_sample"]}'
            )

        # notes
        data["notes"] = str(data["notes"]).strip()

        data["operator"] = str(data["operator"]).strip()
        data["institution"] = str(data["institution"]).strip()

        scats_data[index] = dict(data)

    if out:
        return True, out, {}, {}, {}

    # extract paths
    all_paths = {}
    if "Paths" in df.keys():
        paths_df = df["Paths"]
        for index, row in paths_df.iterrows():
            data = {}
            for column in list(paths_df.columns):
                data[column] = row[column]
                if isinstance(data[column], float) and str(data[column]) == "nan":
                    data[column] = ""

            data["date"] = str(data["date"]).split(" ")[0]
            if data["completeness"] == "":
                data["completeness"] = None

            all_paths[index] = dict(data)

    else:  # no Paths sheet found. Construct from scats

        index = 0
        for idx in scats_data:
            if not scats_data[idx]["path_id"]:
                continue
            data = {}
            data["path_id"] = scats_data[idx]["path_id"]
            data["transect_id"] = scats_data[idx]["transect_id"]
            data["date"] = scats_data[idx]["date"]
            data["sampling_season"] = fn.sampling_season(scats_data[idx]["date"])
            data["completeness"] = None
            data["operator"] = scats_data[idx]["operator"]
            data["institution"] = scats_data[idx]["institution"]
            data["notes"] = ""

            all_paths[index] = dict(data)
            index += 1

    # extract tracks
    all_tracks = {}
    if "Tracks" in df.keys():
        tracks_df = df["Tracks"]
        for index, row in tracks_df.iterrows():
            data = {}
            for column in list(scats_df.columns):
                if isinstance(data[column], float) and str(data[column]) == "nan":
                    data[column] = ""
                else:
                    data[column] = row[column]

            all_tracks[index] = dict(data)

    return False, "", scats_data, all_paths, all_tracks
