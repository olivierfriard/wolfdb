"""
import paths from XLSX file
"""

import pandas as pd
import pathlib as pl
from config import config
import functions as fn
import datetime
import utm

params = config()


def extract_data_from_paths_xlsx(filename: str):
    """
    Extract and check data from a XLSX file
    """

    if pl.Path(filename).suffix == ".XLSX":
        engine = "openpyxl"
    if pl.Path(filename).suffix == ".ODS":
        engine = "odf"

    out = ""

    try:
        df_all = pd.read_excel(pl.Path(params["upload_folder"]) / pl.Path(filename), sheet_name=None, engine=engine)
    except Exception:
        return (
            True,
            fn.alert_danger(f"Error reading the file. Check your XLSX/ODS file"),
            {},
        )

    first_sheet_name = list(df_all.keys())[0]

    tracks_df = df_all[first_sheet_name]

    columns = [
        "transect_id",
        "date",
        "operator",
        "institution",
        "category",
        "completeness",
        "notes",
    ]

    # check columns
    for column in columns:
        if column not in list(tracks_df.columns):
            return True, fn.alert_danger(f"Column {column} is missing"), {}

    paths_data = {}
    for index, row in tracks_df.iterrows():
        data = {}
        for column in list(tracks_df.columns):
            data[column] = row[column]
            if isinstance(data[column], float) and str(data[column]) == "nan":
                data[column] = ""

        if data["transect_id"] == "":
            out += fn.alert_danger(f"Row {index + 2}: transect ID not found")
        data["transect_id"] = data["transect_id"].strip()

        # check date (must be YYYY-MM-DD)
        data["date"] = str(data["date"])
        if " " in data["date"]:
            date = data["date"].split(" ")[0]
        else:
            date = data["date"]
        try:
            datetime.datetime.strptime(date, "%Y-%m-%d")
        except Exception:
            out += fn.alert_danger(f"Row {index + 2}: the date ({date}) is not valid. Use the YYYY-MM-DD format")

        data["path_id"] = fn.get_path_id(data["transect_id"], date)

        data["date"] = date

        """
        try:
            year = int(data["snowtrack_id"][1 : 2 + 1]) + 2000
            month = int(data["snowtrack_id"][3 : 4 + 1])
            day = int(data["snowtrack_id"][5 : 6 + 1])
            date = f"{year}-{month:02}-{day:02}"
            try:
                datetime.datetime.strptime(date, "%Y-%m-%d")
            except Exception:
                out += fn.alert_danger(
                    f'Row {index + 2}: the date ({date}) of the path {data["snowtrack_id"]} is not valid. Use the YYMMDD format'
                )

        except Exception:
            out += fn.alert_danger(
                f"Row {index + 2}: the track ID is not valid at row {index + 2}: {data['snowtrack_id']}"
            )
        """

        data["operator"] = str(data["operator"]).strip()

        data["institution"] = str(data["institution"]).strip()

        # notes
        data["notes"] = str(data["notes"]).strip()

        paths_data[index] = dict(data)

    if out:
        return True, out, {}

    return False, "", paths_data
