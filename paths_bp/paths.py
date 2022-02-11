"""
WolfDB web service
(c) Olivier Friard

flask blueprint for paths management
"""



import flask
from flask import Flask, render_template, redirect, request, Markup, flash, session, make_response
import psycopg2
import psycopg2.extras
from config import config
import json

from .path_form import Path
import functions as fn
from . import paths_export

app = flask.Blueprint("paths", __name__, template_folder="templates")

app.debug = True


params = config()

@app.route("/paths")
@fn.check_login
def paths():
    return render_template("paths.html",
                            header_title="Paths")


@app.route("/view_path/<path_id>")
@fn.check_login
def view_path(path_id):
    """
    Display path data
    """

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute(("SELECT *, "
                    "(SELECT count(*) FROM scats WHERE scats.path_id=paths.path_id) AS n_scats "
                    "FROM paths WHERE path_id = %s"),
                   [path_id])
    path = cursor.fetchone()
    if path is None:
        return render_template("view_path.html",
                               header_title=f"{path_id} not found",
                               path={"path_id": ""},
                               path_id=path_id
                               )

    # relative transect
    transect_id = path["transect_id"]
    cursor.execute(("SELECT *, ST_AsGeoJSON(st_transform(multilines, 4326)) AS transect_geojson, "
                    "ROUND(ST_Length(multilines)) AS transect_length "
                    "FROM transects "
                    "WHERE transect_id = %s"),
                    [transect_id])
    transect = cursor.fetchone()
    if transect is not None:

        transect_geojson = json.loads(transect["transect_geojson"])

        transect_feature = {"type": "Feature",
                            "geometry": dict(transect_geojson),
                            "properties": {
                            "popupContent": transect_id
                                        },
                            "id": 1
                        }
        transect_features = [transect_feature]
        center = f"{transect_geojson['coordinates'][0][1]}, {transect_geojson['coordinates'][0][0]}"

    else:
        transect_features = []
        center = ""

    # scats
    cursor.execute(("SELECT *, ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat, "
                    "ROUND(st_x(st_transform(geometry_utm, 4326))::numeric, 6) as longitude, "
                    "ROUND(st_y(st_transform(geometry_utm, 4326))::numeric, 6) as latitude "
                    "FROM scats WHERE path_id = %s"
                   ),
                   [path_id])

    scats = cursor.fetchall()
    scat_features = []
    for scat in scats:

        scat_geojson = json.loads(scat["scat_lonlat"])

        scat_feature = {"geometry": dict(scat_geojson),
                    "type": "Feature",
                    "properties": {
  "popupContent": f"""Scat ID: <a href="/view_scat/{scat['scat_id']}" target="_blank">{scat['scat_id']}</a>"""
                                  },
                    "id": scat["scat_id"]
                   }

        scat_features.append(scat_feature)

        center = f"{scat['latitude']}, {scat['longitude']}"


    # n tracks
    cursor.execute("SELECT COUNT(*) AS n_tracks FROM snow_tracks WHERE transect_id = %s",  [path_id])
    n_tracks = cursor.fetchone()["n_tracks"]


    return render_template("view_path.html",
                           header_title=f"path ID: {path_id}",
                           path=path,
                           n_tracks=n_tracks,
                           path_id=path_id,
                           map=Markup(fn.leaflet_geojson(center, scat_features, transect_features)))


@app.route("/paths_list")
@fn.check_login
def paths_list():
    # get all paths
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute(("SELECT *, "
                    #"(SELECT province FROM transects WHERE transects.transect_id = paths.transect_id LIMIT 1) AS province, "
                    "(SELECT region FROM transects WHERE transects.transect_id = paths.transect_id LIMIT 1) AS region, "
                    "(SELECT COUNT(*) FROM scats WHERE path_id = paths.path_id) AS n_samples, "
                    "(SELECT COUNT(*) FROM snow_tracks WHERE transect_id = paths.transect_id AND date = paths.date) AS n_tracks "
                   "FROM paths "
                   "ORDER BY region ASC, "
                   #"province ASC, "
                   "path_id, date DESC "
                   ))


    '''
    cursor.execute(("SELECT *, "
                    "(SELECT COUNT(*) FROM scats WHERE path_id = paths.path_id) AS n_samples, "
                    "(SELECT COUNT(*) FROM snow_tracks WHERE transect_id = paths.transect_id AND date = paths.date) AS n_tracks "

                    "FROM paths, transects "
                    "WHERE paths.transect_id = transects.transect_id ORDER by region ASC, province ASC, date DESC")
    )
    '''


    results = cursor.fetchall()

    # count paths
    n_paths = len(results)

    return render_template("paths_list.html",
                           header_title="List of paths",
                           n_paths=n_paths,
                           results=results,
                          )


