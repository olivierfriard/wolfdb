"""
add location to transects
locations are cached in locations.json

"""

import redis

rdis = redis.Redis(db=3)


import psycopg2
import psycopg2.extras
import functions as fn

import subprocess
import sys
import json


connection = fn.get_connection()
cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

cursor.execute(
    "SELECT transect_id, ST_AsGeoJSON(multilines) AS transect_geojson FROM transects"
)
transects = cursor.fetchall()
for row in transects:
    print(file=sys.stderr)

    geojson = json.loads(row["transect_geojson"])

    if geojson["type"] == "MultiLineString":
        print(f"{row['transect_id']}\tMultiLineString\t", end="", file=sys.stderr)

        for line in geojson["coordinates"]:
            for points in line:
                start_position = points
                break

        print(f"{points}", file=sys.stderr)

    if geojson["type"] == "LineString":
        raise

    x, y = points
    loc_str = rdis.get(f"{x} {y}")
    if loc_str is not None:
        d = json.loads(loc_str)
        print(f"found in db: {d}", file=sys.stderr)

        if d["province_code"] == "":
            print(f"Province code missing. Query OSM", file=sys.stderr)
            loc_str = None

    if loc_str is None:
        print("NOT FOUND in DB", file=sys.stderr)

        out, error = subprocess.Popen(
            f"wget -O - http://127.0.0.1:5000/rev_geocoding/{x}/{y}/32N",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
        ).communicate()

        out = out.decode("utf-8")

        print(f"OSM results: {out}", file=sys.stderr)

        try:
            d = eval(out)
            if d["province_code"] == "":
                print("Province code NOT FOUND", file=sys.stderr)
                break

            # db.update({"xy": f"{x} {y}", "geolocation": d})
            rdis.set(f"{x} {y}", out)
        except:
            print("NOT FOUND ON OSM:", file=sys.stderr)
            print(f"{out=}", file=sys.stderr)
            d = {
                "continent": "",
                "country": "NOT FOUND",
                "location": "NOT FOUND",
                "municipality": "NOT FOUND",
                "province": "NOT FOUND",
                "province_code": "NOT FOUND",
                "region": "NOT FOUND",
            }
            # raise
        # print(d, file=sys.stderr)

    print(
        (
            f"Region: {d['region']}\tprovince: {d['province_code']}\t"
            f"Municipality: {d['municipality']}\tLocation: {d['location']}"
        ),
        file=sys.stderr,
    )

    if d["province_code"] == "":
        print("Province code NOT FOUND", file=sys.stderr)
        break

    sql = "UPDATE transect SET region = %s, province = %s, municipality = %s, location = %s WHERE transect_id = %s; "

    out = cursor.mogrify(
        sql,
        [
            d["region"],
            d["province"],
            d["municipality"],
            d["location"],
            row["transect_id"],
        ],
    )

    print(out.decode("utf-8"))

    """
    # cursor.execute(sql, [d['region'] ,d['province_code'], d['municipality'], d['location'], row["scat_id"]])

    # connection.commit()
    """
