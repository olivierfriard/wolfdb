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

#from dead_wolf import Dead_wolf
import functions as fn
from italian_regions import regions

app = flask.Blueprint("dead_wolves", __name__, template_folder="templates")

app.debug = True


params = config()

@app.route("/dead_wolves")
def transects():
    return render_template("dead_wolves.html")


@app.route("/view_dead_wolf/<tissue_id>")
def view_dead_wolf(tissue_id):
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM dead_wolves WHERE tissue_id = %s",
                   [tissue_id])
    dead_wolf = cursor.fetchone()

    return render_template("view_dead_wolf.html",
                           dead_wolf=dead_wolf,
                          )


@app.route("/dead_wolves_list")
def dead_wolves_list():
    # get all dead_wolves
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM dead_wolves ORDER BY tissue_id DESC")

    results = cursor.fetchall()

    return render_template("dead_wolves_list.html",
                           results=results)


'''

@app.route("/new_transect", methods=("GET", "POST"))
def new_transect():

    def not_valid(msg):
        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(Markup(f"<b>{msg}</b>"))

        return render_template("new_transect.html",
                            title="New transect",
                            action=f"/new_transect",
                            form=form,
                            default_values=default_values)


    if request.method == "GET":
        form = Transect()
        return render_template('new_transect.html',
                               title="New transect",
                               action=f"/new_transect",
                            form=form,
                            default_values={})


    if request.method == "POST":
        form = Transect(request.form)

        if form.validate():

            transect_regions = fn.get_regions(request.form["province"])
            if request.form["province"] and transect_regions == "":
                return not_valid("Check the province field!")

            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            sql = ("INSERT INTO transects (transect_id, sector, location, municipality, province, region) "
                   "VALUES (%s, %s, %s, %s, %s, %s)")
            cursor.execute(sql,
                           [
                            request.form["transect_id"], request.form["sector"],
                            request.form["location"].strip(), request.form["municipality"].strip(),
                            request.form["province"].strip().upper(),
                            transect_regions
                           ]
                           )

            connection.commit()

            return redirect("/transects_list")
        else:
            return not_valid("Transect form NOT validated")



@app.route("/edit_transect/<transect_id>", methods=("GET", "POST"))
def edit_transect(transect_id):

    def not_valid(msg):
        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(Markup(f"<b>{msg}</b>"))

        return render_template("new_transect.html",
                            title="Edit transect",
                            action=f"/edit_transect/{transect_id}",
                            form=form,
                            default_values=default_values)


    if request.method == "GET":
        connection = fn.get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM transects WHERE transect_id = %s",
                    [transect_id])
        default_values = cursor.fetchone()

        form = Transect()

        return render_template("new_transect.html",
                            title="Edit transect",
                            action=f"/edit_transect/{transect_id}",
                            form=form,
                            default_values=default_values)

    if request.method == "POST":

        form = Transect(request.form)
        if form.validate():

            transect_regions = fn.get_regions(request.form["province"])
            if request.form["province"] and transect_regions == "":
                return not_valid("Check the province field!")


            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            sql = ("UPDATE transects SET transect_id = %s, sector =%s, location = %s, municipality = %s, province = %s, region = %s "
                   "WHERE transect_id = %s")
            cursor.execute(sql,
                           [
                            request.form["transect_id"].strip(), request.form["sector"],
                            request.form["location"].strip(), request.form["municipality"].strip(),
                            request.form["province"].strip().upper(), transect_regions,
                            transect_id
                           ]
                           )

            connection.commit()

            return redirect(f"/view_transect/{transect_id}")
        else:
            return not_valid("Transect form NOT validated")


@app.route("/del_transect/<transect_id>")
def del_scat(transect_id):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # check if path based on transect exist
    cursor.execute("SELECT COUNT(*) AS n_paths FROM paths WHERE transect_id = %s", [transect_id])
    result = cursor.fetchone()
    if result["n_paths"] > 0:
        return "Some paths are based on this transect. Please remove them before"

    cursor.execute("DELETE FROM transects WHERE transect_id = %s",
                   [transect_id])
    connection.commit()
    return redirect("/transects_list")


'''