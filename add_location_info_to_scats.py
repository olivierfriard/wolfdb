
import psycopg2
import psycopg2.extras
import functions as fn

import subprocess
import sys


connection = fn.get_connection()
cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

cursor.execute("SELECT scat_id, sampling_type, path_id, st_x(geometry_utm)::integer AS x, st_y(geometry_utm)::integer AS y FROM scats ORDER BY scat_id")
scats = cursor.fetchall()
for row in scats:

    print(row["scat_id"])

    out, error = subprocess.Popen(f"wget -O - http://127.0.0.1:5000/rev_geocoding/{row['x']}/{row['y']}/32N",
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, shell=True).communicate()

    out = out.decode("utf-8")
    print(out)
    d = eval(out)
    print(d, file=sys.stderr)


    sql = "UPDATE scats SET region = %s, province = %s, municipality = %s, location = %s WHERE scat_id = %s "
    cursor.execute(sql, [d['region'] ,d['province_code'], d['municipality'], d['location'], row["scat_id"]])
    #connection.commit()



