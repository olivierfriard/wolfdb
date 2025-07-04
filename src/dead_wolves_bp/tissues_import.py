from pathlib import Path
import pandas as pd
import datetime as dt
import utm
from markupsafe import Markup

from config import config
import functions as fn


DEBUG = False
params = config()


"""
import tissues from spreadsheet file
"""


def extract_tissue_data_from_spreadsheet(filename: str):
    """
    Extract and check data from a spreadsheet file (XLSX or ODS)
    """
    if Path(filename).suffix.upper() == ".XLSX":
        engine = "openpyxl"
    if Path(filename).suffix.upper() == ".ODS":
        engine = "odf"

    out: str = ""

    try:
        dw_df = pd.read_excel(
            Path(params["upload_folder"]) / Path(filename), sheet_name=0, engine=engine
        )
    except Exception:
        try:
            dw_df = pd.read_excel(filename, sheet_name=0, engine=engine)
        except Exception:
            return (
                True,
                fn.alert_danger("Error reading the file. Check your XLSX/ODS file"),
                {},
            )  # , {}, {}

    required_columns = (
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
        "box_number",
    )

    # check columns
    for column in required_columns:
        if column not in list(dw_df.columns):
            return (
                True,
                fn.alert_danger(Markup(f"ERROR Column <b>{column}</b> is missing")),
                {},
            )  # , {}, {}

    # check if tissue_id are missing
    if dw_df["tissue_id"].isnull().any():
        # print(f'{dw_df["tissue_id"].isnull().sum()} tissue id missing', file=sys.stderr)
        return (
            True,
            fn.alert_danger(
                Markup(f"{dw_df['tissue_id'].isnull().sum()} tissue id missing")
            ),
            {},
        )  # , {}, {}

    # check if date are missing
    if dw_df["date"].isnull().any():
        return (
            True,
            fn.alert_danger(Markup(f"{dw_df['date'].isnull().sum()} date missing")),
            {},
        )  # , {}, {}

    # check if sampling type are missing
    """
    if dw_df["sampling_type"].isnull().any():
        print(f'{dw_df["sampling_type"].isnull().sum()} sampling type missing', file=sys.stderr)
    """

    # check if coordinates are missing
    if dw_df["coord_east"].isnull().any() or dw_df["coord_north"].isnull().any():
        return True, fn.alert_danger(Markup("coordinates missing")), {}  # , {}, {}

    # check if tissue_id duplicated
    if dw_df["tissue_id"].duplicated().any():
        si = dw_df["tissue_id"]
        return (
            True,
            fn.alert_danger(
                Markup(
                    f"Some tissue_id are duplicated: <pre> {dw_df[si.isin(si[si.duplicated()])].sort_values('tissue_id')}</pre>"
                )
            ),
            {},
            # {},
            # {},
        )

    # check if SCALP category != C1
    if "scalp_category" in dw_df.columns:
        for scalp in dw_df["scalp_category"]:
            if scalp != "C1":
                return (
                    True,
                    fn.alert_danger(
                        Markup(f"SCALP category is <b>{scalp}</b> (should be C1)")
                    ),
                    {},
                    {},
                    {},
                )

    # check date
    for idx, date in enumerate(dw_df["date"]):
        if isinstance(date, dt.datetime):
            date = date.strftime("%Y-%m-%d")
        try:
            dt.datetime.strptime(date, "%Y-%m-%d")
        except Exception:
            return (
                True,
                fn.alert_danger(
                    f"'{date}' is not a valid date at row {idx + 2} (check date format)"
                ),
                {},
            )  # , {}, {}

    # check province code
    for idx, province in enumerate(dw_df["province"]):
        if isinstance(province, int):
            province = f"{province:02}"
        if province not in fn.province_code_list():
            return (
                True,
                fn.alert_danger(f"Province '{province}' not found at row {idx + 2}"),
                {},
            )  # , {}, {}

    columns_list = list(dw_df.columns)

    tissues_data: dict = {}
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

        # check date
        date = str(row["date"]).split(" ")[0].strip()
        data["date"] = date

        # data["genotype_id"] = data["genotype_id"].split(" ")[0]

        # path_id
        if not pd.isna(row["transect_id"]):
            path_id = fn.get_path_id(str(row["transect_id"]), date)
            data["path_id"] = path_id
        else:
            data["path_id"] = None

        # check box number
        if pd.isna(row["box_number"]):
            data["box_number"] = None
        else:
            data["box_number"] = row["box_number"]

        # add region from province code
        data["region"] = fn.province_code2region(data["province"])

        # UTM coord conversion
        # check zone
        data["coord_zone"] = data["coord_zone"].upper().strip()

        if len(data["coord_zone"]) != 3:
            out += fn.alert_danger(
                f"ERROR on coordinates zone {row['coord_zone']}. Must be 3 characters"
            )

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
            out += fn.alert_danger(
                Markup(
                    f"Row {index + 2}: Check the UTM coordinates zone <b>{data['coord_zone']}</b>"
                )
            )

        # check if coordinates are OK
        try:
            _ = utm.to_latlon(
                int(data["coord_east"]), int(data["coord_north"]), zone, hemisphere
            )
        except Exception:
            out += fn.alert_danger(
                f'Row {index + 2}: Check the UTM coordinates. East: "{data["coord_east"]}" North: "{data["coord_north"]} Zone: {data["coord_zone"]}"'
            )
        srid = zone + (32600 if hemisphere == "N" else 32700)
        data["geometry_utm"] = (
            f"ST_GeomFromText('POINT({data['coord_east']} {data['coord_north']})', {srid})"
        )

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

        # no path ID if tissue is opportunistc
        if data["sampling_type"] == "Opportunistic":
            data["path_id"] = ""

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

        if pd.isna(row["operator"]):
            data["operator"] = None
        else:
            data["operator"] = str(data["operator"]).strip()

        if pd.isna(row["institution"]):
            data["institution"] = None
        else:
            data["institution"] = str(data["institution"]).strip()

        tissues_data[index] = dict(data)

        index += 1

    if out:
        return True, out, {}  # , {}, {}

    """
    # extract paths
    all_paths: dict = {}

    # extract tracks
    all_tracks: dict = {}
    """

    return False, "", tissues_data  # , all_paths, all_tracks
