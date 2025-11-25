"""
import tracks from XLSX file
"""

import pandas as pd
import pathlib as pl
from config import config
import functions as fn
import datetime
import utm

params = config()


def extract_data_from_tracks_xlsx(filename: str):
    """
    Extract and check data from a XLSX file
    """

    if pl.Path(filename).suffix == ".XLSX":
        engine = "openpyxl"
    if pl.Path(filename).suffix == ".ODS":
        engine = "odf"

    out = ""

    try:
        df_all = pd.read_excel(
            pl.Path(params["upload_folder"]) / pl.Path(filename),
            sheet_name=None,
            engine=engine,
        )
    except Exception:
        return (
            True,
            fn.alert_danger(f"Error reading the file. Check your XLSX/ODS file"),
            {},
        )

    """
    if "Tracks" not in df.keys():
        return True, fn.alert_danger(f"Tracks sheet not found in workbook"), {}, {}, {}
    scats_df = df["Tracks"]
    """

    first_sheet_name = list(df_all.keys())[0]

    tracks_df = df_all[first_sheet_name]

    columns = [
        "snowtrack_id",
        "transect_id",
        "date",
        "coord_east",
        "coord_north",
        "coord_zone",
        "track_type",
        "location",
        "municipality",
        "province",
        "operator",
        "institution",
        "scalp_category",
        "sampling_type",
        "days_after_snowfall",
        "track_type",
        "minimum_number_of_wolves",
        "track_format",
        "notes",
    ]

    # check columns
    for column in columns:
        if column not in list(tracks_df.columns) and column != "track_type":
            return True, fn.alert_danger(f"Column {column} is missing"), {}

    tracks_data = {}
    for index, row in tracks_df.iterrows():
        data = {}
        for column in list(tracks_df.columns):
            data[column] = row[column]
            if isinstance(data[column], float) and str(data[column]) == "nan":
                data[column] = ""

        # date
        try:
            year = int(data["snowtrack_id"][1 : 2 + 1]) + 2000
            month = int(data["snowtrack_id"][3 : 4 + 1])
            day = int(data["snowtrack_id"][5 : 6 + 1])
            date = f"{year}-{month:02}-{day:02}"
            try:
                datetime.datetime.strptime(date, "%Y-%m-%d")
            except Exception:
                out += fn.alert_danger(
                    f"Row {index + 2}: the date ({date}) of the track ID {data['snowtrack_id']} is not valid. Use the YYMMDD format"
                )

        except Exception:
            out += fn.alert_danger(
                f"Row {index + 2}: the track ID is not valid at row {index + 2}: {data['snowtrack_id']}"
            )

        # check date
        try:
            date_from_file = str(data["date"]).split(" ")[0].strip()
        except Exception:
            date_from_file = ""

        if date != date_from_file:
            out += fn.alert_danger(
                f"Row {index + 2}: check the track ID and the date: {data['snowtrack_id']}  {date_from_file}"
            )

        data["date"] = date_from_file

        # check province code
        province = fn.check_province_code(data["province"])
        if province is None:
            # check province name
            province = fn.province_name2code(data["province"])
            if province is None:
                out += fn.alert_danger(
                    f"Row {index + 2}: The province {data['province']} was not found"
                )
        data["province"] = province

        # add region from province code
        scat_region = fn.province_code2region(data["province"])
        data["region"] = scat_region

        """
        # region
        track_region = fn.get_region(data["province"])
        data["region"] = track_region
        """

        # UTM coord conversion
        # check zone
        if data["coord_zone"].upper() != "32N":
            out += fn.alert_danger(
                f"Row {index + 2}: the UTM zone is not 32N. Only WGS 84 / UTM zone 32N are accepted: found {data['coord_zone']}"
            )

        # check if coordinates are OK
        try:
            _ = utm.to_latlon(
                int(data["coord_east"]), int(data["coord_north"]), 32, "N"
            )
        except Exception:
            out += fn.alert_danger(
                f"Row {index + 2}: check the UTM coordinates: {data['coord_east']} {data['coord_north']} {data['coord_zone']}"
            )

        data["geometry_utm"] = (
            f"SRID=32632;POINT({data['coord_east']} {data['coord_north']})"
        )

        # sampling_type
        data["sampling_type"] = str(data["sampling_type"]).capitalize().strip()
        if data["sampling_type"] not in ["Opportunistic", "Systematic"]:
            out += fn.alert_danger(
                f"Row {index + 2}: Sampling type must be <i>Opportunistic</i> or <i>Systematic</i>: found <b>{data['sampling_type']}</b>"
            )

        # no path ID if scat is opportunistic
        if data["sampling_type"] == "Opportunistic":
            data["transect_id"] = ""

        # scalp_category
        data["scalp_category"] = str(data["scalp_category"]).capitalize().strip()
        if data["scalp_category"] not in ["C1", "C2", "C3", "C4", ""]:
            out += fn.alert_danger(
                f"Row {index + 2}: The scalp category value must be <b>C1, C2, C3, C4</b> or empty: found {data['scalp_category']}"
            )

        data["operator"] = str(data["operator"]).strip()

        data["institution"] = str(data["institution"]).strip()

        data["days_after_snowfall"] = str(data["days_after_snowfall"]).strip()

        if "track_type" in tracks_df.columns:
            data["track_type"] = str(data["track_type"]).strip()
        else:
            data["track_type"] = ""

        data["minimum_number_of_wolves"] = str(data["minimum_number_of_wolves"]).strip()

        # notes
        data["notes"] = str(data["notes"]).strip()

        tracks_data[index] = dict(data)

    if out:
        return True, out, {}

    return False, "", tracks_data
