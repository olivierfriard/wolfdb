"""
WolfDB web service
(c) Olivier Friard

flask blueprint for packs management
"""

import flask
from flask import (
    render_template,
)
from sqlalchemy import text
from config import config

import functions as fn

app = flask.Blueprint("packs", __name__, template_folder="templates")

params = config()
app.debug = params["debug"]


@app.route("/packs")
@fn.check_login
def packs():
    """
    Display the list of packs
    """
    with fn.conn_alchemy().connect() as con:
        packs_list = (
            con.execute(text("SELECT pack FROM genotypes WHERE pack is NOT NULL AND pack != '' GROUP BY pack ORDER BY pack"))
            .mappings()
            .all()
        )

    return render_template(
        "packs_list.html",
        header_title="Packs",
        packs_list=packs_list,
        n_packs=len(packs_list),
    )


@app.route("/view_pack/<name>")
@fn.check_login
def view_pack(name):
    """
    Displat the pack composition
    """
    with fn.conn_alchemy().connect() as con:
        results = (
            con.execute(
                text("SELECT * FROM genotypes_list_mat WHERE pack = :pack ORDER BY date_first_capture ASC"),
                {"pack": name},
            )
            .mappings()
            .all()
        )

    return render_template(
        "view_pack.html",
        header_title="View pack",
        pack_name=name,
        results=results,
        n_individuals=len(results),
    )
