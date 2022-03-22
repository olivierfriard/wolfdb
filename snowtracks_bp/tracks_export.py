"""
export tracks from XLSX file
"""

from openpyxl import Workbook
from tempfile import NamedTemporaryFile
import psycopg2
import psycopg2.extras
from config import config
import fiona
import shutil
import functions as fn
import json


def export_tracks(tracks):

    wb = Workbook()

    ws1 = wb.active
    ws1.title = f"Tracks"

    header = [
        "snowtrack_id",
        "sampling_type",
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
        "days_after_snowfall",
        "minimum_number_of_wolves",
        "track_format",
        "notes",
    ]

    ws1.append(header)

    for row in tracks:
        out = []
        out.append(row["snowtrack_id"])
        out.append(row["sampling_type"])
        out.append(row["transect_id"])
        out.append(row["date"] if row["date"] is not None else "")
        out.append(row["coord_east"])
        out.append(row["coord_north"])
        out.append(row["coord_zone"])
        out.append(row["track_type"])
        out.append(row["location"])
        out.append(row["municipality"])
        out.append(row["province"])
        out.append(row["observer"] if row["observer"] is not None else "")
        out.append(row["institution"] if row["institution"] is not None else "")
        out.append(row["scalp_category"])
        out.append(row["days_after_snowfall"])
        out.append(row["minimum_number_of_wolves"])
        out.append(row["track_format"])
        out.append(row["notes"] if row["notes"] is not None else "")

        ws1.append(out)

    with NamedTemporaryFile() as tmp:
        wb.save(tmp.name)
        tmp.seek(0)
        stream = tmp.read()

        return stream


def export_shapefile(dir_path: str, file_name: str, log_file: str) -> str:
    """
    export tracks that have shape in an ESRI shapefile
    """

    log = open(log_file, "w")

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("SELECT snowtrack_id, ST_AsGeoJSON(multilines) AS track_geojson FROM snow_tracks")
    tracks = cursor.fetchall()

    schema = {
        "geometry": "MultiLineString",
        "properties": [("track_id", "str")],
    }

    with fiona.open(dir_path, mode="w", driver="ESRI Shapefile", schema=schema, crs="EPSG:32632") as layer:

        for track in tracks:

            print(file=log)
            print(track, file=log)

            if track["track_geojson"] is None:
                continue
            transect_geojson = json.loads(track["track_geojson"])

            rowDict = {
                "geometry": {"type": "MultiLineString", "coordinates": transect_geojson["coordinates"]},
                "properties": {"track_id": track["snowtrack_id"]},
            }
            layer.write(rowDict)

    log.close()

    # make a ZIP archive
    zip_file_name = shutil.make_archive(file_name, "zip", dir_path)

    return zip_file_name
