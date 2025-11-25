"""
grid occupancy by cell (from shapefile) by path

"""

import os
import sys
import fiona
import psycopg2
import psycopg2.extras
from sqlalchemy import text

sys.path.insert(1, os.path.join(sys.path[0], ".."))
import functions as fn

if len(sys.argv) != 3:
    print("missing arguments")
    sys.exit(0)

connection = fn.get_connection()
cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

shapes = fiona.open(sys.argv[1])

mode = sys.argv[2]
if mode not in ["presence", "number"]:
    print("mode must be in 'presence' or 'number'")
    sys.exit()

data = {}

for shape in shapes:
    id = shape["id"]
    print(f"cell ID: {id}", file=sys.stderr)

    data[id] = {}

    # print(shape["properties"])
    # print(shape["geometry"]["type"])
    # print(f"{shape['geometry']['coordinates']=}")

    coord_list = shape["geometry"]["coordinates"][0]
    coord_str = ", ".join([f"{round(x[0])} {round(x[1])}" for x in coord_list])

    with fn.conn_alchemy().connect() as con:
        sql = text(
            f"SELECT transect_id FROM transects WHERE ST_INTERSECTS(ST_GeomFromText('POLYGON(({coord_str}))', 32632), multilines); "
        )

        rows2 = con.execute(sql).mappings().all()

        for row2 in rows2:
            print(f"transect ID: {row2['transect_id']}\t", file=sys.stderr)

            rows3 = (
                con.execute(
                    text(
                        "SELECT path_id, date::date FROM paths WHERE transect_id = :transect_id",
                        {"transect_id": row2["transect_id"]},
                    )
                )
                .mappings()
                .all()
            )

            for row3 in rows3:
                path_date = f"{row3['date']:%Y-%m-%d}"
                if path_date not in data[id]:
                    data[id][path_date] = 0

                row4 = (
                    cursor.execute(
                        text(
                            f"SELECT count(scat_id) AS count FROM scats WHERE path_id = :path_id AND ST_CONTAINS(ST_GeomFromText('POLYGON(({coord_str}))', 32632), geometry_utm)"
                        ),
                        {"path_id": row3["path_id"]},
                    )
                    .mappings()
                    .one()
                )
                data[id][path_date] += row4["count"]
                print(
                    f"{row3['path_id']}\tnumber of scats: {row4['count']}",
                    file=sys.stderr,
                )

        print("=" * 50, file=sys.stderr)

tot_scats_nb = 0

sep = ";"
for id in data:
    tot_scats_nb += sum([data[id][date] for date in data[id]])
    if mode == "number":
        print(
            f"{id}{sep}{f'{sep}'.join([str(data[id][date]) for date in sorted(data[id].keys())])}"
        )
    if mode == "presence":
        print(
            f"{id}{sep}{f'{sep}'.join([str(int(data[id][date] > 0)) for date in sorted(data[id].keys())])}"
        )


print(f"{tot_scats_nb=}", file=sys.stderr)
