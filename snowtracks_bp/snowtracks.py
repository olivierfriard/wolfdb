"""
WolfDB web service
(c) Olivier Friard

flask blueprint for scats management
"""



import flask
from flask import Flask, render_template, redirect, request, Markup, flash, session
import psycopg2
import psycopg2.extras
from config import config

from track import Track
import functions as fn

app = flask.Blueprint("snowtracks", __name__, template_folder="templates")

app.debug = True


params = config()

@app.route("/snow_tracks")
def snow_tracks():
    return render_template("snow_tracks.html")


@app.route("/view_snowtrack/<snowtrack_id>")
def view_snowtrack(snowtrack_id):
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM snow_tracks WHERE snowtrack_id = %s",
                   [snowtrack_id])

    return render_template("view_snowtrack.html",
                           results=cursor.fetchone())



@app.route("/snowtracks_list")
def snowtracks_list():
    # get  all tracks
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM snow_tracks ORDER BY date DESC")

    results = cursor.fetchall()

    return render_template("snowtracks_list.html",
                           results=results)



@app.route("/new_snowtrack", methods=("GET", "POST"))
def new_snowtrack():


    if request.method == "GET":
        form = Track()

        # get id of all transects
        form.path_id.choices = [("-", "-")] + [(x, x) for x in fn.all_path_id()]
        return render_template('new_snowtrack.html',
                                title="New snow track",
                                action="/new_snowtrack",
                                form=form,
                                default_values={})


    if request.method == "POST":
        form = Track(request.form)

        # get id of all path
        form.path_id.choices = [("-", "-")] + [(x, x) for x in fn.all_path_id()]

        if form.validate():

            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
            sql = ("INSERT INTO snow_tracks (snowtrack_id, path_id, date, sampling_season, comune, "
                                             "provincia, regione, rilevatore, scalp_category, "
                                             "systematic_sampling, giorni_dopo_nevicata, n_minimo_individui, track_format) "
                   "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
            cursor.execute(sql,
                           [
                            request.form["snowtrack_id"],
                            request.form["path_id"],
                            request.form["date"],
                            fn.sampling_season(request.form["date"]),
                            request.form["comune"],
                            request.form["provincia"].upper(),
                            request.form["regione"],
                            request.form["rilevatore"],
                            request.form["scalp_category"],
                            request.form["systematic_sampling"],
                            request.form["giorni_dopo_nevicata"],
                            request.form["n_minimo_individui"],
                            request.form["track_format"],
                            ]
                           )
            connection.commit()

            return redirect("/snowtracks_list")
        else:
            # default values
            default_values = {}
            for k in request.form:
                default_values[k] = request.form[k]

            flash(Markup("<b>Some values are not set or are wrong. Please check and submit again</b>"))
            return render_template('new_snowtrack.html',
                                   title="New snow track",
                                   action="/new_snowtrack",

                                    form=form,
                                    default_values=default_values)



@app.route("/edit_snowtrack/<snowtrack_id>", methods=("GET", "POST"))
def edit_snowtrack(snowtrack_id):

    if request.method == "GET":
        connection = fn.get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM snow_tracks WHERE snowtrack_id = %s",
                    [snowtrack_id])
        default_values = cursor.fetchone()

        form = Track(path_id=default_values["path_id"],
                     systematic_sampling=default_values["systematic_sampling"])
        # get id of all paths
        form.path_id.choices = [("-", "-")] + [(x, x) for x in fn.all_path_id()]

        return render_template("new_snowtrack.html",
                            title="Edit track",
                            action=f"/edit_snowtrack/{snowtrack_id}",
                            form=form,
                            default_values=default_values)


    if request.method == "POST":
        form = Track(request.form)

        # get id of all transects
        form.path_id.choices = [("-", "-")] + [(x, x) for x in fn.all_path_id()]

        if form.validate():

            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
            sql = ("UPDATE snow_tracks SET "
                        "snowtrack_id = %s,"
                        "path_id = %s,"
                        "date = %s,"
                        "sampling_season = %s,"
                        "comune = %s,"
                        "provincia = %s,"
                        "regione = %s,"
                        "rilevatore = %s,"
                        "scalp_category = %s,"
                        "systematic_sampling = %s,"
                        "giorni_dopo_nevicata = %s,"
                        "n_minimo_individui = %s,"
                        "track_format = %s"
                   "WHERE snowtrack_id = %s")

            cursor.execute(sql,
                           [
                            request.form["snowtrack_id"],
                            request.form["path_id"],
                            request.form["date"],
                            fn.sampling_season(request.form["date"]),
                            request.form["comune"],
                            request.form["provincia"],
                            request.form["regione"],
                            request.form["rilevatore"],
                            request.form["scalp_category"],
                            request.form["systematic_sampling"],
                            request.form["giorni_dopo_nevicata"],
                            request.form["n_minimo_individui"],
                            request.form["track_format"],
                            snowtrack_id
                           ]
                           )
            connection.commit()

            return redirect(f"/view_snowtrack/{snowtrack_id}")
        else:
            # default values
            default_values = {}
            for k in request.form:
                default_values[k] = request.form[k]

            flash(Markup("<b>Some values are not set or are wrong. Please check and submit again</b>"))
            return render_template('new_snowtrack.html',
                                    title="Edit track",
                                    action=f"/edit_snowtrack/{snowtrack_id}",
                                    form=form,
                                    default_values=default_values)
