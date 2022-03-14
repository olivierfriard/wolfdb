"""
create shapefile (using fiona)
with all paths based on the completeness


"""


import psycopg2
import psycopg2.extras

import sys
import json
import fiona

connection = psycopg2.connect(
    user="postgres", password="5WhvfCmfRXweM6NR", host="localhost", port="5432", database="wolf"
)

cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

cursor.execute("SELECT * FROM paths")
paths = cursor.fetchall()

schema = {
    "geometry": "LineString",
    "properties": [
        ("province", "str"),
        ("transect_id", "str"),
        ("path_id", "str"),
        ("completeness", "int"),
        ("date", "str"),
        ("month", "str"),
        ("observer", "str"),
        ("institution", "str"),
        ("category", "str"),
    ],
}

pointShp = fiona.open(sys.argv[1], mode="w", driver="ESRI Shapefile", schema=schema, crs="EPSG:32632")

for path in paths:

    print(file=sys.stderr)
    print(path, file=sys.stderr)
    if path["transect_id"] is None or path["transect_id"] == "":
        print(f"No transect in path", file=sys.stderr)
        continue

    # print(path["date"].isoformat().split("-")[1])
    # continue

    cursor.execute(
        (
            "SELECT *, "
            "ST_AsGeoJSON(multilines) AS transect_geojson, "
            "ROUND(ST_Length(multilines)) AS transect_length "
            "FROM transects "
            "WHERE transect_id = %s"
        ),
        [path["transect_id"]],
    )

    transect = cursor.fetchone()
    # print(transect)

    if transect is None:
        print(f"path['transect_id'] NOT FOUND", file=sys.stderr)
        continue

    if path["completeness"]:

        print(transect["transect_length"], file=sys.stderr)

        transect_geojson = json.loads(transect["transect_geojson"])
        if len(transect_geojson["coordinates"]) == 1:
            # print(transect_geojson["coordinates"])
            start_point = transect_geojson["coordinates"][0][0]
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
                print(point, d, tot_dist, transect["transect_length"], file=sys.stderr)
                new_list.append(point)
                if round((tot_dist / transect["transect_length"]) * 100) >= path["completeness"]:
                    break

            if round((tot_dist / transect["transect_length"]) * 100) >= path["completeness"]:
                print(f'{path["completeness"]} COMPLETE OK  {tot_dist / transect["transect_length"]}', file=sys.stderr)

                rowDict = {
                    "geometry": {"type": "LineString", "coordinates": new_list},
                    "properties": {
                        "province": transect["province"],
                        "transect_id": path["transect_id"],
                        "path_id": path["path_id"],
                        "completeness": path["completeness"],
                        "date": path["date"].isoformat(),
                        "month": path["date"].isoformat().split("-")[1],
                        "observer": path["observer"],
                        "institution": path["institution"],
                        "category": path["category"],
                    },
                }
                pointShp.write(rowDict)

            else:
                print(f'{path["completeness"]} COMPLETE NOT  {tot_dist / transect["transect_length"]}', file=sys.stderr)
