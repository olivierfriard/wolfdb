"""
WolfDB web service
(c) Olivier Friard

flask blueprint for packs management
"""

from flask import render_template, Blueprint, session
from sqlalchemy import text
from config import config

import functions as fn

app = Blueprint("packs", __name__, template_folder="templates")

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
            con.execute(
                text(
                    "SELECT pack, REPLACE(pack, '?', '%3F') AS pack_url FROM genotypes WHERE pack is NOT NULL AND pack != '' GROUP BY pack ORDER BY pack"
                ),
            )
            .mappings()
            .all()
        )

    return render_template(
        "packs_list.html",
        header_title="Packs",
        packs_list=packs_list,
        n_packs=len(packs_list),
    )


@app.route("/view_pack/<path:pack_name>")
@fn.check_login
def view_pack(pack_name):
    """
    Display the pack composition
    """
    with fn.conn_alchemy().connect() as con:
        results = (
            con.execute(
                text(
                    "SELECT * FROM genotypes_list_mat "
                    "WHERE pack = :pack_name "
                    "AND (date_first_capture BETWEEN :start_date AND :end_date OR date_first_capture IS NULL) "
                    "ORDER BY date_first_capture ASC"
                ),
                {"pack_name": pack_name, "start_date": session["start_date"], "end_date": session["end_date"]},
            )
            .mappings()
            .all()
        )

    return render_template(
        "view_pack.html",
        header_title="View pack",
        pack_name=pack_name,
        results=results,
        n_individuals=len(results),
    )
