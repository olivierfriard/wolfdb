"""
grid occupancy by cell (from shapefile) by path

* number of samples
* presence of sample
"""

import sys
import math
import fiona
import psycopg2
import psycopg2.extras
import zipfile
import pathlib as pl
import shutil
import datetime as dt
import json
from shapely.geometry import MultiPolygon, Polygon

from config import config
import functions as fn

params = config()


def get_cell_occupancy(shp_path: str, year_init: str, year_end: str, output_path: str):

    sep = "\t"

    shapes = fiona.open(shp_path)

    data, distances, n_transects = {}, {}, {}

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    crs = int(shapes.crs["init"].replace("epsg:", ""))
    for shape in shapes:

        id = shape["id"]

        data[id] = {}
        distances[id] = {}

        if shape["geometry"]["type"] == "Polygon":
            mp = MultiPolygon([Polygon(x) for x in shape["geometry"]["coordinates"]])
        elif shape["geometry"]["type"] == "MultiPolygon":
            mp = MultiPolygon([Polygon(x[0]) for x in shape["geometry"]["coordinates"]])
        else:
            return (0, "geometry not Polygon or Multipolygon")

        sql = (
            f"SELECT *, "
            "ST_AsGeoJSON(multilines) AS transect_geojson, "
            "ROUND(ST_Length(multilines)) AS transect_length "
            "FROM transects "
            # f"WHERE ST_INTERSECTS(ST_GeomFromText('{mp}', 32632), multilines); "
            f"WHERE ST_INTERSECTS(ST_Buffer(ST_Transform(ST_GeomFromText('{mp}', {crs}), 32632),0), multilines) "
        )

        cursor.execute(sql)
        transects = cursor.fetchall()

        n_transects[id] = len(transects) if transects is not None else 0

        for transect in transects:

            transect_geojson = json.loads(transect["transect_geojson"])

            cursor.execute(
                (
                    "SELECT path_id, date::date, completeness FROM paths "
                    "WHERE transect_id = %s "
                    "AND EXTRACT(year FROM date) between %s AND %s"
                ),
                [transect["transect_id"], year_init, year_end],
            )
            paths = cursor.fetchall()

            for path in paths:
                path_date = f"{path['date']:%Y-%m-%d}"
                if path_date not in data[id]:
                    data[id][path_date] = 0

                cursor.execute(
                    (
                        "SELECT count(scat_id) AS count FROM scats "
                        f"WHERE path_id = %s AND ST_CONTAINS(ST_Transform(ST_GeomFromText('{mp}', {crs}), 32632), geometry_utm)"
                        # f"WHERE path_id = %s AND ST_CONTAINS(ST_GeomFromText('{mp}', 32632), geometry_utm)"
                    ),
                    [path["path_id"]],
                )
                scat = cursor.fetchone()
                data[id][path_date] += scat["count"]

                completeness = path["completeness"] if path["completeness"] is not None else 100

                tot_dist = 0
                for idx, point in enumerate(transect_geojson["coordinates"][0]):
                    if idx == 0:
                        continue
                    d = (
                        (point[0] - transect_geojson["coordinates"][0][idx - 1][0]) ** 2
                        + (point[1] - transect_geojson["coordinates"][0][idx - 1][1]) ** 2
                    ) ** 0.5
                    tot_dist += d

                    if round((tot_dist / transect["transect_length"]) * 100) >= completeness:
                        break

                path_date = f"{path['date']:%Y-%m-%d}"
                if path_date not in distances[id]:
                    distances[id][path_date] = 0

                distances[id][path_date] += tot_dist

    header = f"Cell index{sep}"

    for property in shapes.schema["properties"]:
        header += f"{property}\t"

    max_paths_number = max([len(data[id]) for id in data])

    header += f"{sep.join([f'{year_init}-{x:0{int(math.log10(max_paths_number))+1}}' for x in range(1, max_paths_number + 1)])}\n"

    out_number, out_presence, out_dates, out_distances = header, header, header, header

    for id in data:
        out_number += f"{id}{sep}"
        # properties
        for property in shapes[int(id)]["properties"]:
            out_number += f"{shapes[int(id)]['properties'][property]}{sep}"
        out_number += f"{sep.join([str(data[id][date]) for date in sorted(data[id].keys())])}"
        if len(data[id]):
            out_number += sep
        out_number += f"{sep.join(['NA'] * (max_paths_number - len(data[id])) )}\n"

        out_presence += f"{id}{sep}"
        # properties
        for property in shapes[int(id)]["properties"]:
            out_presence += f"{shapes[int(id)]['properties'][property]}{sep}"
        out_presence += f"{sep.join([str(int(data[id][date] > 0)) for date in sorted(data[id].keys())])}"
        if len(data[id]):
            out_presence += sep
        out_presence += f"{sep.join(['NA'] * (max_paths_number - len(data[id])) )}\n"

        out_dates += f"{id}{sep}"
        # properties
        for property in shapes[int(id)]["properties"]:
            out_dates += f"{shapes[int(id)]['properties'][property]}{sep}"
        out_dates += f"{sep.join([date for date in sorted(data[id].keys())])}"
        if len(data[id]):
            out_dates += sep
        out_dates += f"{sep.join(['NA'] * (max_paths_number - len(data[id])) )}\n"

    for id in distances:
        out_distances += f"{id}{sep}"
        # properties
        for property in shapes[int(id)]["properties"]:
            out_distances += f"{shapes[int(id)]['properties'][property]}{sep}"
        out_distances += f"{sep.join([str(round(distances[id][date])) for date in sorted(distances[id].keys())])}"
        if len(distances[id]):
            out_distances += sep
        out_distances += f"{sep.join(['NA'] * (max_paths_number - len(distances[id])) )}\n"

    # remove directory containing shapefile
    pl.Path(shp_path).parent
    if pl.Path(shp_path).parent.is_dir():
        shutil.rmtree(pl.Path(shp_path).parent)

    # zip results

    '''zip_output = f"static/cell_occupancy_{dt.datetime.now():%Y-%m-%d_%H%M%S}.zip"'''

    """
    import io
    zip_output = io.BytesIO()
    """

    with zipfile.ZipFile("static/" + output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("cell_occupancy_samples_number.tsv", out_number)
        archive.writestr("cell_occupancy_samples_presence.tsv", out_presence)
        archive.writestr("cell_occupancy_dates.tsv", out_dates)
        archive.writestr("cell_distances.tsv", out_distances)

    return (0, output_path)


if __name__ == "__main__":
    result, msg = get_cell_occupancy(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    if result:
        with open(
            pl.Path(params["temp_folder"]) / pl.Path(f"cell_occupancy_{dt.datetime.now():%Y-%m-%d_%H%M%S}.log"), "w"
        ) as f_out:
            f_out.write(msg + "\n")
