"""
display the distance between scat and the closer transect
"""

import psycopg2
import psycopg2.extras

from config import config
import functions as fn


def scats_location():
    out = ""

    sql = """
    select transect_id, st_distance(ST_GeomFromText('POINT(XXX YYY)',32632), multilines)::integer as distance
    from transects
    where st_distance(ST_GeomFromText('POINT(XXX YYY)',32632), multilines) = (select min(st_distance(ST_GeomFromText('POINT(XXX YYY)',32632), multilines)) from transects);
    """

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute(
        "SELECT scat_id, sampling_type, path_id, st_x(geometry_utm)::integer AS x, st_y(geometry_utm)::integer AS y FROM scats WHERE sampling_type = 'Systematic'"
    )
    scats = cursor.fetchall()
    for row in scats:
        sql2 = sql.replace("XXX", str(row["x"])).replace("YYY", str(row["y"]))

        cursor.execute(sql2)
        transect = cursor.fetchone()

        path_id = row["path_id"].replace(" ", "_")

        if path_id.startswith(transect["transect_id"] + "_"):
            match = "OK"
        else:
            match = "NO"

        print(
            f"{row['scat_id']}\t{row['sampling_type']}\t{path_id}\t{transect['transect_id']}\t{transect['distance']}\t{match}"
        )


scats_location()