@app.route("/export_paths")
@fn.check_login
def export_paths():

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute(("SELECT *, "
                    "(SELECT province FROM transects WHERE transects.transect_id = paths.transect_id LIMIT 1) AS province, "
                    "(SELECT region FROM transects WHERE transects.transect_id = paths.transect_id LIMIT 1) AS region, "
                    "(SELECT COUNT(*) FROM scats WHERE path_id = paths.path_id) AS n_samples, "
                    "(SELECT COUNT(*) FROM snow_tracks WHERE transect_id = paths.transect_id AND date = paths.date) AS n_tracks "
                   "FROM paths "
                   "ORDER BY region ASC, "
                   "province ASC, "
                   "path_id, date DESC "
                   ))

    file_content = paths_export.export_paths(cursor.fetchall())

    response = make_response(file_content, 200)
    response.headers["Content-type"] = "application/application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    response.headers["Content-disposition"] = "attachment; filename=paths.xlsx"

    return response



@app.route("/new_path", methods=("GET", "POST"))
@fn.check_login
def new_path():

    def not_valid(msg):
        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(fn.alert_danger(f"<b>{msg}</b>"))

        return render_template("new_path.html",
                                header_title="Insert a new path",
                                title="New path",
                                action=f"/new_path",
                                form=form,
                                default_values=default_values)



    if request.method == "GET":
        form = Path()

        # get id of all transects
        form.transect_id.choices = [("", "")] + [(x, x) for x in fn.all_transect_id()]

        return render_template("new_path.html",
                               header_title="Insert a new path",
                               title="New path",
                               action=f"/new_path",
                               form=form,
                               default_values={})

    if request.method == "POST":


        form = Path(request.form)

        # get id of all transects
        form.transect_id.choices = [("", "")] + [(x, x) for x in fn.all_transect_id()]

        if form.validate():

            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            # path_id
            path_id = f'{request.form["transect_id"]}|{request.form["date"][2:].replace("-", "")}'

            # check if path_id already exists
            cursor.execute("SELECT path_id FROM paths WHERE path_id = %s", [path_id])
            if cursor.fetchone() is not None:
                return not_valid(f"The path ID {path_id} already exists")

            # check completness
            if not (0 < int(request.form["completeness"]) <= 100):
                return not_valid(f"Completeness must be an integer like 0 < completeness <= 100")

            sql = ("INSERT INTO paths (path_id, transect_id, date, sampling_season, completeness, "

                   "observer, institution, notes) "
                   "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)")
            cursor.execute(sql,
                           [path_id,
                            request.form["transect_id"],
                            request.form["date"],
                            fn.sampling_season(request.form["date"]),
                            request.form["completeness"] if request.form["completeness"] else None,
                            request.form["observer"], request.form["institution"], request.form["notes"]
                           ]
                           )
            connection.commit()

            return redirect("/paths_list")

        else:

            return not_valid("Some values are not set or are wrong. Please check and submit again")




@app.route("/edit_path/<path_id>", methods=("GET", "POST"))
@fn.check_login
def edit_path(path_id):

    if request.method == "GET":
        connection = fn.get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM paths WHERE path_id = %s",
                       [path_id])
        default_values = cursor.fetchone()

        if default_values["category"] is None:
            default_values["category"] = ""

        form = Path(transect_id=default_values["transect_id"],
                    completeness=default_values["completeness"],
                    )
        # get id of all transects
        form.transect_id.choices = [("", "")] + [(x, x) for x in fn.all_transect_id()]
        form.notes.data = default_values["notes"]

        return render_template("new_path.html",
                               header_title=f"Edit path {path_id}",
                               title="Edit path",
                               action=f"/edit_path/{path_id}",
                               form=form,
                               default_values=default_values)


    if request.method == "POST":
        form = Path(request.form)

        # get id of all transects
        form.transect_id.choices = [("", "")] + [(x, x) for x in fn.all_transect_id()]

        if form.validate():

            # path_id
            new_path_id = f'{request.form["transect_id"]}|{request.form["date"][2:].replace("-", "")}'

            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
            sql = ("UPDATE paths SET "
                   "path_id = %s,"
                   "transect_id = %s, "
                   "date = %s, "
                   "sampling_season = %s, "
                   "completeness = %s, "
                   "observer = %s, "
                   "institution = %s, "
                   "category = %s, "
                   "notes = %s "
                   "WHERE path_id = %s")

            cursor.execute(sql,
                           [new_path_id,
                            request.form["transect_id"],
                            request.form["date"],
                            fn.sampling_season(request.form["date"]),
                            request.form["completeness"] if request.form["completeness"] else None,
                            request.form["observer"], request.form["institution"],
                            request.form["category"],
                            request.form["notes"],
                            path_id
                           ]
                           )
            connection.commit()

            return redirect(f"/view_path/{new_path_id}")
        else:
            # default values
            default_values = {}
            for k in request.form:
                default_values[k] = request.form[k]

            flash(Markup("<b>Some values are not set or are wrong. Please check and submit again</b>"))
            return render_template("new_path.html",
                                    title="Edit path",
                                    action=f"/edit_path/{path_id}",
                                    form=form,
                                    default_values=default_values)


@app.route("/del_path/<path_id>")
@fn.check_login
def del_path(path_id):
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("DELETE FROM paths WHERE path_id = %s",
                   [path_id])
    connection.commit()
    return redirect("/paths_list")