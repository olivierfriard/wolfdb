"""
WolfDB web service
(c) Olivier Friard

flask blueprint for packs management
"""


import flask
from flask import Flask, render_template, redirect, request, Markup, flash, session, make_response
import psycopg2
import psycopg2.extras
from config import config

import functions as fn

app = flask.Blueprint("packs", __name__, template_folder="templates")

params = config()
app.debug = params["debug"]



@app.route("/packs")
@fn.check_login
def packs():

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("SELECT pack FROM genotypes WHERE pack is NOT NULL AND pack != '' GROUP BY pack ORDER BY pack")
    packs_list = cursor.fetchall()

    return render_template("packs_list.html",
                            header_title="Packs",
                            packs_list=packs_list,
                            n_packs=len(packs_list)
                            )



@app.route("/view_pack/<name>")
@fn.check_login
def view_pack(name):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute(("SELECT *, "
                    "(SELECT date FROM wa_scat_tissue where wa_code = (select wa_code from wa_results where wa_results.genotype_id=genotypes.genotype_id LIMIT 1)) as date "
                    "FROM genotypes WHERE pack = %s"),
                    [name])

    results = cursor.fetchall()

    return render_template("view_pack.html",
                            header_title="View pack",
                            pack_name=name,
                            results=results,
                            n_individuals=len(results)
                            )

