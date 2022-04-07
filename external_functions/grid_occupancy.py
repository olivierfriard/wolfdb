"""
read shapefile with fiona module

"""


import sys
import fiona
import psycopg2
import psycopg2.extras
import functions as fn

connection = fn.get_connection()
cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

shapes = fiona.open(sys.argv[1])


for shape in shapes:

    id = shape["id"]
    print(id, file=sys.stderr)

    # print(shape["properties"])
    # print(shape["geometry"]["type"])
    # print(f"{shape['geometry']['coordinates']=}")

    coord_list = shape["geometry"]["coordinates"][0]
    coord_str = ", ".join([f"{round(x[0])} {round(x[1])}" for x in coord_list])

    sql = f"SELECT COUNT(scat_id) AS count FROM scats WHERE ST_CONTAINS(ST_GeomFromText('POLYGON(({coord_str}))', 32632), geometry_utm); "
    print(sql, file=sys.stderr)

    cursor.execute(sql)
    result = cursor.fetchone()
    print(f'{id}\t{result["count"]}\t{result["count"] != 0}')
