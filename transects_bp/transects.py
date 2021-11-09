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

from transect import Transect
import functions as fn

app = flask.Blueprint("transects", __name__, template_folder="templates")

app.debug = True


params = config()

@app.route("/transects")
def transects():
    return render_template("transects.html")


@app.route("/view_transect/<transect_id>")
def view_transect(transect_id):
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM transect WHERE transect_id = %s",
                   [transect_id])
    transect = cursor.fetchone()

    # path
    cursor.execute("SELECT * FROM paths WHERE transect_id = %s ORDER BY date DESC",
                   [transect_id])
    results_paths = cursor.fetchall()

    # snow tracks
    cursor.execute("SELECT * FROM snow_tracks WHERE path_id LIKE %s ORDER BY date DESC",
                   [f"{transect_id} %"])
    results_snowtracks = cursor.fetchall()


    return render_template("view_transect.html",
                           transect=transect,
                           paths=results_paths,
                           snowtracks=results_snowtracks)


@app.route("/transects_list")
def transects_list():
    # get all transects
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM transect ORDER BY transect_id")

    results = cursor.fetchall()

    return render_template("transects_list.html",
                           results=results)


@app.route("/new_transect", methods=("GET", "POST"))
def new_transect():

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

            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            sql = ("INSERT INTO transect (transect_id, sector, localita, provincia, regione) "
                   "VALUES (%s, %s, %s, %s, %s)")
            cursor.execute(sql,
                           [
                            request.form["transect_id"], request.form["sector"],
                            request.form["localita"], request.form["provincia"], request.form["regione"]
                           ]
                           )

            connection.commit()

            return redirect("/transects_list")
        else:
            return "Transect form NOT validated<br><a href="/">Home</a>"



@app.route("/edit_transect/<transect_id>", methods=("GET", "POST"))
def edit_transect(transect_id):

    if request.method == "GET":
        connection = fn.get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM transect WHERE transect_id = %s",
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

            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            sql = ("UPDATE transect SET transect_id = %s, sector =%s, localita = %s, provincia = %s, regione = %s "
                   "WHERE transect_id = %s")
            cursor.execute(sql,
                           [
                            request.form["transect_id"], request.form["sector"],
                            request.form["localita"], request.form["provincia"], request.form["regione"],
                            transect_id
                           ]
                           )

            connection.commit()

            return redirect(f"/view_transect/{transect_id}")
        else:
            return "Transect form NOT validated<br><a href="/">Home</a>"

