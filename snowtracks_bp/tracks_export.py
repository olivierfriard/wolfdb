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
        "Path ID",
        "Transect ID",
        "Region",
        "Province",
        "Date",
        "Sampling season",
        "Completeness",
        "Number of samples",
        "Number of tracks",
        "Operator",
        "Institution",
        "Category",
        "Notes",
    ]

    ws1.append(header)

    for row in tracks:
        out = []
        out.append(row["path_id"])
        out.append(row["transect_id"])
        out.append(row["region"])
        out.append(row["province"])
        out.append(row["date"] if row["date"] is not None else "")
        out.append(row["sampling_season"] if row["sampling_season"] is not None else "")
        out.append(row["completeness"])
        out.append(row["n_samples"])
        out.append(row["n_tracks"])
        out.append(row["observer"] if row["observer"] is not None else "")
        out.append(row["institution"] if row["institution"] is not None else "")
        out.append(row["category"] if row["category"] is not None else "")
        out.append(row["notes"] if row["notes"] is not None else "")

        ws1.append(out)

    with NamedTemporaryFile() as tmp:
        wb.save(tmp.name)
        tmp.seek(0)
        stream = tmp.read()

        return stream


def export_shapefile(dir_path: str, log_file: str):
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

            print(transect_geojson)

            rowDict = {
                "geometry": {"type": "MultiLineString", "coordinates": transect_geojson["coordinates"]},
                "properties": {"track_id": track["snowtrack_id"]},
            }
            layer.write(rowDict)

    log.close()

    # make a ZIP archive
    zip_file_name = shutil.make_archive(dir_path, "zip", dir_path)

    return zip_file_name
