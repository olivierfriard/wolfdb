"""
create file static/systematic_scats_transects_location.html

The output file contains the closest transect for every systematic scat

This script is required by wolfdb.py


see https://gist.github.com/NihalHarish/8597e5691889cd719e6c to improve with multiprocessing

"""

from sqlalchemy import text
import functions as fn
import datetime
import os
import sys
import time
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

start_date = sys.argv[1]
end_date = sys.argv[2]
output_file_path = sys.argv[3]


LOCK_FILE_NAME_PATH = "check_location.lock"

# verify if lock exist and age of lock file
if os.path.exists(LOCK_FILE_NAME_PATH) and (
    time.time() - os.path.getctime(LOCK_FILE_NAME_PATH) < 1800
):
    print("Check systematic locations already running. Exiting")
    sys.exit()

# create lock file
with open(LOCK_FILE_NAME_PATH, "w") as f_out:
    f_out.write(datetime.datetime.now().isoformat())

output: str = ""


with fn.conn_alchemy().connect() as con:
    scats = (
        con.execute(
            text(
                (
                    "SELECT scat_id, sampling_type, path_id, snowtrack_id, st_x(geometry_utm)::integer AS x, st_y(geometry_utm)::integer AS y "
                    "FROM scats "
                    "WHERE sampling_type != 'Opportunistic' "
                    "AND date between :start_date AND :end_date "
                )
            ),
            {
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        .mappings()
        .all()
    )

    out2 = ""
    c = 0
    for row in scats:
        # check if transect_id exists
        if "|" in row["path_id"]:
            transect_id_to_search = row["path_id"].split("|")[0]
            row2 = (
                con.execute(
                    text(
                        "SELECT transect_id FROM transects WHERE transect_id = :transect_id_to_search"
                    ),
                    {"transect_id_to_search": transect_id_to_search},
                )
                .mappings()
                .fetchone()
            )
            if row2 is not None:
                transect_id_found = row2["transect_id"]
            else:
                transect_id_found = ""
        else:
            transect_id_found = ""

        # check if track ID exists
        track_id_to_search = row["snowtrack_id"]
        row3 = (
            con.execute(
                text(
                    "SELECT snowtrack_id FROM snow_tracks WHERE snowtrack_id = :track_id_to_search"
                ),
                {"track_id_to_search": track_id_to_search},
            )
            .mappings()
            .fetchone()
        )
        if row3 is not None:
            track_id_found = row3["snowtrack_id"]
        else:
            track_id_found = ""

        sql = text(
            (
                f" SELECT snowtrack_id, st_distance(ST_GeomFromText('POINT({row['x']} {row['y']})',32632), multilines)::integer AS distance "
                "FROM snow_tracks "
                f"WHERE multilines is not null "
                f"AND st_distance(ST_GeomFromText('POINT({row['x']} {row['y']})',32632), multilines) = (SELECT min(st_distance(ST_GeomFromText('POINT({row['x']} {row['y']})',32632), multilines)) FROM snow_tracks) "
            )
        )
        track = con.execute(sql).mappings().fetchone()

        sql = text(
            (
                f" SELECT transect_id, st_distance(ST_GeomFromText('POINT({row['x']} {row['y']})',32632), multilines)::integer AS distance "
                "FROM transects "
                f"WHERE st_distance(ST_GeomFromText('POINT({row['x']} {row['y']})',32632), multilines) = (SELECT min(st_distance(ST_GeomFromText('POINT({row['x']} {row['y']})',32632), multilines)) FROM transects) "
            )
        )

        transect = con.execute(sql).mappings().fetchone()

        path_id = row["path_id"].replace(" ", "|")

        if path_id.startswith(transect["transect_id"] + "|"):
            match = "OK"
            out2 += "<tr>"
        else:
            match = "NO"
            c += 1
            out2 += '<tr class="table-danger">'

            sql = text("SELECT path_id FROM paths WHERE path_id = :transect_scat")
            results = (
                con.execute(
                    sql,
                    {
                        "transect_scat": transect["transect_id"]
                        + "|"
                        + row["scat_id"][1:7]
                    },
                )
                .mappings()
                .fetchone()
            )
            if results is not None:
                new_path_id = results["path_id"]
            else:
                new_path_id = f"""path ID {transect["transect_id"] + "|" + row["scat_id"][1:7]} NOT FOUND"""

            transect["transect_id"]

        if match == "NO":
            if "NOT FOUND" in new_path_id:
                out2 += (
                    f"""<td><a href="/view_scat/{row["scat_id"]}">{row["scat_id"]}</a></td>"""
                    f"""<td>{row["sampling_type"]}</td>"""
                    f"""<td><a href="/view_path/{row["path_id"]}">{path_id}</a></td>"""
                    f"""<td>{"<b>NOT FOUND</b>" if transect_id_found == "" else transect_id_found}</td>"""
                    f"""<td><a href="/view_transect/{transect["transect_id"]}">{transect["transect_id"]}</a></td>"""
                    f"""<td>{transect["distance"]}</td>"""
                    f"""<td>{new_path_id}</td>"""
                )

            else:
                out2 += (
                    f"""<td><a href="/view_scat/{row["scat_id"]}">{row["scat_id"]}</a></td>"""
                    f"""<td>{row["sampling_type"]}</td>"""
                    f"""<td><a href="/view_path/{row["path_id"]}">{path_id}</a></td>"""
                    f"""<td>{"<b>NOT FOUND</b>" if transect_id_found == "" else transect_id_found}</td>"""
                    f"""<td><a href="/view_transect/{transect["transect_id"]}">{transect["transect_id"]}</a></td>"""
                    f"""<td>{transect["distance"]}</td>"""
                    f"""<td><a class="btn btn-danger btn-small" href="/set_path_id/{row["scat_id"]}/{new_path_id}" onclick="return confirm('Are you sure to set the path ID?')">Set {new_path_id} as path ID</a></td>"""
                )

            if track_id_found:
                out2 += f"""<td><a href="/view_track/{row["snowtrack_id"]}">{row["snowtrack_id"]}</a></td>"""
            else:
                if row["snowtrack_id"]:
                    out2 += f"""<td>{row["snowtrack_id"]} NOT FOUND IN DB</a></td>"""
                else:
                    out2 += "<td></td>"

            out2 += (
                f"""<td>{track["snowtrack_id"]}</td>""" f"<td>{track['distance']}</td>"
            )


output += f"Check done at {datetime.datetime.now().replace(microsecond=0).isoformat().replace('T', ' ')}<br><br>\n"


output += f"{len(scats)} scats (sampling type &ne; Opportunistic).<br>\n"

output += f"{c} scat positions that do not match the transect ID.<br><br>\n"

output += '<table class="table table-striped">\n'

output += "<tr><th>Scat ID</th><th>Sampling type</th><th>Path ID</th><th>Current transect ID</th><th>Closer Transect ID</th><th>Distance (m)</th><th>Action</th><th>Current track ID</th><th>Closer Track ID</th><th>Distance to closer track ID</th></tr>"

output += out2


output += "</table>\n"


env = Environment(
    loader=FileSystemLoader("templates/"),
)
template = env.get_template("page.html")

with open(f"{output_file_path}", "w") as f_out:
    f_out.write(
        template.render(
            header_title="Location of scats on transects and tracks",
            title="Location of scats on transects and tracks",
            content=Markup(output),
        )
    )

if os.path.exists(LOCK_FILE_NAME_PATH):
    os.remove(LOCK_FILE_NAME_PATH)
