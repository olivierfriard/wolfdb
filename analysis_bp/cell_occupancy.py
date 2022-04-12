"""
grid occupancy by cell (from shapefile) by path

* number of samples
* presence of sample
"""

import os
import sys
import fiona
import psycopg2
import psycopg2.extras
import zipfile
import functions as fn
import pathlib as pl
import shutil
import datetime as dt
import io


def get_cell_occupancy(zip_shapefile_path: str):

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

    """
    mode = "presence"
    if mode not in ["presence", "number"]:
        print("mode must be in 'presence' or 'number'")
        sys.exit()
    """

    data = {}

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    for shape in shapes:

        id = shape["id"]
        # print(f"cell ID: {id}", file=sys.stderr)

        data[id] = {}

        coord_list = shape["geometry"]["coordinates"][0]
        coord_str = ", ".join([f"{round(x[0])} {round(x[1])}" for x in coord_list])

        sql = f"SELECT transect_id FROM transects WHERE ST_INTERSECTS(ST_GeomFromText('POLYGON(({coord_str}))', 32632), multilines); "

        cursor.execute(sql)
        rows2 = cursor.fetchall()

        for row2 in rows2:
            # print(f'transect ID: {row2["transect_id"]}\t', file=sys.stderr)

            cursor.execute("SELECT path_id, date::date FROM paths WHERE transect_id = %s", [row2["transect_id"]])
            rows3 = cursor.fetchall()

            for row3 in rows3:
                path_date = f"{row3['date']:%Y-%m-%d}"
                if path_date not in data[id]:
                    data[id][path_date] = 0

                cursor.execute(
                    f"SELECT count(scat_id) AS count FROM scats WHERE path_id = %s AND ST_CONTAINS(ST_GeomFromText('POLYGON(({coord_str}))', 32632), geometry_utm)",
                    [row3["path_id"]],
                )
                row4 = cursor.fetchone()
                data[id][path_date] += row4["count"]
                # print(f"{row3['path_id']}\tnumber of scats: {row4['count']}", file=sys.stderr)

    out_number = f"Cell ID{sep}"
    out_presence = f"Cell ID{sep}"
    for id in data:
        out_number += f"{id}{sep}{ f'{sep}'.join([str(data[id][date]) for date in sorted(data[id].keys())])}\n"
        out_presence += (
            f"{id}{sep}{ f'{sep}'.join([str(int(data[id][date] > 0)) for date in sorted(data[id].keys())])}\n"
        )

    # remove directory
    if (pl.Path("/tmp") / pl.Path(zip_shapefile_path).stem).is_dir():
        shutil.rmtree(pl.Path("/tmp") / pl.Path(zip_shapefile_path).stem)

    # zip results
    '''zip_file_path = f"static/cell_occupancy_{dt.datetime.now():%Y-%m-%d_%H%M%S}.zip"'''

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("cell_occupancy_samples_number.tsv", out_number)
        archive.writestr("cell_occupancy_samples_presence.tsv", out_presence)

    return (0, zip_buffer)
