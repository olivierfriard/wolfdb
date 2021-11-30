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

from .track import Track
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

    def not_valid(msg):

        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(Markup(f"<b>{msg}</b>"))
        return render_template('new_snowtrack.html',
                                title="New snow track",
                                action="/new_snowtrack",

                                form=form,
                                default_values=default_values)


    if request.method == "GET":
        form = Track()

        # get id of all transects
        form.path_id.choices = [("", "")] + [(x, x) for x in fn.all_path_id()]
        return render_template('new_snowtrack.html',
                                title="New snow track",
                                action="/new_snowtrack",
                                form=form,
                                default_values={})


    if request.method == "POST":
        form = Track(request.form)

        # get id of all paths
        form.path_id.choices = [("", "")] + [(x, x) for x in fn.all_path_id()]

        if form.validate():

            # date
            try:
                year = int(request.form['snowtrack_id'][1:2+1]) + 2000
                month = int(request.form['snowtrack_id'][3:4+1])
                day = int(request.form['snowtrack_id'][5:6+1])
                date = f"{year}-{month}-{day}"
            except Exception:
                return not_valid("The snowtrack_id value is not correct")

            # region
            track_region = fn.get_region(request.form["province"])


            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
            sql = ("INSERT INTO snow_tracks (snowtrack_id, path_id, date, sampling_season, "
                                             "location, municipality, province, region,"
                                             "observer, institution, scalp_category, "
                                             "sampling_type, days_after_snowfall, minimum_number_of_wolves,"
                                             "track_format, notes)"
                   "VALUES (%s, %s, %s, %s, "
                           "%s, %s, %s, %s, "
                           "%s, %s, %s, "
                           "%s, %s, %s, "
                           "%s, %s)")
            cursor.execute(sql,
                           [
                            request.form["snowtrack_id"],
                            request.form["path_id"],
                            date,
                            fn.sampling_season(date),
                            request.form["location"].strip(),
                            request.form["municipality"].strip(),
                            request.form["province"].strip().upper(),
                            track_region,
                            request.form["observer"],
                            request.form["institution"],
                            request.form["scalp_category"],
                            request.form["sampling_type"],
                            int(request.form["days_after_snowfall"]) if request.form["days_after_snowfall"] else None,
                            int(request.form["minimum_number_of_wolves"]) if request.form["minimum_number_of_wolves"] else None,
                            request.form["track_format"],
                            request.form["notes"]
                            ]
                           )
            connection.commit()

            return redirect("/snowtracks_list")
        else:
            return not_valid("Some values are not set or are wrong. Please check and submit again")


@app.route("/edit_snowtrack/<snowtrack_id>", methods=("GET", "POST"))
def edit_snowtrack(snowtrack_id):

    def not_valid(msg):

        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(Markup(f"<b>{msg}</b>"))
        return render_template('new_snowtrack.html',
                                title="Edit track",
                                action=f"/edit_snowtrack/{snowtrack_id}",
                                form=form,
                                default_values=default_values)


    if request.method == "GET":
        connection = fn.get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM snow_tracks WHERE snowtrack_id = %s",
                    [snowtrack_id])
        default_values = cursor.fetchone()

        form = Track(path_id=default_values["path_id"],
                     sampling_type=default_values["sampling_type"],
                     scalp_category=default_values["scalp_category"])
        # get id of all paths
        form.path_id.choices = [("", "")] + [(x, x) for x in fn.all_path_id()]
        form.notes.data = default_values["notes"]


        print(default_values["notes"])

        return render_template("new_snowtrack.html",
                            title="Edit track",
                            action=f"/edit_snowtrack/{snowtrack_id}",
                            form=form,
                            default_values=default_values)


    if request.method == "POST":
        form = Track(request.form)

        # get id of all paths
        form.path_id.choices = [("", "")] + [(x, x) for x in fn.all_path_id()]

        if form.validate():

            # date
            try:
                year = int(request.form['snowtrack_id'][1:2+1]) + 2000
                month = int(request.form['snowtrack_id'][3:4+1])
                day = int(request.form['snowtrack_id'][5:6+1])
                date = f"{year}-{month}-{day}"
            except Exception:
                return not_valid("The snowtrack_id value is not correct")

            # region
            track_region = fn.get_region(request.form["province"])


            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
            sql = ("UPDATE snow_tracks SET "
                        "snowtrack_id = %s,"
                        "path_id = %s,"
                        "date = %s,"
                        "sampling_season = %s,"
                        "location = %s,"
                        "municipality = %s,"
                        "province = %s,"
                        "region = %s,"
                        "observer = %s,"
                        "institution = %s,"
                        "scalp_category = %s,"
                        "sampling_type = %s,"
                        "days_after_snowfall = %s,"
                        "minimum_number_of_wolves = %s,"
                        "track_format = %s,"
                        "notes = %s"
                   "WHERE snowtrack_id = %s")

            cursor.execute(sql,
                           [
                            request.form["snowtrack_id"],
                            request.form["path_id"],
                            date,
                            fn.sampling_season(date),
                            request.form["location"],
                            request.form["municipality"],
                            request.form["province"].strip().upper(),
                            track_region,
                            request.form["observer"],
                            request.form["institution"],
                            request.form["scalp_category"],
                            request.form["sampling_type"],
                            request.form["days_after_snowfall"],
                            request.form["minimum_number_of_wolves"],
                            request.form["track_format"],
                            request.form["notes"],
                            snowtrack_id
                           ]
                           )
            connection.commit()

            return redirect(f"/view_snowtrack/{snowtrack_id}")
        else:
            return not_valid("Some values are not set or are wrong. Please check and submit again")


@app.route("/del_snowtrack/<snowtrack_id>")
def del_snowtrack(snowtrack_id):
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("DELETE FROM snow_tracks WHERE snowtrack_id = %s",
                   [snowtrack_id])
    connection.commit()
    return redirect("/snowtracks_list")