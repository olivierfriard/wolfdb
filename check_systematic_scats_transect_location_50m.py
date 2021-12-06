
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

out += "<h1>Location on transects closer than 50 m for scats from systematic sample</h1>\n"

out += f"Check done at {datetime.datetime.now().replace(microsecond=0).isoformat().replace('T', ' ')}<br><br>\n"


out += '<table class="table table-striped">\n'

out += "<tr><th>Scat ID</th><th>Sampling type</th><th>Path ID</th><th>Closer Transect ID</th><th>Distance (m)</th><th>Match with path ID</th></tr>"

sql = """
SELECT transect_id, st_distance(ST_GeomFromText('POINT(XXX YYY)',32632), points_utm)::integer AS distance
FROM transects
WHERE st_distance(ST_GeomFromText('POINT(XXX YYY)',32632), points_utm) < 50;
"""

connection = fn.get_connection()
cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

cursor.execute("SELECT scat_id, sampling_type, path_id, st_x(geometry_utm)::integer AS x, st_y(geometry_utm)::integer AS y FROM scats WHERE sampling_type = 'Systematic'")
scats = cursor.fetchall()
for row in scats:

    sql2 = sql.replace("XXX", str(row["x"])).replace("YYY", str(row["y"]))

    cursor.execute(sql2)
    transects = cursor.fetchall()

    path_id = row["path_id"].replace(" ", "_")

    transects_list = []
    distances_list = []
    for transect in transects:
        transects_list.append(transect["transect_id"])
        distances_list.append(transect["distance"])

    for tr in transects_list:
        if path_id.startswith(tr + "_"):
            match = "OK"
            out += '<tr>'
            break
    else:
        match = "NO"
        out += '<tr class="table-danger">'

    #if match == "NO":
    td = ""
    for t,d in zip(transects_list, distances_list):
        td += f"{t} ({d} m); "
    out += f'<td>{row["scat_id"]}</td><td>{row["sampling_type"]}</td><td>{path_id}</td><td>{td}</td><td>{match}</td></tr>\n'


out += "</table>\n"

out += "</body></html>"

with open("static/systematic_scats_transects_location_50.html", "w") as f_out:
    f_out.write(out)


