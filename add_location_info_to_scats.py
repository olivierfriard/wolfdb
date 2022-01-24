"""
add location to scats in "auto" fields
locations are cached in locations.json

"""

from tinydb import TinyDB, Query

db = TinyDB('locations.json')

Row = Query()

#db.insert({'xy': 1, 'geolocation': })

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

    print(row["scat_id"], row['x'], row['y'], file=sys.stderr)

    r = db.search(Row.xy == f"{row['x']} {row['y']}")
    #print(r)
    if r:
        
        d = r[0]['geolocation']
        print("found in db", d, file=sys.stderr)

    else:
        
        out, error = subprocess.Popen(f"wget -O - http://127.0.0.1:5000/rev_geocoding/{row['x']}/{row['y']}/32N",
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, shell=True).communicate()

        out = out.decode("utf-8")
        #print(out)
        try:
            d = eval(out)
            db.insert({"xy": f"{row['x']} {row['y']}", 'geolocation': d})
        except:
            print(f"{out=}", file=sys.stderr)
            d = {'continent': '', 'country': 'NOT FOUND', 'location': 'NOT FOUND', 'municipality': 'NOT FOUND', 'province': 'NOT FOUND', 'province_code': 'NOT FOUND', 'region': 'NOT FOUND'}
            #raise
        #print(d, file=sys.stderr)


    print(row['x'], row['y'], file=sys.stderr)
    print(d['region'] ,d['province_code'], d['municipality'], d['location'], file=sys.stderr)

    
    sql = "UPDATE scats SET region_auto = %s, province_auto = %s, municipality_auto = %s, location_auto = %s WHERE scat_id = %s; "

    out = cursor.mogrify(sql, [d['region'] ,d['province_code'], d['municipality'], d['location'], row["scat_id"]])

    print(out.decode("utf-8"))
    
    # cursor.execute(sql, [d['region'] ,d['province_code'], d['municipality'], d['location'], row["scat_id"]])

    #connection.commit()
    



