"""
grid path effort by cell (from shapefile) by path

"""

import os
import json
import sys
import fiona
import psycopg2
import psycopg2.extras


sys.path.insert(1, os.path.join(sys.path[0], ".."))
import functions as fn


if len(sys.argv) != 3:
    print("missing arguments")
    sys.exit(0)

connection = fn.get_connection()
cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

shapes = fiona.open(sys.argv[1])

mode = sys.argv[2]  # by_cell, by_date,
if mode not in ["by_cell", "by_date"]:
    print("mode must be in 'by_cell' or 'by_date'")
    sys.exit()

distances = {}
n_transects = {}

for shape in shapes:

    id = shape["id"]
    print(f"cell ID: {id}", file=sys.stderr)

    distances[id] = {}

    # print(shape["properties"])
    # print(shape["geometry"]["type"])
    print(f"{shape['geometry']['coordinates']=}", file=sys.stderr)

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

    # iterate paths
    for transect in transects:
        print(f'transect ID: {transect["transect_id"]}\t', file=sys.stderr)
        transect_geojson = json.loads(transect["transect_geojson"])
        if len(transect_geojson["coordinates"]) != 1:
            print(f"CHECK TRANSECT COORDINATES {transect['transect_id']}")
            sys.exit()

        cursor.execute(
            "SELECT path_id, date::date, completeness FROM paths WHERE transect_id = %s", [transect["transect_id"]]
        )
        paths = cursor.fetchall()
        for path in paths:
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

                print(
                    f'path_id: {path["path_id"]}  distance: {round((tot_dist / transect["transect_length"]) * 100)}',
                    file=sys.stderr,
                )

                path_date = f"{path['date']:%Y-%m-%d}"
                if path_date not in distances[id]:
                    distances[id][path_date] = 0

                distances[id][path_date] += tot_dist

    print("=" * 50, file=sys.stderr)


sep = "\t"


if mode == "by_date":
    # header
    print("cell ID\ttransects number\tdistances (m)")
    for id in distances:
        print(
            f"{id}{sep}{n_transects[id]}{sep}{ f'{sep}'.join([str(round(distances[id][date])) for date in sorted(distances[id].keys())])}"
        )

if mode == "by_cell":
    # header
    print("cell ID\ttransects number\tTotal distance (m)")

    for id in distances:
        tot_distance = round(sum([distances[id][date] for date in distances[id]]))
        print(f"{id}{sep}{n_transects[id]}{sep}{tot_distance}")
