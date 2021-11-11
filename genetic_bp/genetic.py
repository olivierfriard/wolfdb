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

import functions as fn

app = flask.Blueprint("genetic", __name__, template_folder="templates")

app.debug = True


params = config()



@app.route("/genetic_samples")
def genetic_samples():
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM scats WHERE wa_code IS NOT NULL ORDER BY scat_id")

    return render_template("genetic_samples_list.html",
                           results=cursor.fetchall())


@app.route("/view_genetic_data/<wa_code>")
def view_genetic_data(wa_code):
        connection = fn.get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM wa_locus WHERE wa_code = %s", [wa_code])

        return render_template("add_genetic_data.html",
                                mode='view',
                                wa_code=wa_code,
                                loci=cursor.fetchall())




@app.route("/add_genetic_data/<wa_code>", methods=("GET", "POST",))
def add_genetic_data(wa_code):

    if request.method == "GET":
        connection = fn.get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM loci ")

        return render_template("add_genetic_data.html",
                            wa_code=wa_code,
                            loci=cursor.fetchall())

    if request.method == "POST":
        connection = fn.get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM loci ")
        loci=cursor.fetchall()
        for locus in loci:
            cursor.execute("INSERT INTO wa_locus (wa_code, locus, value1, value2) VALUES (%s, %s, %s, %s) ",
                           [wa_code, locus['name'],
                           int(request.form[locus['name']+ "_1"]) if request.form[locus['name']+ "_1"] else None,
                           int(request.form[locus['name']+ "_2"]) if request.form[locus['name']+ "_2"] else None]
                           )

        cursor.execute("UPDATE scats SET genetic_sample = 'Yes' WHERE wa_code = %s", [wa_code])

        connection.commit()
        return "Values inserted"
