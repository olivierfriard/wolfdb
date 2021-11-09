"""
WolfDB web service
(c) Olivier Friard

flask blueprint for paths management
"""



import flask
from flask import Flask, render_template, redirect, request, Markup, flash, session
import psycopg2
import psycopg2.extras
from config import config

from path import Path
import functions as fn

app = flask.Blueprint("paths", __name__, template_folder="templates")

app.debug = True


params = config()

@app.route("/paths")
def paths():
    return render_template("paths.html")


@app.route("/view_path/<id>")
def view_path(id):
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM paths WHERE concat(transect_id, ' ', date) = %s",
                   [id])

    results = cursor.fetchone()

    # n samples
    path_id = f'{results["transect_id"]} {results["date"]}'
    cursor.execute("SELECT COUNT(*) AS n_samples FROM scat WHERE path_id = %s ", [path_id])
    n_samples = cursor.fetchone()["n_samples"]

    # n tracks
    path_id = f'{results["transect_id"]} {results["date"]}'
    cursor.execute("SELECT COUNT(*) AS n_tracks FROM snow_tracks WHERE path_id = %s",
    [f'{results["id"]} {results["date"]}'])
    n_tracks = cursor.fetchone()["n_tracks"]


    return render_template("view_path.html",
                           results=results,
                           n_samples=n_samples,
                           n_tracks=n_tracks)


@app.route("/paths_list")
def paths_list():
    # get  all paths
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute(("SELECT *, "
                    "(SELECT COUNT(*) FROM scat WHERE path_id = CONCAT(paths.transect_id, ' ', paths.date)) AS n_samples, "
                    "(SELECT COUNT(*) FROM snow_tracks WHERE transect_id = paths.transect_id AND date = paths.date) AS n_tracks "
                   "FROM paths ORDER BY date DESC"
                   ))

    results = cursor.fetchall()
    return render_template("paths_list.html",
                           results=results,
                            )




@app.route("/new_path", methods=("GET", "POST"))
def new_path():

    if request.method == "GET":
        form = Path()

        # get id of all transects
        form.transect_id.choices = [("-", "-")] + [(x, x) for x in fn.all_transect_id()]

        return render_template("new_path.html",
                               title="New path",
                               action=f"/new_path",
                               form=form,
                               default_values={})

    if request.method == "POST":
        form = Path(request.form)

        # get id of all transects
        form.transect_id.choices = [("-", "-")] + [(x, x) for x in fn.all_transect_id()]

        if form.validate():

            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
            sql = ("INSERT INTO paths (transect_id, date, sampling_season, completeness, "
                   #"numero_segni_trovati, numero_campioni, "
                   "operatore, note) "
                   "VALUES (%s, %s, %s, %s, %s, %s)")
            cursor.execute(sql,
                           [
                            request.form["transect_id"],
                            request.form["date"],
                            fn.sampling_season(request.form["date"]),
                            request.form["completeness"] if request.form["completeness"] else None,
                            #request.form["numero_segni_trovati"] if request.form["numero_segni_trovati"] else None,
                            #request.form["numero_campioni"] if request.form["numero_campioni"] else None,
                            request.form["operatore"], request.form["note"]
                           ]
                           )
            connection.commit()

            return redirect("/paths_list")
        else:
            # default values
            default_values = {}
            for k in request.form:
                default_values[k] = request.form[k]

            flash(Markup("<b>Some values are not set or are wrong. Please check and submit again</b>"))
            return render_template('new_path.html',
                                    title="New path",
                                    action=f"/new_path",
                                    form=form,
                                    default_values=default_values)





@app.route("/edit_path/<id>", methods=("GET", "POST"))
def edit_path(id):

    if request.method == "GET":
        connection = fn.get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM paths WHERE concat(transect_id, ' ', date) = %s",
                    [id])
        default_values = cursor.fetchone()

        form = Path(transect_id=default_values["transect_id"],)
        # get id of all transects
        form.transect_id.choices = [("-", "-")] + [(x, x) for x in fn.all_transect_id()]


        return render_template("new_path.html",
                            title="Edit path",
                            action=f"/edit_path/{id}",
                            form=form,
                            default_values=default_values)


    if request.method == "POST":
        form = Path(request.form)

        # get id of all transects
        form.transect_id.choices = [("-", "-")] + [(x, x) for x in fn.all_transect_id()]

        if form.validate():

            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
            sql = ("UPDATE paths SET "
                   "transect_id=%s, "
                   "date=%s, "
                   "sampling_season=%s, "
                   "completeness=%s, "
                   #"numero_segni_trovati=%s, "
                   #"numero_campioni=%s, "
                   "operatore=%s, "
                   "note=%s "
                   "WHERE concat(transect_id, ' ', date) = %s")

            cursor.execute(sql,
                           [
                            request.form["transect_id"],
                            request.form["date"],
                            fn.sampling_season(request.form["date"]),
                            request.form["completeness"] if request.form["completeness"] else None,
                            #request.form["numero_segni_trovati"] if request.form["numero_segni_trovati"] else None,
                            #request.form["numero_campioni"] if request.form["numero_campioni"] else None,
                            request.form["operatore"], request.form["note"],
                            id
                           ]
                           )
            connection.commit()

            return redirect(f"/view_path/{id}")
        else:
            # default values
            default_values = {}
            for k in request.form:
                default_values[k] = request.form[k]

            flash(Markup("<b>Some values are not set or are wrong. Please check and submit again</b>"))
            return render_template("new_path.html",
                                    title="Edit path",
                                    action=f"/edit_path/{id}",
                                    form=form,
                                    default_values=default_values)


@app.route("/del_path/<id>")
def del_path(id):
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("DELETE FROM paths WHERE id = %s",
                   [id])
    connection.commit()
    return redirect("/paths_list")