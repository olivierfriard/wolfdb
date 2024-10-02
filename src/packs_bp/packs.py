"""
WolfDB web service
(c) Olivier Friard

flask blueprint for packs management
"""

from flask import render_template, Blueprint, session, render_template_string
from sqlalchemy import text
from markupsafe import Markup
import folium

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

        # map
        map_data = con.execute(
            text(
                "select geometry_utm, genotype_id AS genotype_id, scat_id AS sample_id, wa_results.wa_code from scats, wa_results "
                "WHERE scats.wa_code = wa_results.wa_code and wa_results.genotype_id in (SELECT genotype_id FROM genotypes WHERE pack = :pack AND (date_first_capture BETWEEN :start_date AND :end_date OR date_first_capture IS NULL)) "
                "UNION"
                "select geometry_utm, wa_results.genotype_id AS genotype_id, tissue_id AS sample_id, wa_results.wa_code from dead_wolves, wa_results "
                "WHERE dead_wolves.wa_code = wa_results.wa_code and wa_results.genotype_id in (SELECT genotype_id FROM genotypes WHERE pack = :pack AND (date_first_capture BETWEEN :start_date AND :end_date OR date_first_capture IS NULL))"
            ),
            {"pack_name": pack_name, "start_date": session["start_date"], "end_date": session["end_date"]},
        )

    return render_template(
        "view_pack.html",
        header_title="View pack",
        pack_name=pack_name,
        results=results,
        n_individuals=len(results),
    )


@app.route("/folium")
@fn.check_login
def folium_():
    """
    Display the pack composition
    """
    m = folium.Map(
        width=800,
        height=600,
    )

    m.get_root().render()
    header = m.get_root().header.render()
    body_html = m.get_root().html.render()
    script = m.get_root().script.render()

    print(header)

    print(body_html)

    return render_template(
        "view_pack_folium.html",
        header_title="View pack",
        folium_header=Markup(header),
        folium_body=Markup(body_html),
        folium_script=Markup(script),
        # pack_name=pack_name,
        # results=results,
        # n_individuals=len(results),
    )

    return render_template_string(
        """
            <!DOCTYPE html>
            <html>
                <head>
                    {{ header|safe }}
                </head>
                <body>
                    <h1>Using components</h1>
                    {{ body_html|safe }}
                    <script>
                        {{ script|safe }}
                    </script>
                </body>
            </html>
        """,
        header=header,
        body_html=body_html,
        script=script,
    )
