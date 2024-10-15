"""
WolfDB web service
(c) Olivier Friard

flask blueprint for packs management
"""

from flask import render_template, Blueprint, session  # , render_template_string
from sqlalchemy import text
from markupsafe import Markup

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
                    "SELECT pack, REPLACE(pack, '?', '%3F') AS pack_url, COUNT(*) AS n_individuals "
                    "FROM genotypes WHERE pack is NOT NULL AND pack != '' "
                    "GROUP BY pack ORDER BY pack"
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
        wa_codes = (
            con.execute(
                text(
                    "SELECT "
                    "ST_X(st_transform(geometry_utm, 4326)) as longitude, "
                    "ST_Y(st_transform(geometry_utm, 4326)) as latitude, "
                    "genotype_id,"
                    "scat_id AS sample_id,"
                    "'scat' AS sample_type,"
                    "wa_results.wa_code "
                    "FROM scats, wa_results "
                    "WHERE scats.wa_code = wa_results.wa_code "
                    "      AND wa_results.genotype_id in (SELECT genotype_id FROM genotypes_list_mat WHERE pack = :pack_name "
                    "                                                                             AND (date_first_capture BETWEEN :start_date AND :end_date OR date_first_capture IS NULL)) "
                    "UNION "
                    "SELECT "
                    "ST_X(st_transform(geometry_utm, 4326)) as longitude, "
                    "ST_Y(st_transform(geometry_utm, 4326)) as latitude, "
                    "wa_results.genotype_id AS genotype_id,"
                    "tissue_id AS sample_id,"
                    "'Dead wolf' AS sample_type,"
                    "wa_results.wa_code "
                    "FROM dead_wolves, wa_results "
                    "WHERE dead_wolves.wa_code = wa_results.wa_code "
                    "       AND wa_results.genotype_id in (SELECT genotype_id FROM genotypes_list_mat WHERE pack = :pack_name "
                    "                                                                              AND (date_first_capture BETWEEN :start_date AND :end_date OR date_first_capture IS NULL))"
                ),
                {"pack_name": pack_name, "start_date": session["start_date"], "end_date": session["end_date"]},
            )
            .mappings()
            .all()
        )

    samples_features: list = []
    sum_lon: float = 0.0
    sum_lat: float = 0.0
    count_wa_code: int = 0
    for row in wa_codes:
        count_wa_code += 1
        sum_lon += row["longitude"]
        sum_lat += row["latitude"]

        popup_content: list = []
        if row["sample_type"] == "scat":
            color = params["scat_color"]
            popup_content.append(f"""Scat ID: <a href="/view_scat/{row['sample_id']}" target="_blank">{row['sample_id']}</a><br>""")
        elif row["sample_type"] == "Dead wolf":
            color = params["dead_wolf_color"]
            popup_content.append(f"""Tissue ID: <a href="/view_tissue/{row['sample_id']}" target="_blank">{row['sample_id']}</a><br>""")
        else:
            color = "red"

        popup_content.append(f"""WA code: <a href="/view_wa/{row['wa_code']}" target="_blank">{row['wa_code']}</a><br>""")
        popup_content.append(f"""Genotype ID: <a href="/view_genotype/{row['genotype_id']}" target="_blank">{row['genotype_id']}</a>""")

        sample_feature = {
            "geometry": {"type": "Point", "coordinates": [row["longitude"], row["latitude"]]},
            "type": "Feature",
            "properties": {
                "style": {"color": color, "fillColor": color, "fillOpacity": 1},
                "popupContent": "".join(popup_content),
            },
            "id": row["sample_id"],
        }
        samples_features.append(sample_feature)

    if count_wa_code:
        center = f"{sum_lat / count_wa_code}, {sum_lon / count_wa_code}"
        map = Markup(
            fn.leaflet_geojson(
                {
                    "scats": samples_features,
                    "scats_color": params["scat_color"],
                    "center": center,
                }
            )
        )
    else:
        map = ""

    return render_template(
        "view_pack.html",
        header_title="View pack",
        pack_name=pack_name,
        results=results,
        n_individuals=len(results),
        map=map,
        scat_color=params["scat_color"],
        dead_wolf_color=params["dead_wolf_color"],
        count_wa_code=count_wa_code,
    )


'''
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
'''
