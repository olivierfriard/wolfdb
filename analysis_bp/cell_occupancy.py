"""
grid occupancy by cell (from shapefile) by path

* number of samples
* presence of sample
"""

import math
import fiona
import psycopg2
import psycopg2.extras
import zipfile
import functions as fn
import pathlib as pl
import shutil
import datetime as dt
import io
import json


def get_cell_occupancy(zip_shapefile_path: str, year_init: str, year_end: str):

    sep = "\t"

    # extract zip file

    with zipfile.ZipFile(zip_shapefile_path, "r") as zip_ref:
        zip_ref.extractall(pl.Path("/tmp") / pl.Path(zip_shapefile_path).stem)

    # remove uploaded file
    pl.Path(zip_shapefile_path).unlink()

    if len(list((pl.Path("/tmp") / pl.Path(zip_shapefile_path).stem).glob("*.shp"))) != 1:
        return 1, "shp not found"
    shp_path = str(list((pl.Path("/tmp") / pl.Path(zip_shapefile_path).stem).glob("*.shp"))[0])

    shapes = fiona.open(shp_path)

    data, distances, n_transects = {}, {}, {}

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    for shape in shapes:

        id = shape["id"]
        # print(f"cell ID: {id}", file=sys.stderr)

        data[id] = {}
        distances[id] = {}

        coord_list = shape["geometry"]["coordinates"][0]
        coord_str = ", ".join([f"{round(x[0])} {round(x[1])}" for x in coord_list])

        sql = (
            f"SELECT *, "
            "ST_AsGeoJSON(multilines) AS transect_geojson, "
            "ROUND(ST_Length(multilines)) AS transect_length "
            "FROM transects "
            f"WHERE ST_INTERSECTS(ST_GeomFromText('POLYGON(({coord_str}))', 32632), multilines); "
        )

        cursor.execute(sql)
        transects = cursor.fetchall()

        n_transects[id] = len(transects) if transects is not None else 0

        for transect in transects:

            transect_geojson = json.loads(transect["transect_geojson"])

            cursor.execute(
                "SELECT path_id, date::date, completeness FROM paths WHERE transect_id = %s", [transect["transect_id"]]
            )
            paths = cursor.fetchall()

            for path in paths:
                path_date = f"{path['date']:%Y-%m-%d}"
                if path_date not in data[id]:
                    data[id][path_date] = 0

                cursor.execute(
                    f"SELECT count(scat_id) AS count FROM scats WHERE path_id = %s AND ST_CONTAINS(ST_GeomFromText('POLYGON(({coord_str}))', 32632), geometry_utm)",
                    [path["path_id"]],
                )
                scat = cursor.fetchone()
                data[id][path_date] += scat["count"]

                if path["completeness"]:

                    tot_dist = 0
                    new_list = []
                    for idx, point in enumerate(transect_geojson["coordinates"][0]):
                        if idx == 0:
                            continue
                        d = (
                            (point[0] - transect_geojson["coordinates"][0][idx - 1][0]) ** 2
                            + (point[1] - transect_geojson["coordinates"][0][idx - 1][1]) ** 2
                        ) ** 0.5
                        tot_dist += d

                        if round((tot_dist / transect["transect_length"]) * 100) >= path["completeness"]:
                            break

                    path_date = f"{path['date']:%Y-%m-%d}"
                    if path_date not in distances[id]:
                        distances[id][path_date] = 0

                    distances[id][path_date] += tot_dist

    max_paths_number = max([len(data[id]) for id in data])

    header = f"Cell ID{sep}{sep.join([f'{year_init}-{x:0{int(math.log10(max_paths_number))+1}}' for x in range(1, max_paths_number + 1)])}\n"

    out_number, out_presence, out_dates = header, header, header

    for id in data:
        out_number += f"{id}{sep}{ f'{sep}'.join([str(data[id][date]) for date in sorted(data[id].keys())])}\n"
        out_presence += (
            f"{id}{sep}{ f'{sep}'.join([str(int(data[id][date] > 0)) for date in sorted(data[id].keys())])}\n"
        )
        out_dates += f"{id}{sep}{ f'{sep}'.join([date for date in sorted(data[id].keys())])}\n"

    out_distances = "Cell ID\tTransects number\tdistances (m)"
    for id in distances:
        tot_distance = round(sum([distances[id][date] for date in distances[id]]))
        out_distances += f"{id}{sep}{n_transects[id]}{sep}{tot_distance}\n"

    # remove directory containing shapefile
    if (pl.Path("/tmp") / pl.Path(zip_shapefile_path).stem).is_dir():
        shutil.rmtree(pl.Path("/tmp") / pl.Path(zip_shapefile_path).stem)

    # zip results
    '''zip_file_path = f"static/cell_occupancy_{dt.datetime.now():%Y-%m-%d_%H%M%S}.zip"'''

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("cell_occupancy_samples_number.tsv", out_number)
        archive.writestr("cell_occupancy_samples_presence.tsv", out_presence)
        archive.writestr("cell_occupancy_dates.tsv", out_dates)
        archive.writestr("cell_distances.tsv", out_distances)

    return (0, zip_buffer)
