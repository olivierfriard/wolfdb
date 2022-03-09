"""
create file static/systematic_scats_transects_location.html

The output file contains the closest transect for every systematic scat

This script is required by wolfdb.py


see https://gist.github.com/NihalHarish/8597e5691889cd719e6c to improve with multiprocessing

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
<title>Check systematic scats locations - WolfDB</title>

<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-1BmE4kWBq78iYhFldvKuhfTAU6auU8tT94WrHftjDbrCEXSU1oBoqyl2QvZ6jIW3" crossorigin="anonymous">

<style>main > .container {  padding: 60px 15px 0;}</style>

</head>
"""

try:
    with open("templates/dev_style.html", "r") as f_in:
        out += f"<style>{f_in.read()}</style>"
except Exception:
    pass

connection = fn.get_connection()
cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

cursor.execute(
    (
        "SELECT scat_id, sampling_type, path_id, snowtrack_id, st_x(geometry_utm)::integer AS x, st_y(geometry_utm)::integer AS y "
        "FROM scats "
        "WHERE sampling_type != 'Opportunistic' "
    )
)
scats = cursor.fetchall()

out2 = ""
c = 0
for row in scats:

    # check if transect_id exists
    if "|" in row["path_id"]:
        transect_id_to_search = row["path_id"].split("|")[0]
        cursor.execute("SELECT transect_id FROM transects WHERE transect_id = %s", [transect_id_to_search])
        row2 = cursor.fetchone()
        if row2 is not None:
            transect_id_found = row2["transect_id"]
        else:
            transect_id_found = ""
    else:
        transect_id_found = ""

    # check if track ID exists
    track_id_to_search = row["snowtrack_id"]
    cursor.execute("SELECT snowtrack_id FROM snow_tracks WHERE snowtrack_id = %s", [track_id_to_search])
    row3 = cursor.fetchone()
    if row3 is not None:
        track_id_found = row3["snowtrack_id"]
    else:
        track_id_found = ""

    sql = (
        f" SELECT snowtrack_id, st_distance(ST_GeomFromText('POINT({row['x']} {row['y']})',32632), multilines)::integer AS distance "
        "FROM snow_tracks "
        f"WHERE multilines is not null "
        f"AND st_distance(ST_GeomFromText('POINT({row['x']} {row['y']})',32632), multilines) = (SELECT min(st_distance(ST_GeomFromText('POINT({row['x']} {row['y']})',32632), multilines)) FROM snow_tracks) "
    )
    cursor.execute(sql)
    track = cursor.fetchone()
    print(f"{track=}")

    sql = (
        f" SELECT transect_id, st_distance(ST_GeomFromText('POINT({row['x']} {row['y']})',32632), multilines)::integer AS distance "
        "FROM transects "
        f"WHERE st_distance(ST_GeomFromText('POINT({row['x']} {row['y']})',32632), multilines) = (SELECT min(st_distance(ST_GeomFromText('POINT({row['x']} {row['y']})',32632), multilines)) FROM transects) "
    )

    cursor.execute(sql)
    transect = cursor.fetchone()

    path_id = row["path_id"].replace(" ", "|")

    if path_id.startswith(transect["transect_id"] + "|"):
        match = "OK"
        out2 += "<tr>"
    else:
        match = "NO"
        c += 1
        out2 += '<tr class="table-danger">'

        sql = "SELECT path_id FROM paths WHERE path_id = %s  "
        cursor.execute(sql, [transect["transect_id"] + "|" + row["scat_id"][1:7]])
        results = cursor.fetchone()
        if results is not None:
            new_path_id = results["path_id"]
        else:
            new_path_id = f"""path ID {transect['transect_id'] + "|" + row['scat_id'][1:7]} NOT FOUND"""

        transect["transect_id"]

    if match == "NO":

        if "NOT FOUND" in new_path_id:
            out2 += (
                f"""<td><a href="/view_scat/{row['scat_id']}">{row['scat_id']}</a></td>"""
                f"""<td>{row['sampling_type']}</td>"""
                f"""<td><a href="/view_path/{row['path_id']}">{path_id}</a></td>"""
                f"""<td>{'<b>NOT FOUND</b>' if transect_id_found == '' else transect_id_found}</td>"""
                f"""<td><a href="/view_transect/{transect['transect_id']}">{transect['transect_id']}</a></td>"""
                f"""<td>{transect['distance']}</td>"""
                f"""<td>{new_path_id}</td>"""
            )

        else:
            out2 += (
                f"""<td><a href="/view_scat/{row['scat_id']}">{row['scat_id']}</a></td>"""
                f"""<td>{row['sampling_type']}</td>"""
                f"""<td><a href="/view_path/{row['path_id']}">{path_id}</a></td>"""
                f"""<td>{'<b>NOT FOUND</b>' if transect_id_found == '' else transect_id_found}</td>"""
                f"""<td><a href="/view_transect/{transect['transect_id']}">{transect['transect_id']}</a></td>"""
                f"""<td>{transect['distance']}</td>"""
                f"""<td><a class="btn btn-danger btn-small" href="/set_path_id/{row['scat_id']}/{new_path_id}" onclick="return confirm('Are you sure to set the path ID?')">Set {new_path_id} as path ID</a></td>"""
            )


out += "<h1>Location on transects for systematic scats</h1>\n"

out += f"Check done at {datetime.datetime.now().replace(microsecond=0).isoformat().replace('T', ' ')}<br><br>\n"


out += '<a href="/systematic_scats_transect_location" class="btn btn-primary">Update data</a><br><br>'


out += f"{len(scats)} scats (sampling type &ne; Opportunistic).<br>\n"

out += f"{c} scat positions that do not match the transect ID.<br>\n"

out += '<table class="table table-striped">\n'

out += "<tr><th>Scat ID</th><th>Sampling type</th><th>Path ID</th><th>Current transect ID</th><th>Closer Transect ID</th><th>Distance (m)</th><th>Action</th></tr>"

out += out2


out += "</table>\n"

out += "</body></html>"

with open("static/systematic_scats_transects_location.html", "w") as f_out:
    f_out.write(out)
