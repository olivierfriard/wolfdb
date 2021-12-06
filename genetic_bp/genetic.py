"""
WolfDB web service
(c) Olivier Friard

flask blueprint for scats management
"""



import flask
from flask import render_template, redirect, request, Markup, flash, session
import psycopg2
import psycopg2.extras
from config import config

import functions as fn

app = flask.Blueprint("genetic", __name__, template_folder="templates")

app.debug = True


params = config()

@app.route("/view_wa/<wa_code>")
def view_wa(wa_code):
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM scats WHERE wa_code = %s ", [wa_code])
    return render_template("view_wa.html",
                           results=cursor.fetchone())


@app.route("/wa_genetic_samples")
def genetic_samples():
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    '''
    cursor.execute("SELECT count(scat_id) AS n_wa FROM scats WHERE wa_code IS NOT NULL AND wa_code != ''")
    n_wa = cursor.fetchone()["n_wa"]
    '''

    cursor.execute("SELECT *, (select scat_id from scats WHERE wa_code != '' AND wa_code = wa_results.wa_code limit 1) AS scat_id FROM wa_results ORDER BY wa_code ASC")

    return render_template("wa_genetic_samples_list.html",
                           results=cursor.fetchall())


@app.route("/view_genetic_data/<wa_code>")
def view_genetic_data(wa_code):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM loci ")
    loci = cursor.fetchall()
    data = {}
    for locus in loci:
        data[locus["name"]] = {"value1": "", "value2": "", "timestamp": "", "notes": ""}

    cursor.execute("SELECT * FROM wa_locus WHERE wa_code = %s ORDER BY locus, timestamp", [wa_code])
    for row in cursor.fetchall():
        data[row['locus']] =  {"value1": row['value1'], "value2": row['value2'], "timestamp": str(row['timestamp']).split(".")[0], "notes": row['notes']}

    return render_template("view_genetic_data.html",
                           wa_code=wa_code,
                           loci=loci,
                           data=data)



@app.route("/add_genetic_data/<wa_code>", methods=("GET", "POST",))
def add_genetic_data(wa_code):

    if request.method == "GET":
        connection = fn.get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM loci ")
        loci = cursor.fetchall()

        '''
        data = {}
        for locus in loci:
            data[locus["name"]] = {"value1": "", "value2": "", "timestamp": ""}

        cursor.execute("SELECT * FROM wa_locus WHERE wa_code = %s  ORDER BY locus, timestamp", [wa_code])
        for row in cursor.fetchall():
            data[row['locus']] =  {"value1": row['value1'], "value2": row['value2'], "timestamp": str(row['timestamp']).split(".")[0]}

        '''
        return render_template("add_genetic_data.html",
                                wa_code=wa_code,
                                mode="modify",
                                loci=loci,
                                )

    if request.method == "POST":
        connection = fn.get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM loci ")
        loci=cursor.fetchall()
        for locus in loci:
            if request.form[locus['name'] + "_1"] or (locus['name'] != "SRY" and request.form[locus['name'] + "_2"]):
                cursor.execute("INSERT INTO wa_locus (wa_code, locus, value1, value2, timestamp, notes) VALUES (%s, %s, %s, %s, NOW(), %s) ",
                           [wa_code, locus['name'],
                           int(request.form[locus['name'] + "_1"]) if request.form[locus['name'] + "_1"] else None,

                           int(request.form[locus['name'] + "_2"]) if (locus['name'] != "SRY" and request.form[locus['name'] + "_2"]) else None,

                           request.form[locus['name'] + "_notes"] if request.form[locus['name'] + "_notes"] else None
                           ])

        cursor.execute("UPDATE scats SET genetic_sample = 'Yes' WHERE wa_code = %s", [wa_code])

        connection.commit()
        return redirect(f"/view_genetic_data/{wa_code}")



@app.route("/view_genetic_data_history/<wa_code>/<locus>")
def view_genetic_data_history(wa_code, locus):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT *, to_char(timestamp, 'YYYY-MM-DD HH24:MI:SS') AS formated_timestamp FROM wa_locus WHERE wa_code = %s AND locus = %s ORDER by timestamp DESC", [wa_code, locus])
    results = cursor.fetchall()

    return render_template("view_genetic_data_history.html",
                            results = results,
                            wa_code=wa_code,
                            locus=locus)
