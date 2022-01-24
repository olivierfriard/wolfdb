"""
create file static/systematic_scats_transects_location.html

The output file contains the closest transect for every systematic scat

This script is required by wolfdb.py

"""

import psycopg2
import psycopg2.extras
import functions as fn

import datetime

out = '<html lang="en" class="h-100"><body>'

out += """
<head>
    <meta charset="utf-8">
    <link rel="shortcut icon" href="https://www.unito.it/sites/default/files/favicon.png" type="image/png" />
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="WolfDB">
    <meta name="author" content="Olivier Friard">

    <title>WolfDB</title>



<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-1BmE4kWBq78iYhFldvKuhfTAU6auU8tT94WrHftjDbrCEXSU1oBoqyl2QvZ6jIW3" crossorigin="anonymous">


<style>
main > .container {
  padding: 60px 15px 0;
}

</style>

</head>
"""

sql = """
SELECT transect_id, st_distance(ST_GeomFromText('POINT(XXX YYY)',32632), points_utm)::integer AS distance
FROM transects
WHERE st_distance(ST_GeomFromText('POINT(XXX YYY)',32632), points_utm) = (select min(st_distance(ST_GeomFromText('POINT(XXX YYY)',32632), points_utm)) FROM transects);
"""

connection = fn.get_connection()
cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

cursor.execute("SELECT scat_id, sampling_type, path_id, st_x(geometry_utm)::integer AS x, st_y(geometry_utm)::integer AS y FROM scats WHERE sampling_type = 'Systematic'")
scats = cursor.fetchall()

'''
out += "<h1>Location on transects for scats from systematic sample</h1>\n"

out += f"Check done at {datetime.datetime.now().replace(microsecond=0).isoformat().replace('T', ' ')}<br><br>\n"

out += f"{len(scats)} systematic scats.<br>\n"

out += '<table class="table table-striped">\n'

out += "<tr><th>Scat ID</th><th>Sampling type</th><th>Path ID</th><th>Closer Transect ID</th><th>Distance (m)</th><th>Match with path ID</th></tr>"
'''

out2 = ""
c = 0
for row in scats:

    sql2 = sql.replace("XXX", str(row["x"])).replace("YYY", str(row["y"]))

    cursor.execute(sql2)
    transect = cursor.fetchone()

    path_id = row["path_id"].replace(" ", "|")

    if path_id.startswith(transect["transect_id"] + "|"):
        match = "OK"
        out2 += '<tr>'
    else:
        match = "NO"
        c += 1
        out2 += '<tr class="table-danger">'

    if match == "NO":
        out2 += (f"""<td><a href="/view_scat/{row['scat_id']}">{row['scat_id']}</a></td>"""
                 f"""<td>{row['sampling_type']}</td>"""
                 f"""<td><a href="/view_path/{row['path_id']}">{path_id}</a></td>"""
                 f"""<td><a href="/view_transect/{transect['transect_id']}">{transect['transect_id']}</a></td>"""
                 f"""<td>{transect['distance']}</td>"""
                 f"""<td>{match}</td></tr>\n"""
                )


out += "<h1>Location on transects for scats from systematic sample</h1>\n"

out += f"Check done at {datetime.datetime.now().replace(microsecond=0).isoformat().replace('T', ' ')}<br><br>\n"

out += f"{len(scats)} systematic scats.<br>\n"

out += f"{c} scat positions that does not match the transect ID.<br>\n"

out += '<table class="table table-striped">\n'

out += "<tr><th>Scat ID</th><th>Sampling type</th><th>Path ID</th><th>Closer Transect ID</th><th>Distance (m)</th><th>Match with path ID</th></tr>"

out += out2


out += "</table>\n"

out += "</body></html>"

with open("static/systematic_scats_transects_location.html", "w") as f_out:
    f_out.write(out)


