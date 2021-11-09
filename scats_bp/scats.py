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

from scat import Scat
import functions as fn

app = flask.Blueprint("scats", __name__, template_folder="templates")

app.debug = True


params = config()



@app.route("/scats")
def scats():
    return render_template("scats.html")




@app.route("/wa_form", methods=("POST",))
def wa_form():

    data = request.form

    return f"""
<form action="/add_wa" method="POST" style="padding-top:30px; padding-bottom:30px">

  <input type="hidden" id="scat_id" name="scat_id" value="{request.form['scat_id']}">

  <div class="form-group">
  <label for="usr">WA code/genetic ID</label>
  <input type="text" class="form-control" id="wa" name="wa">
</div>

<button type="submit" class="btn btn-primary">Add code</button>
</form>
"""


@app.route("/add_wa", methods=("POST",))
def add_wa():

    print(request.form)
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("UPDATE scat SET genetic_id = %s WHERE scat_id = %s",
                   [request.form['wa'], request.form['scat_id']])

    connection.commit()
    return redirect(f"/view_scat/{request.form['scat_id']}")





@app.route("/view_scat/<scat_id>")
def view_scat(scat_id):
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM scat WHERE scat_id = %s",
                   [scat_id])

    return render_template("view_scat.html",
                           results=cursor.fetchone())



@app.route("/scats_list")
def scats_list():
    # get all scats

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM scat ORDER BY scat_id")

    return render_template("scats_list.html",
                           results=cursor.fetchall())


@app.route("/new_scat", methods=("GET", "POST"))
def new_scat():

    if request.method == "GET":
        form = Scat()
        # get id of all paths
        form.path_id.choices = [("-", "-")] + [(x, x) for x in fn.all_path_id()]
        # get id of all snow tracks
        form.snowtrack_id.choices = [("-", "-")] + [(x, x) for x in fn.all_snow_tracks_id()]

        return render_template("new_scat.html",
                               title="New scat",
                               action=f"/new_scat",
                               form=form,
                               default_values={})

    if request.method == "POST":
        form = Scat(request.form)

        # get id of all transects
        form.path_id.choices = [("-", "-")] + [(x, x) for x in fn.all_path_id()]

        # get id of all snow tracks
        form.snowtrack_id.choices = [("-", "-")] + [(x, x) for x in fn.all_snow_tracks_id()]

        if form.validate():

            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            sql = ("INSERT INTO scat (scat_id, date, sampling_season, sampling_type, path_id, snowtrack_id, "
                   "localita, comune, provincia, "
                   "deposition, matrix,collected_scat, "
                   "coord_east, coord_north, rilevatore_ente, scalp_category) "
                   "VALUES (%s, %s, %s, %s,%s, %s, %s, %s,%s, %s, %s, %s,%s, %s, %s, %s)")
            cursor.execute(sql,
                           [
                            request.form["scat_id"],
                            request.form["date"],
                            fn.sampling_season(request.form["date"]),
                            request.form["sampling_type"],
                            request.form["path_id"],
                            request.form["snowtrack_id"],
                            request.form["localita"], request.form["comune"], request.form["provincia"],
                            request.form["deposition"], request.form["matrix"], request.form["collected_scat"],
                            request.form["coord_east"], request.form["coord_north"],
                            request.form["rilevatore_ente"], request.form["scalp_category"]
                           ]
                           )

            connection.commit()

            return redirect("/scats_list")
        else:
            # default values
            default_values = {}
            for k in request.form:
                default_values[k] = request.form[k]

            flash(Markup("<b>Some values are not set or are wrong. Please check and submit again</b>"))

            return render_template("new_scat.html",
                                   title="New scat",
                                   action=f"/new_scat",
                                   form=form,
                                   default_values=default_values)



@app.route("/edit_scat/<scat_id>", methods=("GET", "POST"))
def edit_scat(scat_id):

    if request.method == "GET":
        connection = fn.get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM scat WHERE scat_id = %s",
                    [scat_id])
        default_values = cursor.fetchone()

        form = Scat(path_id=default_values["path_id"],
                    snowtrack_id=default_values["snowtrack_id"],
                    sampling_type=default_values["sampling_type"],
                    deposition=default_values["deposition"],
                    matrix=default_values["matrix"],
                    collected_scat=default_values["collected_scat"])

        # get id of all paths
        form.path_id.choices = [("-", "-")] + [(x, x) for x in fn.all_path_id()]
        # get id of all snow tracks
        form.snowtrack_id.choices = [("-", "-")] + [(x, x) for x in fn.all_snow_tracks_id()]

        return render_template("new_scat.html",
                            title="Edit scat",
                            action=f"/edit_scat/{scat_id}",
                            form=form,
                            default_values=default_values)


    if request.method == "POST":

        form = Scat(request.form)

        # get id of all paths
        form.path_id.choices = [("-", "-")] + [(x, x) for x in fn.all_path_id()]

        # get id of all snow tracks
        form.snowtrack_id.choices = [("-", "-")] + [(x, x) for x in fn.all_snow_tracks_id()]

        if form.validate():

            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            sql = ("UPDATE scat SET scat_id = %s, "
                   "                date = %s,"
                   "                sampling_season = %s,"
                   "                sampling_type = %s,"
                   "                path_id = %s, "
                   "                snowtrack_id = %s, "
                   "                localita = %s, "
                   "                comune = %s, "
                   "                provincia = %s, "
                   "                deposition = %s, "
                   "                matrix = %s, "
                   "                collected_scat = %s, "
                   "                coord_east = %s, "
                   "                coord_north = %s, "
                   "                rilevatore_ente = %s, "
                   "                scalp_category = %s "
                   "WHERE scat_id = %s")
            cursor.execute(sql,
                           [
                            request.form["scat_id"],
                            request.form["date"],
                            fn.sampling_season(request.form["date"]),
                            request.form["sampling_type"],
                            request.form["path_id"],
                            request.form["snowtrack_id"],
                            request.form["localita"], request.form["comune"], request.form["provincia"],
                            request.form["deposition"], request.form["matrix"], request.form["collected_scat"],
                            request.form["coord_east"], request.form["coord_north"],
                            request.form["rilevatore_ente"], request.form["scalp_category"],
                            scat_id
                           ]
                           )

            connection.commit()

            return redirect(f"/view_scat/{scat_id}")
        else:
            # default values
            default_values = {}
            for k in request.form:
                default_values[k] = request.form[k]

            flash(Markup("<b>Some values are not set or are wrong. Please check and submit again</b>"))

            return render_template("new_scat.html",
                                   title="Edit scat",
                                   action=f"/edit_scat/{scat_id}",
                                   form=form,
                                   default_values=default_values)
