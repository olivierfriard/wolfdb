"""
WolfDB web service
(c) Olivier Friard

flask blueprint for genetic data management
"""

from flask import (
    render_template,
    redirect,
    request,
    flash,
    session,
    make_response,
    Blueprint,
    current_app,
    jsonify,
    url_for,
)
from markupsafe import Markup
from sqlalchemy import text
from config import config
import json
import matplotlib
import matplotlib.pyplot as plt
import subprocess
import redis
import pathlib as pl
import uuid
import datetime as dt
import time
import jinja2
from geojson import Polygon

import functions as fn
from . import export
from . import import_

app = Blueprint("genetic", __name__, template_folder="templates")

params = config()
app.debug = params["debug"]

# db wolf -> db 0
rdis = redis.Redis(db=(0 if params["database"] == "wolf" else 1))


def get_cmap(n, name="viridis"):
    """
    Returns a function that maps each index in 0, 1, ..., n-1 to a distinct
    RGB color; the keyword argument name must be a standard mpl colormap name.
    """

    return plt.cm.get_cmap(name, n)
    # return plt.colormaps.get_cmap(name, n)


@app.route("/del_genotype/<genotype_id>")
@fn.check_login
def del_genotype(genotype_id):
    """
    set genotype as deleted (record_status field)
    """
    with fn.conn_alchemy().connect() as con:
        con.execute(
            text("UPDATE genotypes SET record_status = 'deleted' WHERE genotype_id = :genotype_id"),
            {"genotype_id": genotype_id},
        )
        con.execute(
            text("UPDATE wa_results SET genotype_id = NULL WHERE genotype_id = :genotype_id"),
            {"genotype_id": genotype_id},
        )

    # after_genotype_modif()    already done in after_wa_results_modif
    after_wa_results_modif()

    flash(fn.alert_success(f"<b>Genotype {genotype_id} deleted</b>"))

    return redirect(request.referrer)


@app.route("/undel_genotype/<genotype_id>")
@fn.check_login
def undel_genotype(genotype_id):
    """
    set genotype as temp (record_status field)
    """
    with fn.conn_alchemy().connect() as con:
        con.execute(
            text("UPDATE genotypes SET record_status = 'temp' WHERE genotype_id = :genotype_id"),
            {"genotype_id": genotype_id},
        )
        after_genotype_modif()

    flash(fn.alert_success(f"<b>Genotype {genotype_id} undeleted</b>"))

    return redirect(f"{request.referrer}#{genotype_id}")


@app.route("/def_genotype/<genotype_id>")
@fn.check_login
def def_genotype(genotype_id):
    """
    set genotype as definitive (record_status field)
    """
    with fn.conn_alchemy().connect() as con:
        con.execute(
            text("UPDATE genotypes SET record_status = 'OK' WHERE genotype_id = :genotype_id"),
            {"genotype_id": genotype_id},
        )
        after_genotype_modif()

    flash(fn.alert_success(f"<b>Genotype {genotype_id} set as definitive</b>"))

    return redirect(f"{request.referrer}#{genotype_id}")


@app.route("/temp_genotype/<genotype_id>")
@fn.check_login
def temp_genotype(genotype_id):
    """
    set genotype as temporary (record_status field)
    """
    with fn.conn_alchemy().connect() as con:
        con.execute(
            text("UPDATE genotypes SET record_status = 'temp' WHERE genotype_id = :genotype_id"),
            {"genotype_id": genotype_id},
        )
        after_genotype_modif()

    flash(fn.alert_success(f"<b>Genotype {genotype_id} set as temporary</b>"))

    return redirect(f"{request.referrer}#{genotype_id}")


@app.route("/view_genotype/<genotype_id>")
@fn.check_login
def view_genotype(genotype_id: str):
    """
    visualize genotype's data
    """

    with fn.conn_alchemy().connect() as con:
        genotype = (
            con.execute(
                text("SELECT * FROM genotypes_list_mat WHERE genotype_id = :genotype_id"),
                {"genotype_id": genotype_id},
            )
            .mappings()
            .fetchone()
        )

        if genotype is None:
            flash(fn.alert_danger(f"The genotype <b>{genotype_id}</b> was not found in Genotypes table"))
            # return to the last page
            if "url_genotypes_list" in session:
                return redirect(session["url_genotypes_list"])
            if "url_wa_list" in session:
                return redirect(session["url_wa_list"])
            return "Error on genotype"

        session["view_genotype_id"] = genotype_id

        genotype_loci = fn.get_genotype_loci_values_redis(genotype_id)

        # samples
        wa_codes = (
            con.execute(
                text(
                    "SELECT wa_code, sample_id, sample_type, "
                    "ST_X(st_transform(geometry_utm, 4326)) as longitude, "
                    "ST_Y(st_transform(geometry_utm, 4326)) as latitude "
                    "FROM wa_scat_dw_mat "
                    "WHERE genotype_id = :genotype_id "
                    "ORDER BY wa_code"
                ),
                {"genotype_id": genotype_id},
            )
            .mappings()
            .all()
        )

    # loci list
    loci_list: dict = fn.get_loci_list()

    samples_features: list = []
    loci_values: dict = {}
    count_wa_code: int = 0
    sum_lon: float = 0.0
    sum_lat: float = 0.0
    for row in wa_codes:
        count_wa_code += 1
        sum_lon += row["longitude"]
        sum_lat += row["latitude"]

        """
        if row["sample_type"] == "scat":
            color = params["scat_color"]
        """
        if row["sample_type"] == "Dead wolf":
            color = params["dead_wolf_color"]
        else:
            color = "red"

        color = params["scat_color"]

        sample_feature = {
            "geometry": {
                "type": "Point",
                "coordinates": [row["longitude"], row["latitude"]],
            },
            "type": "Feature",
            "properties": {
                "style": {"color": color, "fillColor": color, "fillOpacity": 1},
                "popupContent": (
                    f"""Scat ID: <a href="/view_scat/{row["sample_id"]}" target="_blank">{row["sample_id"]}</a><br>"""
                    f"""WA code: <a href="/view_wa/{row["wa_code"]}" target="_blank">{row["wa_code"]}</a><br>"""
                    # f"""Genotype ID: {row['genotype_id']}"""
                ),
            },
            "id": row["sample_id"],
        }
        samples_features.append(sample_feature)

        loci_values[row["wa_code"]] = fn.get_wa_loci_values_redis(row["wa_code"])

    if count_wa_code:
        map = Markup(
            fn.leaflet_geojson(
                {
                    "scats": samples_features,
                    "scats_color": params["scat_color"],
                    "center": f"{sum_lat / count_wa_code}, {sum_lon / count_wa_code}",
                }
            )
        )
    else:
        map = ""

    return render_template(
        "view_genotype.html",
        header_title=f"Genotype ID: {genotype_id}",
        result=genotype,
        genotype_loci=genotype_loci,
        n_recap=len(wa_codes),
        wa_codes=wa_codes,
        loci_list=loci_list,
        loci_values=loci_values,
        count_wa_code=count_wa_code,
        map=map,
        scat_color=params["scat_color"],
        dead_wolf_color=params["dead_wolf_color"],
        transect_color=params["transect_color"],
        track_color=params["track_color"],
    )


@app.route(
    "/genotypes_list/<int:offset>/<limit>/<type>",
    methods=(
        "GET",
        "POST",
    ),
)
@app.route("/genotypes_list/<int:offset>/<limit>/<type>/<mode>")
@fn.check_login
def genotypes_list(offset: int, limit: int | str, type: str, mode="web"):
    """
    Display genetic data for genotypes: all, temp, definitive

    Read loci values from redis
    """

    filter: str = "WHERE (date_first_capture BETWEEN :start_date AND :end_date OR date_first_capture IS NULL) "

    # check type of genotype
    match type:
        case "all":
            filter += "AND record_status != 'deleted'"
            header_title = "List of all genotypes"

        case "definitive":
            filter += "AND record_status = 'OK'"
            header_title = "List of definitive genotypes"

        case "temp":
            filter += "AND record_status = 'temp'"
            header_title = "List of temporary genotypes"

        case "deleted":
            filter += "AND record_status = 'deleted'"
            header_title = "List of temporary genotypes"
        case _:
            return f"{type} not found"

    # test limit value: must be ALL or int
    if limit != "ALL":
        try:
            limit = int(limit)
        except Exception:
            return "An error has occured. Check the URL"
    else:  # "ALL":
        offset = 0

    # check if wa code is specified to scroll the table
    if "view_genotype_id" in session:
        view_genotype_id = session["view_genotype_id"]
        del session["view_genotype_id"]
    else:
        view_genotype_id = None

    with fn.conn_alchemy().connect() as con:
        sql_all = f"SELECT *, count(*) OVER() AS n_genotypes FROM genotypes_list_mat {filter} LIMIT {limit} OFFSET {offset}"

        if request.method == "POST":
            offset = 0
            limit = "ALL"

            if request.args.get("search") is None:
                search_term = request.form["search"].strip()
            else:
                search_term = request.args.get("search").strip()

        if request.method == "GET":
            if request.args.get("search") is not None:
                search_term: str = request.args.get("search").strip()
            else:
                search_term: str = ""

        if ":" in search_term:
            sql_search = sql_all
            values: dict = {}
            sql_search: str = "SELECT *, count(*) OVER() AS n_genotypes FROM genotypes_list_mat "
            for idx, field_term in enumerate(search_term.split(";")):
                field, value = [x.strip().lower() for x in field_term.split(":")]
                if field not in (
                    "genotype",
                    "notes",
                    "tmp id",
                    "date",
                    "pack",
                    "sex",
                    "status",
                    "working notes",
                ):
                    flash(
                        fn.alert_danger(
                            "<b>Search term not found</b>. Must be 'genotype id', 'notes', 'tmp id', 'date', 'pack', 'sex', 'status' or 'working notes'"
                        )
                    )
                    return redirect(session["url_wa_list"])
                if field == "genotype":
                    field = "genotype id"
                field = field.replace(" ", "_")
                if idx == 0:
                    sql_search += f" WHERE ({field} ILIKE :search{idx}) "
                else:
                    sql_search += f" AND ({field} ILIKE :search{idx}) "
                values[f"search{idx}"] = f"%{value}%"

        else:  # search in all fields
            values = {"search": f"%{search_term}%"}

            sql_search = (
                "SELECT *, count(*) OVER() AS n_genotypes FROM genotypes_list_mat WHERE ("
                "genotype_id ILIKE :search "
                "OR notes ILIKE :search "
                "OR tmp_id ILIKE :search "
                "OR date::text ILIKE :search "
                "OR pack ILIKE :search "
                "OR sex ILIKE :search "
                "OR status ILIKE :search "
                "OR working_notes ILIKE :search "
                ") "
            )

        results = (
            con.execute(
                text(sql_all if not search_term else sql_search),
                dict(
                    {
                        "start_date": session["start_date"],
                        "end_date": session["end_date"],
                    },
                    **values,
                ),
            )
            .mappings()
            .all()
        )

    # loci list
    loci_list: dict = fn.get_loci_list()

    loci_values: dict = {}
    for row in results:
        loci_values[row["genotype_id"]] = fn.get_genotype_loci_values_redis(row["genotype_id"])

    if mode == "export":
        file_content = export.export_genotypes_list(loci_list, results, loci_values)

        response = make_response(file_content, 200)
        response.headers["Content-type"] = "application/application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        response.headers["Content-disposition"] = f"attachment; filename=genotypes_list_{dt.datetime.now():%Y-%m-%d_%H%M%S}.xlsx"

        return response

    else:
        session["url_genotypes_list"] = f"/genotypes_list/{offset}/{limit}/{type}?search={search_term}"
        if "url_wa_list" in session:
            del session["url_wa_list"]

        if results:
            title = f"List of {results[0]['n_genotypes']} {type} genotypes".replace(" all", "").replace("_short", "")
        else:
            title = "No genotype found"

        return render_template(
            "genotypes_list.html",
            header_title=header_title,
            title=title,
            limit=limit,
            offset=offset,
            type=type,
            n_genotypes=results[0]["n_genotypes"] if results else 0,
            results=results,
            loci_list=loci_list,
            loci_values=loci_values,
            short="",
            search_term=search_term,
            view_genotype_id=view_genotype_id,
        )


@app.route("/genotype_without_wa_loci")
@fn.check_login
def genotype_without_wa_loci():
    """
    returns list of genotypes without wa code loci values
    """

    sql = text("""SELECT genotype_id,
            n_recaptures,
            (SELECT STRING_AGG(CONCAT(wa_code, ' ',mtdna), ' | ') FROM wa_scat_dw_mat WHERE genotype_id = g.genotype_id ) AS "wa_code_mtDNA"
            FROM genotypes_list_mat g
            WHERE 
            n_recaptures != 0 
            AND genotype_id NOT IN (SELECT genotype_id FROM genotype_locus)
            ORDER BY genotype_id;
          """)
    with fn.conn_alchemy().connect() as con:
        out: list = ['<table class="table">']
        out.append("<thead><tr><th>Genotype ID</th><th>Number of recaptures</th><th>WA codes / mtDna</th></tr></thead>\n")
        out.append("<tbody>")
        for row in con.execute(sql).mappings().all():
            out.append("<tr>")
            out.append(f"<td>{row['genotype_id']}</td><td>{row['n_recaptures']}</td><td>{row['wa_code_mtDNA']}</td>")
            out.append("</tr>\n")
        out.append("</tbody>")
        out.append("</table>")

    return render_template(
        "page.html",
        header_title="Genotypes without wa code loci values",
        title="Genotypes without wa code loci values",
        out=Markup("\n".join(out)),
    )


@app.route("/view_wa/<wa_code>")
@fn.check_login
def view_wa(wa_code: str):
    """
    visualize WA code and correlated sample data
    link to view genetic data (if available)
    """
    with fn.conn_alchemy().connect() as con:
        result = (
            con.execute(
                text(
                    "SELECT scat_id AS sample_id, 'Scat' AS sample_type, NULL AS tissue_id FROM scats WHERE wa_code = :wa_code "
                    "UNION "
                    "SELECT id::text as sample_id, 'Dead wolf' AS sample_type, tissue_id FROM dead_wolves WHERE wa_code = :wa_code "
                ),
                {"wa_code": wa_code},
            )
            .mappings()
            .all()
        )
        if result is None:
            flash(fn.alert_danger(f"WA code not found: {wa_code}"))
            return redirect(request.referrer)
        if len(result) > 1:
            flash(fn.alert_danger(f"WA code found in scats and dead wolves table. Check {wa_code}"))
            return redirect(request.referrer)

        # check if genetic data available
        genetic_data = (
            con.execute(
                text("SELECT wa_code FROM wa_results WHERE wa_code = :wa_code"),
                {"wa_code": wa_code},
            )
            .mappings()
            .all()
        )

        return render_template(
            "view_wa.html",
            header_title=f"{wa_code}",
            wa_code=wa_code,
            result=result[0],
            genetic_data=genetic_data,
        )


@app.route("/plot_all_wa")
@fn.check_login
def plot_all_wa(add_polygon: bool = False, samples: str = "genotypes"):
    """
    plot all WA codes (scats and dead wolves)

    Args:
        add_polygon (bool):
        samples (str):

    """

    scat_features: list = []
    tot_min_lat: float = 90
    tot_min_lon: float = 90
    tot_max_lat: float = -90
    tot_max_lon: float = -90

    t0 = time.time()
    with fn.conn_alchemy().connect() as con:
        for row in (
            con.execute(
                text(
                    "SELECT wa_code, sample_id, genotype_id, "
                    "ST_X(st_transform(geometry_utm, 4326)) as longitude, "
                    "ST_Y(st_transform(geometry_utm, 4326)) as latitude "
                    "FROM wa_scat_dw_mat "
                    "WHERE mtdna != 'Poor DNA' "
                    "AND date BETWEEN :start_date AND :end_date "
                ),
                {
                    "start_date": session["start_date"],
                    "end_date": session["end_date"],
                },
            )
            .mappings()
            .all()
        ):
            tot_min_lat = min([tot_min_lat, row["latitude"]])
            tot_max_lat = max([tot_max_lat, row["latitude"]])
            tot_min_lon = min([tot_min_lon, row["longitude"]])
            tot_max_lon = max([tot_max_lon, row["longitude"]])

            if row["sample_id"].startswith("E"):
                color = params["scat_color"]
            elif row["sample_id"][0] in "TM":
                color = params["dead_wolf_color"]
            else:
                color = "red"

            scat_feature = {
                "geometry": {
                    "type": "Point",
                    "coordinates": [row["longitude"], row["latitude"]],
                },
                "type": "Feature",
                "properties": {
                    "style": {"color": color, "fillColor": color, "fillOpacity": 1},
                    "popupContent": (
                        f"""Scat ID: <a href="/view_scat/{row["sample_id"]}" target="_blank">{row["sample_id"]}</a><br>"""
                        f"""WA code: <a href="/view_wa/{row["wa_code"]}" target="_blank">{row["wa_code"]}</a><br>"""
                        f"""Genotype ID: {row["genotype_id"]}"""
                    ),
                },
                "id": row["sample_id"],
            }

            scat_features.append(scat_feature)

    print(time.time() - t0)

    return render_template(
        "plot_all_wa.html",
        header_title="Locations of WA codes",
        title=Markup(f"<h3>Locations of {len(scat_features)} samples WA codes.</h3>"),
        map=Markup(
            fn.leaflet_geojson(
                data={
                    "scats": scat_features,
                    "scats_color": params["scat_color"],
                    "fit": [[tot_min_lat, tot_min_lon], [tot_max_lat, tot_max_lon]],
                },
                add_polygon=add_polygon,
                samples=samples,
            )
        ),
        add_polygon=add_polygon,
        distance=0,
        scat_color=params["scat_color"],
        dead_wolf_color=params["dead_wolf_color"],
    )


@app.route("/plot_all_wa2")
@fn.check_login
def plot_all_wa2(add_polygon: bool = False, samples: str = "genotypes"):
    """
    plot all WA codes (scats and dead wolves)

    Args:
        add_polygon (bool):
        samples (str):

    """

    scat_features: list = []
    tot_min_lat: float = 90
    tot_min_lon: float = 90
    tot_max_lat: float = -90
    tot_max_lon: float = -90
    scat_markers: str = ""

    t0 = time.time()
    with fn.conn_alchemy().connect() as con:
        wa_count: int = 0
        for row in (
            con.execute(
                text(
                    "SELECT wa_code, sample_id, genotype_id, "
                    "ST_X(st_transform(geometry_utm, 4326)) as longitude, "
                    "ST_Y(st_transform(geometry_utm, 4326)) as latitude "
                    "FROM wa_scat_dw_mat "
                    "WHERE mtdna != 'Poor DNA' "
                    "AND date BETWEEN :start_date AND :end_date "
                ),
                {
                    "start_date": session["start_date"],
                    "end_date": session["end_date"],
                },
            )
            .mappings()
            .all()
        ):
            wa_count += 1
            tot_min_lat = min([tot_min_lat, row["latitude"]])
            tot_max_lat = max([tot_max_lat, row["latitude"]])
            tot_min_lon = min([tot_min_lon, row["longitude"]])
            tot_max_lon = max([tot_max_lon, row["longitude"]])

            if row["sample_id"].startswith("E"):
                color = params["scat_color"]
            elif row["sample_id"][0] in "TM":
                color = params["dead_wolf_color"]
            else:
                color = "red"

            popup_text = (
                f"""Scat ID: <a href="/view_scat/{row["sample_id"]}" target="_blank">{row["sample_id"]}</a><br>"""
                f"""WA code: <a href="/view_wa/{row["wa_code"]}" target="_blank">{row["wa_code"]}</a><br>"""
            )
            if row["genotype_id"]:
                popup_text += f"""Genotype ID: {row["genotype_id"]}"""
            else:
                popup_text += "No genotype"
            # popup_text = "POPUP"
            scat_markers += (
                f"""{{coords:[{round(row["latitude"], 5)},{round(row["longitude"], 5)}],"""
                f"""label:"{row["genotype_id"]}","""
                f"""popup:'{popup_text}'}},"""
            )

    print(time.time() - t0)

    return render_template(
        "plot_all_wa.html",
        header_title="Locations of WA codes",
        title=Markup(f"<h3>Locations of {wa_count} WA code{'s' if wa_count > 1 else ''}.</h3>"),
        map=Markup(
            fn.leaflet_geojson_label(
                data={
                    "scats": scat_features,
                    "scats_color": params["scat_color"],
                    "fit": [[tot_min_lat, tot_min_lon], [tot_max_lat, tot_max_lon]],
                    "scat_markers": f"[{scat_markers}]",
                },
                add_polygon=add_polygon,
                samples=samples,
            )
        ),
        add_polygon=add_polygon,
        distance=0,
        scat_color=params["scat_color"],
        dead_wolf_color=params["dead_wolf_color"],
    )


@app.route("/plot_wa_clusters/<int:distance>")
@fn.check_login
def plot_wa_clusters(distance: int):
    """
    plot WA clusters using ST_ClusterDBSCAN function
    """

    MINPOINT = 1

    print(f"{session["start_date"]=}")
    print(f"{session["end_date"]=}")
    print(f"{distance=}")

    with fn.conn_alchemy().connect() as con:
        results = (
            con.execute(
                text(
                    "SELECT wa_code, sample_id, genotype_id, "
                    "coord_east, coord_north, "
                    "ST_X(st_transform(geometry_utm, 4326)) as longitude, "
                    "ST_Y(st_transform(geometry_utm, 4326)) as latitude, "
                    "ST_ClusterDBSCAN(geometry_utm, eps:=:distance, minpoints:=:minpoint) OVER(ORDER BY wa_code) AS cid "
                    "FROM wa_scat_dw_mat "
                    "WHERE mtdna != 'Poor DNA' "
                    "AND date BETWEEN :start_date AND :end_date"
                ),
                {
                    "start_date": session["start_date"],
                    "end_date": session["end_date"],
                    "distance": distance,
                    "minpoint": MINPOINT,
                },
            )
            .mappings()
            .all()
        )

    print(f"{len(results)=}")

    # max cluster id
    max_cluster_id = max([row["cid"] for row in results if row["cid"] is not None])

    """print(f"{max_cluster_id=}")"""

    cmap = get_cmap(max_cluster_id)

    """print(f"{cmap=}")"""

    # size of each cluster
    cluster_id_count = {}
    for row in results:
        if row["cid"] not in cluster_id_count:
            cluster_id_count[row["cid"]] = 0
        cluster_id_count[row["cid"]] += 1
    print(f"{cluster_id_count=}")

    """
    for row in results:
        if row["cid"] == 0:
            print(row["coord_east"], row["coord_north"], row["longitude"], row["latitude"])
            print("-" * 50)

            max_dist = 0
            min_dist = 1000000
            for row2 in results:
                if row2["cid"] == 0:
                    d = ((row["coord_east"] - row2["coord_east"]) ** 2 + (row["coord_north"] - row2["coord_north"]) ** 2) ** 0.5
                    max_dist = max(d, max_dist)
                    min_dist = min(min_dist, d)
            print(f"{min_dist=}")
            print(f"{max_dist=}")
            print()
    """

    scat_features: list = []
    min_lon, min_lat, max_lon, max_lat = 90, 90, -90, -90
    for row in results:
        # skip loci with value 0 or -

        """loci_val = rdis.get(row["wa_code"])
        if loci_val is None:
            continue
        d = json.loads(loci_val)
        """

        flag_ok = False

        d = fn.get_wa_loci_values_redis(row["wa_code"])

        for locus in d:
            for allele in d[locus]:
                if d[locus][allele]["value"] not in ("-", 0):
                    flag_ok = True
                    break
            if flag_ok:
                break
        else:  # not broken
            continue

        min_lon = min(min_lon, row["longitude"])
        min_lat = min(min_lat, row["latitude"])
        max_lon = max(max_lon, row["longitude"])
        max_lat = max(max_lat, row["latitude"])

        if row["cid"] is not None:
            color = matplotlib.colors.to_hex(cmap(row["cid"]), keep_alpha=False)
        else:
            color = "#000000"
        scat_feature = {
            "geometry": {
                "type": "Point",
                "coordinates": [row["longitude"], row["latitude"]],
            },  # dict(scat_geojson),
            "type": "Feature",
            "properties": {
                "style": {"color": color, "fillColor": color, "fillOpacity": 1},
                "popupContent": (
                    f"""Sample ID: <a href="/view_scat/{row["sample_id"]}" target="_blank">{row["sample_id"]}</a><br>"""
                    f"""WA code: <a href="/view_wa/{row["wa_code"]}" target="_blank">{row["wa_code"]}</a><br>"""
                    f"""Genotype ID: <b>{row["genotype_id"]}</b><br>"""
                    f"""Cluster ID {row["cid"]}:<br><a href="/wa_analysis/{distance}/{row["cid"]}">{cluster_id_count[row["cid"]]} samples</a> """
                    f"""<a href="/wa_analysis_group/DBSCAN-{distance}-{row["cid"]}/web">Genotypes</a>"""
                ),
            },
            "id": row["sample_id"],
        }

        scat_features.append(scat_feature)

    return render_template(
        "plot_clusters.html",
        header_title=f"WA codes clusters ({distance} m)",
        title=Markup(f"Plot of {len(scat_features)} WA codes clusters"),
        map=Markup(
            fn.leaflet_geojson(
                {
                    "scats": scat_features,
                    "scats_color": params["scat_color"],
                    "fit": [[min_lat, min_lon], [max_lat, max_lon]],
                }
            )
        ),
        distance=int(distance),
        minpoint=MINPOINT,
        clusters_number=len(cluster_id_count),
    )


@app.route(
    "/wa_genetic_samples/<int:offset>/<limit>",
    methods=(
        "GET",
        "POST",
    ),
)
@app.route(
    "/wa_genetic_samples/<int:offset>/<limit>/<filter>",
    methods=(
        "GET",
        "POST",
    ),
)
@app.route("/wa_genetic_samples/<int:offset>/<limit>/<filter>/<mode>")
@fn.check_login
def wa_genetic_samples(offset: int, limit: int | str, filter="all", mode="web"):
    """
    display genetic data for WA code
    filter: all / with notes / red_flag / no_values
    """

    if filter not in ("all", "with_notes", "red_flag", "no_values"):
        return "An error has occured. Check the URL"

    # test limit value: must be ALL or int
    if limit != "ALL":
        try:
            limit = int(limit)
        except Exception:
            return "An error has occured. Check the URL"

    if limit == "ALL":
        offset = 0

    # check if wa code is specified to scroll the table
    if "view_wa_code" in session:
        view_wa_code = session["view_wa_code"]
        del session["view_wa_code"]
    else:
        view_wa_code = None

    if request.method == "POST":
        offset = 0
        limit = "ALL"
        if request.args.get("search") is not None:
            search_term = request.args.get("search").strip()
        else:
            search_term = request.form["search"].strip()

    elif request.method == "GET":
        if request.args.get("search") is not None:
            search_term: str = request.args.get("search").strip()
        else:
            search_term: str = ""

    sql_all = "SELECT * FROM wa_genetic_samples_mat WHERE (date BETWEEN :start_date AND :end_date OR date IS NULL) "

    with fn.conn_alchemy().connect() as con:
        if ":" in search_term:
            sql_search = sql_all
            values: dict = {}
            for idx, field_term in enumerate(search_term.split(";")):
                field, value = [x.strip().lower() for x in field_term.split(":")]
                research_fields = (
                    "wa",
                    "date",
                    "sample id",
                    "municipality",
                    "province",
                    "genotype id",
                    "sex",
                    "tmp id",
                    "notes",
                    "pack",
                    "box",
                )
                if field not in research_fields:
                    flash(fn.alert_danger(f"Search term not found. Must be {'","'.join(research_fields)}"))
                    return redirect(session["url_wa_list"])

                field = field.replace(" ", "_")
                if field == "wa":
                    field = "wa_code"
                if field == "sex":
                    field = "sex_id"
                    values[f"search{idx}"] = value
                    sql_search += f" AND ({field} = :search{idx}) "
                elif field == "box":
                    field = "box_number"
                    values[f"search{idx}"] = value
                    sql_search += f" AND ({field} = :search{idx}) "
                else:
                    sql_search += f" AND ({field} ILIKE :search{idx}) "
                    values[f"search{idx}"] = f"%{value}%"

        else:
            values = {"search": f"%{search_term}%"}
            sql_search = sql_all + (
                " AND ("
                "wa_code ILIKE :search "
                "OR sample_id ILIKE :search "
                "OR date::text ILIKE :search "
                "OR municipality ILIKE :search "
                "OR genotype_id ILIKE :search "
                "OR tmp_id ILIKE :search "
                "OR notes ILIKE :search "
                "OR pack ILIKE :search "
                "OR box_number::text = :search "
                ") "
            )

        wa_scats = (
            con.execute(
                text(sql_all if not search_term else sql_search),
                dict(
                    {
                        "start_date": session["start_date"],
                        "end_date": session["end_date"],
                    },
                    **values,
                ),
            )
            .mappings()
            .all()
        )

    # loci list
    loci_list: dict = fn.get_loci_list()

    out: list = []
    loci_values: list = {}
    locus_notes: dict = {}
    mem_genotype_loci: dict = {}
    for row in wa_scats:
        # genotype working notes
        has_genotype_notes = True if (row["notes"] is not None and row["notes"]) else False

        loci_val = fn.get_wa_loci_values_redis(row["wa_code"])
        # loci_values[row["wa_code"]] = fn.get_wa_loci_values_redis(row["wa_code"])
        loci_values[row["wa_code"]] = dict(loci_val)

        has_loci_notes = False
        has_orange_loci_notes = False
        has_loci_values = False

        # check if loci have notes and values and corresponds to genotype loci
        for x in loci_values[row["wa_code"]]:
            for allele in ("a", "b"):
                if allele not in loci_values[row["wa_code"]][x]:
                    continue

                loci_values[row["wa_code"]][x][allele]["divergent_allele"] = ""

                if loci_values[row["wa_code"]][x][allele]["has_history"]:
                    if loci_values[row["wa_code"]][x][allele]["definitive"]:
                        loci_values[row["wa_code"]][x][allele]["color"] = params["green_note"]
                    else:
                        loci_values[row["wa_code"]][x][allele]["color"] = params["red_note"]
                        has_loci_notes = True

                if loci_values[row["wa_code"]][x][allele]["value"] not in (0, "-"):
                    has_loci_values = True

                # check if wa loci corresponds to genotype loci (if not the background colo will be orange)
                if row["genotype_id"]:
                    genotype_loci_val = {}
                    if mem_genotype_loci.get(row["genotype_id"], False):
                        genotype_loci_val = mem_genotype_loci[row["genotype_id"]]
                    else:
                        genotype_loci_val = fn.get_genotype_loci_values_redis(row["genotype_id"])
                        if genotype_loci_val is not None:
                            mem_genotype_loci[row["genotype_id"]] = genotype_loci_val
                        else:
                            print(f"Loci not found {row["genotype_id"]=}  {row["wa_code"]=}")

                    try:
                        if (
                            genotype_loci_val
                            and genotype_loci_val[x][allele]["value"] != loci_val[x][allele]["value"]
                            and loci_val[x][allele]["value"] not in (0, "-")
                            and loci_val[x][allele]["value"] not in (0, "-")
                        ):
                            has_orange_loci_notes = True
                            loci_values[row["wa_code"]][x][allele]["divergent_allele"] = Markup(
                                '<span style="font-size:24px">&#128312;</span>'
                            )
                            # check if allele has already a color
                    except Exception:
                        pass

        if filter == "no_values":
            out.append(dict(row))

        # skip if no loci values and no notes
        if not has_loci_values and not has_loci_notes:
            continue

        if (filter == "red_flag") and (has_loci_notes):
            out.append(dict(row))

        if (filter == "all") or (filter == "with_notes" and (has_genotype_notes or has_loci_notes)):
            out.append(dict(row))

        if has_loci_notes:
            locus_notes[row["wa_code"]] = Markup("&#128681;")  # red flag
        if has_orange_loci_notes:
            if row["wa_code"] in locus_notes:
                locus_notes[row["wa_code"]] += Markup("&#128312;")  # orange
            else:
                locus_notes[row["wa_code"]] = Markup("&#128312;")  # orange

    if mode == "export":
        file_content = export.export_wa_genetic_samples(loci_list, out, loci_values, filter)

        response = make_response(file_content, 200)
        response.headers["Content-type"] = "application/application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        response.headers["Content-disposition"] = f"attachment; filename=wa_genetic_samples_{dt.datetime.now():%Y-%m-%d_%H%M%S}.xlsx"

        return response

    else:
        # apply offset and limit
        n_wa = len(out)
        if limit != "ALL":
            out = out[offset : offset + limit]

        if n_wa:
            title = f"Genetic data of {n_wa} WA codes"
            match filter:
                case "with_notes":
                    title += " with notes"
                case "red_flag":
                    title += " with locus/allele notes"
                case "no_values":
                    title += " (including WA without loci values)"
        else:
            title = "No WA code found"

        session["url_wa_list"] = f"/wa_genetic_samples/{offset}/{limit}/{filter}?search={search_term}"
        if "url_scats_list" in session:
            del session["url_scats_list"]

        return render_template(
            "wa_genetic_samples_list_limit.html",
            header_title="Genetic data of WA codes",
            title=title,
            n_wa=n_wa,
            limit=limit,
            offset=offset,
            loci_list=loci_list,
            wa_scats=out,
            loci_values=loci_values,
            locus_notes=locus_notes,
            filter=filter,
            search_term=search_term,
            view_wa_code=view_wa_code,
        )


@app.route("/wa_analysis/<distance>/<int:cluster_id>")
@app.route("/wa_analysis/<distance>/<int:cluster_id>/<mode>")
@fn.check_login
def wa_analysis(distance: int, cluster_id: int, mode: str = "web"):
    """
    display cluster content
    excel add-in GenAIex
    """
    if mode not in ("web", "export", "ml-relate", "colony"):
        return "error: mode must be web, export or ml-relate"

    with fn.conn_alchemy().connect() as con:
        # loci list
        loci_list: list = fn.get_loci_list()

        # DBScan
        wa_list: list = []
        for row in (
            con.execute(
                text(
                    "SELECT wa_code, sample_id, municipality, cluster_id FROM "
                    "(SELECT wa_code, sample_id, municipality, "
                    "ST_ClusterDBSCAN(geometry_utm, eps:= :distance, minpoints:=1) OVER(ORDER BY wa_code) AS cluster_id "
                    "FROM wa_scat_dw_mat "
                    "WHERE mtdna != 'Poor DNA' "
                    "AND date BETWEEN :start_date AND :end_date) q WHERE cluster_id = :cluster_id "
                ),
                {
                    "start_date": session["start_date"],
                    "end_date": session["end_date"],
                    "distance": distance,
                    "cluster_id": cluster_id,
                },
            )
            .mappings()
            .all()
        ):
            wa_list.append(row["wa_code"])
        wa_list_str = "','".join(wa_list)

        wa_scats = (
            con.execute(
                text(
                    "SELECT wa_code, sample_id, date, municipality, coord_east, coord_north, coord_zone, "
                    "mtdna, genotype_id, tmp_id, sex_id, "
                    "(SELECT working_notes FROM genotypes WHERE genotype_id=wa_scat_dw_mat.genotype_id) AS notes, "
                    "(SELECT status FROM genotypes WHERE genotype_id=wa_scat_dw_mat.genotype_id) AS status, "
                    "(SELECT pack FROM genotypes WHERE genotype_id=wa_scat_dw_mat.genotype_id) AS pack, "
                    "(SELECT 'Yes' FROM dead_wolves WHERE tissue_id = sample_id LIMIT 1) as dead_recovery "
                    "FROM wa_scat_dw_mat "
                    f"WHERE wa_code IN ('{wa_list_str}') "
                    "AND date BETWEEN :start_date AND :end_date "
                    "ORDER BY wa_code ASC"
                ),
                {
                    "start_date": session["start_date"],
                    "end_date": session["end_date"],
                },
            )
            .mappings()
            .all()
        )

        loci_values: dict = {}
        count_samples_with_data: int = 0

        ml_relate: list = [f"Cluster id {cluster_id}"]

        # check if almost one value for locus (ML-Relate)
        for loci in loci_list:
            has_loci_values: bool = False
            for row in wa_scats:
                loci_values[row["wa_code"]] = fn.get_wa_loci_values_redis(row["wa_code"])

                for allele in ("a", "b"):
                    if allele not in loci_values[row["wa_code"]][loci]:
                        continue
                    if loci_values[row["wa_code"]][loci][allele]["value"] not in (
                        0,
                        "-",
                    ):
                        has_loci_values = True

            if has_loci_values:
                ml_relate.append(loci)

        ml_relate.append("Pop")

        out: list = []
        for row in wa_scats:
            if row["wa_code"] not in loci_values:
                continue

            # check if almost one locus has a value
            has_loci_values = False
            for locus in loci_values[row["wa_code"]]:
                for allele in ("a", "b"):
                    if allele not in loci_values[row["wa_code"]][loci]:
                        continue
                    if loci_values[row["wa_code"]][locus][allele]["value"] not in (
                        0,
                        "-",
                    ):
                        has_loci_values = True
                if has_loci_values:
                    break

            # Genepop / ML-relate
            mrl = row["wa_code"] + "\t,\t"
            for x in loci_values[row["wa_code"]]:
                if locus not in ml_relate:  # no value for locus
                    continue
                for allele in ("a", "b"):
                    if allele not in loci_values[row["wa_code"]][locus] or loci_values[row["wa_code"]][locus][allele]["value"] in (0, "-"):
                        mrl += "000"
                    else:
                        mrl += f"{loci_values[row['wa_code']][locus][allele]['value']:03}"
                mrl += "\t"

            if has_loci_values:
                out.append(row)
                ml_relate.append(mrl.strip())
                count_samples_with_data += 1

        if mode == "export":
            file_content = export.export_wa_analysis(loci_list, out, loci_values, distance, cluster_id)
            response = make_response(file_content, 200)
            response.headers["Content-type"] = "application/application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            response.headers["Content-disposition"] = (
                f"attachment; filename=cluster_id{cluster_id}_{dt.datetime.now():%Y-%m-%d_%H%M%S}.xlsx"
            )
            return response

        elif mode == "ml-relate":
            response = make_response("\n".join(ml_relate), 200)
            response.headers["Content-type"] = "text/plain"
            response.headers["Content-disposition"] = f"attachment; filename=cluster_id{cluster_id}_distance{distance}.txt"
            return response

        else:
            session["go_back_url"] = f"/wa_analysis/{distance}/{cluster_id}"

            return render_template(
                "wa_analysis.html",
                header_title=f"cluster ID: {cluster_id} distance: {distance} m) - WA matches",
                title=Markup(
                    (
                        f"Matches (cluster id: {cluster_id} distance: {distance} m) "
                        f"{count_samples_with_data} WA code{'s' if count_samples_with_data > 1 else ''} with data ({len(wa_scats)} total)"
                    )
                ),
                loci_list=loci_list,
                wa_scats=out,
                loci_values=loci_values,
                distance=distance,
                cluster_id=cluster_id,
                ml_relate="\n".join(ml_relate),
            )


def get_genotypes_from_wa(wa_list: list):
    """
    get genotype info from list of WA codes
    TODO: check if same genotype has 2 different sex
    """

    wa_list_str = "','".join(wa_list)
    with fn.conn_alchemy().connect() as con:
        # fetch grouped genotypes
        genotype_id = (
            con.execute(
                text(
                    "SELECT genotype_id, count(wa_code) AS n_recap, sex_id "
                    "FROM wa_scat_dw_mat "
                    f"WHERE wa_code in ('{wa_list_str}') "
                    "GROUP BY genotype_id, sex_id "
                    "ORDER BY genotype_id ASC"
                )
            )
            .mappings()
            .all()
        )
        return genotype_id


def get_genotypes_data(genotypes_info):
    """
    get info and loci values of genotypes
    """

    loci_values: dict = {}
    data: dict = {}
    count_sex: dict = {"M": 0, "F": 0, "": 0}

    with fn.conn_alchemy().connect() as con:
        for row in genotypes_info:
            if row["genotype_id"] is None:
                continue

            result = (
                con.execute(
                    text(
                        "SELECT *, "
                        "(SELECT 'Yes' FROM wa_scat_dw_mat "
                        "        WHERE (sample_type = 'Dead wolf' OR sample_id like 'M%') "
                        "              AND genotype_id=genotypes.genotype_id LIMIT 1) AS dead_recovery "
                        "FROM genotypes WHERE genotype_id = :genotype_id"
                    ),
                    {"genotype_id": row["genotype_id"]},
                )
                .mappings()
                .fetchone()
            )

            if result is None:
                continue
            data[row["genotype_id"]] = dict(result)
            data[row["genotype_id"]]["n_recap"] = row["n_recap"]
            count_sex[result["sex"]] += 1

            loci_values[row["genotype_id"]] = fn.get_genotype_loci_values_redis(row["genotype_id"])

    return data, loci_values, count_sex


def create_ml_relate_input(title: str, loci_values) -> str:
    """
    create the input data for ML-Relate software
    """
    ml_relate: list = [title]
    for locus in fn.get_loci_list():
        locus_has_values: bool = False
        for genotype in loci_values:
            for allele in ("a", "b"):
                if allele not in loci_values[genotype][locus]:
                    continue
                if loci_values[genotype][locus][allele]["value"] not in (0, "-"):
                    locus_has_values = True
        if locus_has_values:
            ml_relate.append(locus)
    ml_relate.append("Pop")
    for genotype in loci_values:
        mrl = genotype + "\t,\t"
        for locus in loci_values[genotype]:
            if locus not in ml_relate:  # no value for locus
                continue
            for allele in ("a", "b"):
                if loci_values[genotype][locus][allele]["value"] in (0, "-"):
                    mrl += "000"
                else:
                    mrl += f"{loci_values[genotype][locus][allele]['value']:03}"
            mrl += "\t"

        ml_relate.append(mrl.strip())

    return "\n".join(ml_relate)


@app.route("/view_wa_polygon/<polygon>/<mode>")
@fn.check_login
def view_wa_polygon(polygon: str, mode: str):
    """
    Display the WA contained in polygon
    """
    accepted_mode: tuple = ("web", "export")
    if mode not in accepted_mode:
        return f"mode error: mode must be {','.join(accepted_mode)}"

    with fn.conn_alchemy().connect() as con:
        # loci list
        loci_list: dict = fn.get_loci_list()

        sql_all = text(
            "SELECT * "
            "FROM wa_genetic_samples_mat "
            "WHERE (date BETWEEN :start_date AND :end_date OR date IS NULL) "
            "AND ST_Within(geometry_utm, st_transform(ST_GeomFromText(:wkt_polygon, 4326), ST_SRID(geometry_utm)))"
        )

        wa_list = (
            con.execute(
                sql_all,
                {
                    "wkt_polygon": polygon,
                    "start_date": session["start_date"],
                    "end_date": session["end_date"],
                },
            )
            .mappings()
            .all()
        )
    n_wa = len(wa_list)
    if n_wa == 0:
        return "No WA codes in polygon"

    loci_values: dict = {}
    for wa in wa_list:
        if wa["genotype_id"]:
            loci_values[wa["wa_code"]] = fn.get_genotype_loci_values_redis(wa["genotype_id"])

    if mode == "web":
        return render_template(
            "wa_list.html",
            header_title="WA codes",
            title=f"{n_wa} WA code{'s' if n_wa > 1 else ''}",
            loci_list=loci_list,
            n_wa=n_wa,
            wa_list=wa_list,
            loci_values=loci_values,
            polygon=polygon,
        )
    # XLSX format
    if mode == "export":
        file_content = export.export_wa(loci_list, wa_list, loci_values)
        response = make_response(file_content, 200)
        response.headers["Content-type"] = "application/application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        response.headers["Content-disposition"] = f"attachment; filename=wa_{dt.datetime.now():%Y-%m-%d_%H%M%S}.xlsx"
        return response


@app.route("/wa_analysis_group/<tool>/<mode>")
@fn.check_login
def wa_analysis_group(tool: str, mode: str):
    """
    display cluster content
    """
    accepted_mode: tuple = ("web", "export", "ml-relate", "colony", "run_colony")
    if mode not in accepted_mode:
        return f"mode error: mode must be {','.join(accepted_mode)}"

    with fn.conn_alchemy().connect() as con:
        # loci list
        loci_list: dict = fn.get_loci_list()

        distance = None
        cluster_id = None
        # DBScan
        if tool.startswith("DBSCAN"):
            distance, cluster_id = [int(x) for x in tool.split("-")[1:]]
            wa_list: list = []
            for row in (
                con.execute(
                    text(
                        "SELECT wa_code, "
                        f"ST_ClusterDBSCAN(geometry_utm, eps:={distance}, minpoints:=1) over() AS cluster_id "
                        "FROM wa_scat_dw_mat "
                        "WHERE mtdna != 'Poor DNA' "
                        "AND date BETWEEN :start_date AND :end_date "
                    ),
                    {
                        "start_date": session["start_date"],
                        "end_date": session["end_date"],
                    },
                )
                .mappings()
                .all()
            ):
                if row["cluster_id"] == cluster_id:
                    wa_list.append(row["wa_code"])

        if tool.startswith("POLYGON"):
            wa_codes = (
                con.execute(
                    text(
                        "SELECT wa_code FROM wa_scat_dw_mat WHERE "
                        "mtdna != 'Poor DNA' "
                        "AND date BETWEEN :start_date AND :end_date "
                        "AND ST_Within(geometry_utm, st_transform(ST_GeomFromText(:wkt_polygon, 4326), 32632))"
                    ),
                    {
                        "wkt_polygon": tool,
                        "start_date": session["start_date"],
                        "end_date": session["end_date"],
                    },
                )
                .mappings()
                .all()
            )
            if len(wa_codes) == 0:
                return "No WA codes selected"

            # get postgresql geometry
            with fn.conn_alchemy().connect() as con:
                text_geom_md5 = (
                    con.execute(
                        text("select MD5(ST_GeomFromText(:wkt_polygon)::text) AS geometry "),
                        {
                            "wkt_polygon": tool,
                        },
                    )
                    .mappings()
                    .fetchone()["geometry"]
                )

            wa_list = [x["wa_code"] for x in wa_codes]

    # fetch grouped genotypes
    genotypes_info = get_genotypes_from_wa(wa_list)

    data, loci_values, count_sex = get_genotypes_data(genotypes_info)

    colony_output_dir = pl.Path("colony_output")
    colony_output_path = pl.Path(current_app.static_folder) / colony_output_dir

    if not colony_output_path.is_dir():
        colony_output_path.mkdir(parents=True, exist_ok=True)

    if "colony" in mode:
        # load the colony template
        with open("external_functions/colony_template.dat", "r") as file_in:
            colony_template = jinja2.Template(file_in.read())

        # load the loci list to use with colony
        colony_loci: set = set()
        with fn.conn_alchemy().connect() as con:
            for row in con.execute(text("SELECT name FROM loci WHERE use_with_colony = true")).mappings().all():
                colony_loci.add(row["name"])

        with open("external_functions/loci_to_use_with_colony.txt", "r") as file_in:
            colony_loci = [x.strip().upper() for x in file_in.readlines()]

        """print(f"{colony_loci=}")"""

        valid_locus: list = []
        for locus in loci_list:
            if locus.upper() not in colony_loci:
                continue
            """ print()
            print(f"{locus=}")
            """
            locus_has_values: bool = False
            for genotype in loci_values:
                # print(f"{genotype=}")
                for allele in ("a", "b"):
                    if allele not in loci_values[genotype][locus]:
                        continue
                    # print(f"{allele} {loci_values[genotype][locus][allele]=}")
                    if loci_values[genotype][locus][allele]["value"] not in (0, "-"):
                        locus_has_values = True
            if locus_has_values:
                valid_locus.append(locus)

        allele_data = []
        allele_data.append("     " + ("     ".join(valid_locus)))
        allele_data.append("     " + ("     ".join(["0"] * len(valid_locus))))
        allele_data.append("")
        allele_data.append("  ".join(["0.01"] * len(valid_locus)))
        allele_data.append("  ".join(["0.01"] * len(valid_locus)))
        allele_data.extend(["", ""])
        for genotype in loci_values:
            row = genotype + " "

            for locus in loci_values[genotype]:
                if locus not in valid_locus:  # no value for locus
                    continue
                for allele in ("a", "b"):
                    if loci_values[genotype][locus][allele]["value"] in (0, "-"):
                        row += "0 "
                    else:
                        row += f"{loci_values[genotype][locus][allele]['value']:03} "
                row += " "

            allele_data.append(row.strip())

        allele_sex: dict = {}
        for sex in ("M", "F"):
            allele_sex[sex] = []
            for genotype in loci_values:
                if data[genotype]["sex"] != sex:
                    continue
                row = genotype + " "
                for locus in loci_values[genotype]:
                    if locus not in valid_locus:  # no value for locus
                        continue
                    for allele in ("a", "b"):
                        if loci_values[genotype][locus][allele]["value"] in (0, "-"):
                            row += "0 "
                        else:
                            row += f"{loci_values[genotype][locus][allele]['value']:03} "
                    row += " "

                allele_sex[sex].append(row.strip())

        colony_out = [
            colony_template.render(
                dataset_name=f"genotypes_cluster_id{cluster_id}_distance{distance}",
                output_file_name=f"genotypes_cluster_id{cluster_id}_distance{distance}",
                offspring_number=len(allele_sex["M"]) + len(allele_sex["F"]),
                loci_number=len(valid_locus),
                alleles="\n".join(allele_data),
                n_male=count_sex["M"],
                n_female=count_sex["F"],
                male_alleles="\n".join(allele_sex["M"]),
                female_alleles="\n".join(allele_sex["F"]),
            )
        ]

    if mode == "export":
        file_content = export.export_wa_analysis_group(loci_list, data, loci_values)
        response = make_response(file_content, 200)
        response.headers["Content-type"] = "application/application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        response.headers["Content-disposition"] = f"attachment; filename=genotypes_{dt.datetime.now():%Y-%m-%d_%H%M%S}.xlsx"
        return response

    elif mode == "colony":
        response = make_response("\n".join(colony_out), 200)
        response.headers["Content-type"] = "text/plain"

        if tool.startswith("DBSCAN"):
            default_file_name = f"genotypes_cluster_id{cluster_id}_distance{distance}.dat"
            response.headers["Content-disposition"] = f"attachment; filename={default_file_name}"

        if tool.startswith("POLYGON"):
            default_file_name = f"{len(loci_values)}_genotypes_selected_on_map.dat"
        response.headers["Content-disposition"] = f"attachment; filename={default_file_name}"
        return response

    elif mode == "run_colony":
        if tool.startswith("DBSCAN"):
            input_file_name = colony_output_path / pl.Path(f"{distance}_{cluster_id}")
            with open(f"{input_file_name}.dat", "w") as file_out:
                file_out.write("\n".join(colony_out))

        if tool.startswith("POLYGON"):
            input_file_name = colony_output_path / pl.Path(text_geom_md5)
            with open(f"{input_file_name}.dat", "w") as file_out:
                file_out.write("\n".join(colony_out))

        if not pl.Path(params["colony_path"]).is_file():
            flash(fn.alert_danger("The Colony program was not found. Please contact the administrator."))
            return redirect(f"/wa_analysis_group/{tool}/web")

        with open(f"{input_file_name}.stdout", "w") as colony_stdout:
            _ = subprocess.Popen(
                [
                    params["colony_path"],
                    f"IFN:{input_file_name}.dat",
                    f"OFN:{input_file_name}",
                ],
                stdout=colony_stdout,
            )

        # wait few seconds for errormessage
        time.sleep(4)

        # check if colony errormessage file exists
        colony_error_message: str = ""
        if pl.Path("Colony2.ErrorMessage").is_file():
            # read file content
            with open(pl.Path("Colony2.ErrorMessage"), "r") as file_in:
                colony_error_message = file_in.read()
            pl.Path("Colony2.ErrorMessage").unlink()
            flash(
                fn.alert_danger(
                    (
                        "<b>ERROR: Colony returns the following message</b>:<br>"
                        f"<pre>{colony_error_message}</pre><br>"
                        "Use the <b>Export for Colony</b> button to check the input file."
                    )
                )
            )
            return redirect(f"/wa_analysis_group/{tool}/web")

        flash(fn.alert_success("<b>The Colony program is running</b>. Reload the page continuously (F5) until the results are displayed."))

        return redirect(f"/wa_analysis_group/{tool}/web")

    # Genepop format (for ML-Relate)
    elif mode == "ml-relate":
        if tool.startswith("DBSCAN"):
            title = f"Cluster id {cluster_id}"
            default_file_name = f"ML-Relate_genotypes_cluster_id{cluster_id}_distance{distance}.txt"
        else:
            title = "selected on map"
            default_file_name = f"ML-Relate_{len(loci_values)}_genotypes_selected_on_map.txt"

        ml_relate = create_ml_relate_input(title, loci_values)

        response = make_response(ml_relate, 200)
        response.headers["Content-type"] = "text/plain"
        response.headers["Content-disposition"] = f"attachment; filename={default_file_name}"
        return response

    else:  # html
        colony_results_content: str = ""
        colony_result: str = ""

        if tool.startswith("DBSCAN"):
            header_title = f"Genotype{'s' if len(loci_values) > 1 else ''} for cluster ID: {cluster_id} distance: {distance} m))"
            page_title = Markup(
                f"DBSCAN cluster id: {cluster_id} distance: {distance} m - <b>{len(loci_values)}</b> genotype{'s' if len(loci_values) > 1 else ''}"
            )

            colony_output_file = pl.Path(f"{distance}_{cluster_id}.BestConfig_Ordered")
            colony_output_file_path = colony_output_path / colony_output_file

        if tool.startswith("POLYGON"):
            header_title = f"Genotype{'s' if len(loci_values) > 1 else ''} for selected WA codes"
            page_title = Markup(f"{len(loci_values)} genotype{'s' if len(loci_values) > 1 else ''} for selected WA codes")

            colony_output_file = pl.Path(f"{text_geom_md5}.BestConfig_Ordered")
            colony_output_file_path = colony_output_path / colony_output_file

        # check colony results file already exists
        if colony_output_file_path.is_file():
            colony_result = "/static" / colony_output_dir / colony_output_file
            # read file content
            with open(colony_output_file_path, "r") as file_in:
                colony_results_content = file_in.read()

        return render_template(
            "wa_analysis_group.html",
            header_title=header_title,
            title=page_title,
            tool=tool,
            loci_list=loci_list,
            genotypes_info=genotypes_info,
            data=data,
            loci_values=loci_values,
            distance=distance,
            cluster_id=cluster_id,
            colony_result=colony_result,
            colony_results_content=colony_results_content,
        )


@app.route("/view_genetic_data/<wa_code>")
@fn.check_login
def view_genetic_data(wa_code: str):
    """
    visualize genetic data for WA code
    """

    session["view_wa_code"] = wa_code

    with fn.conn_alchemy().connect() as con:
        # get info about WA code
        row = (
            con.execute(
                text("SELECT sex_id, genotype_id FROM wa_results WHERE wa_code = :wa_code"),
                {"wa_code": wa_code},
            )
            .mappings()
            .fetchone()
        )

        if row is None:
            flash(fn.alert_danger(f"WA code {wa_code} not found"))
            return redirect(request.referrer)

        sex = row["sex_id"]
        genotype_id = row["genotype_id"]

        # loci list
        loci_list = fn.get_loci_list()

        wa_loci = fn.get_wa_loci_values_redis(wa_code)

        # genotype_loci = fn.get_genotype_loci_values(row["genotype_id"], loci_list)
        genotype_loci = fn.get_genotype_loci_values_redis(row["genotype_id"])

        for locus in loci_list:
            for allele in ("a", "b"):
                if allele not in wa_loci[locus]:
                    continue
                # check wa / genotype
                if genotype_loci and genotype_loci[locus][allele]["value"] != wa_loci[locus][allele]["value"]:
                    wa_loci[locus][allele]["divergent_allele"] = Markup(
                        f"""<button type="button" class="btn btn-warning btn-sm">{genotype_loci[locus][allele]["value"]}</button>"""
                    )
                if wa_loci[locus][allele]["notes"]:
                    if not wa_loci[locus][allele]["definitive"]:
                        wa_loci[locus][allele]["bgcolor"] = params["red_note"]
                    else:
                        wa_loci[locus][allele]["bgcolor"] = params["green_note"]
                else:
                    wa_loci[locus][allele]["bgcolor"] = "#ffffff00"

        return render_template(
            "view_genetic_data.html",
            header_title=f"{wa_code} genetic data",
            wa_code=wa_code,
            loci_list=loci_list,
            sex=sex,
            genotype_id=genotype_id,
            data=wa_loci,
            genotype_loci=genotype_loci,
        )


@app.route(
    "/add_genetic_data/<wa_code>",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def add_genetic_data(wa_code: str):
    """
    Let user add loci values for WA code
    """
    with fn.conn_alchemy().connect() as con:
        # get info about WA code
        row = (
            con.execute(
                text("SELECT sex_id, genotype_id FROM wa_results WHERE wa_code = :wa_code"),
                {"wa_code": wa_code},
            )
            .mappings()
            .fetchone()
        )

        loci = con.execute(text("SELECT * FROM loci ORDER BY position ASC")).mappings().all()

        # loci list
        loci_list = fn.get_loci_list()

        wa_loci = fn.get_wa_loci_values_redis(wa_code)

        # genotype_loci = fn.get_genotype_loci_values(row["genotype_id"], loci_list)
        genotype_loci = fn.get_genotype_loci_values_redis(row["genotype_id"])

        for locus in loci_list:
            for allele in ("a", "b"):
                if allele not in wa_loci[locus]:
                    continue
                # check wa / genotype
                if genotype_loci and genotype_loci[locus][allele]["value"] != wa_loci[locus][allele]["value"]:
                    wa_loci[locus][allele]["divergent_allele"] = Markup(
                        f"""<button type="button" class="btn btn-warning btn-sm">{genotype_loci[locus][allele]["value"]}</button>"""
                    )
                if wa_loci[locus][allele]["notes"]:
                    if not wa_loci[locus][allele]["definitive"]:
                        wa_loci[locus][allele]["bgcolor"] = params["red_note"]
                    else:
                        wa_loci[locus][allele]["bgcolor"] = params["green_note"]
                else:
                    wa_loci[locus][allele]["bgcolor"] = "#ffffff00"

        if request.method == "GET":
            return render_template(
                "add_genetic_data.html",
                header_title=f"Add genetic data for {wa_code}",
                go_back_url=request.referrer,
                wa_code=wa_code,
                loci=loci,
                loci_values=wa_loci,
                sex=row["sex_id"],
                genotype_id=row["genotype_id"],
            )

        if request.method == "POST":
            # set sex
            con.execute(
                text("UPDATE wa_results SET sex_id = :sex_id WHERE wa_code = :wa_code"),
                {"sex_id": request.form["sex"], "wa_code": wa_code},
            )
            after_wa_results_modif()
            # test sex for all WA codes
            rows = (
                con.execute(
                    text(
                        "SELECT DISTINCT sex_id FROM wa_results WHERE genotype_id in (SELECT genotype_id FROM wa_results where wa_code = :wa_code)"
                    ),
                    {"wa_code": wa_code},
                )
                .mappings()
                .fetchall()
            )
            if len(rows) == 1:  # same sex value for all WA codes -> Set genotype
                con.execute(
                    text(
                        "UPDATE genotypes SET sex = :sex WHERE genotype_id = (SELECT genotype_id FROM wa_results WHERE wa_code = :wa_code)"
                    ),
                    {"sex": rows[0]["sex_id"], "wa_code": wa_code},
                )
                after_genotype_modif()

            current_epoch = int(time.time())
            for locus in loci:
                for allele in ("a", "b"):
                    if locus["name"] + f"_{allele}" in request.form and request.form[locus["name"] + f"_{allele}"]:
                        con.execute(
                            text(
                                "INSERT INTO wa_locus "
                                "(wa_code, locus, allele, val, timestamp, notes, user_id, definitive) "
                                "VALUES (:wa_code, :locus, :allele, :val, to_timestamp(:current_epoch), :notes, :user_id, :definitive)"
                            ),
                            {
                                "wa_code": wa_code,
                                "locus": locus["name"],
                                "allele": allele,
                                "val": int(request.form[locus["name"] + f"_{allele}"])
                                if request.form[locus["name"] + f"_{allele}"]
                                else None,
                                "current_epoch": current_epoch,
                                "notes": request.form[locus["name"] + f"_{allele}_notes"]
                                if request.form[locus["name"] + f"_{allele}_notes"]
                                else None,
                                "user_id": session.get("user_name", session["email"]),
                                "definitive": True,
                            },
                        )

            # update redis
            rdis.set(wa_code, json.dumps(fn.get_wa_loci_values(wa_code, loci_list)[0]))

            # update genotype_locus

            for locus in loci:
                for allele in ("a", "b"):
                    if locus["name"] + f"_{allele}" in request.form and request.form[locus["name"] + f"_{allele}"]:
                        sql = text(
                            "SELECT DISTINCT (SELECT val FROM wa_locus WHERE locus = :locus AND allele = :allele AND wa_code = wa_scat_dw_mat.wa_code ORDER BY timestamp DESC LIMIT 1) AS val "
                            "FROM wa_scat_dw_mat "
                            "WHERE genotype_id = (SELECT genotype_id FROM wa_results WHERE wa_code = :wa_code)"
                        )
                        rows = (
                            con.execute(
                                sql,
                                {
                                    "locus": locus["name"],
                                    "allele": allele,
                                    "wa_code": wa_code,
                                },
                            )
                            .mappings()
                            .all()
                        )

                        if len(rows) == 1:  # all wa code have the same value
                            sql = text(
                                "SELECT distinct (SELECT id FROM genotype_locus where locus = :locus AND allele = :allele AND genotype_id = wa_scat_dw_mat.genotype_id ORDER BY timestamp DESC LIMIT 1) AS id "
                                "FROM wa_scat_dw_mat "
                                "WHERE genotype_id = (SELECT genotype_id FROM wa_results where wa_code = :wa_code)"
                            )

                            rows2 = (
                                con.execute(
                                    sql,
                                    {
                                        "locus": locus["name"],
                                        "allele": allele,
                                        "wa_code": wa_code,
                                    },
                                )
                                .mappings()
                                .all()
                            )

                            for row2 in rows2:
                                con.execute(
                                    text(
                                        "UPDATE genotype_locus "
                                        "SET notes = :notes, "
                                        "val = :val, "
                                        "timestamp = NOW(), "
                                        "user_id = :user_id "
                                        "WHERE id = :id"
                                    ),
                                    {
                                        "notes": request.form[locus["name"] + f"_{allele}_notes"]
                                        if request.form[locus["name"] + f"_{allele}_notes"]
                                        else None,
                                        "id": row2["id"],
                                        "val": int(request.form[locus["name"] + f"_{allele}"])
                                        if request.form[locus["name"] + f"_{allele}"]
                                        else None,
                                        "user_id": session.get("user_name", session["email"]),
                                    },
                                )

                                # get genotype id
                                genotype_id = (
                                    con.execute(
                                        text("SELECT genotype_id FROM genotype_locus WHERE id = :id"),
                                        {"id": row2["id"]},
                                    )
                                    .mappings()
                                    .fetchone()["genotype_id"]
                                )

                                rdis.set(
                                    genotype_id,
                                    json.dumps(fn.get_genotype_loci_values(genotype_id, loci_list)),
                                )

            return redirect(f"/view_genetic_data/{wa_code}")


@app.route("/view_genetic_data_history/<wa_code>/<locus>")
@fn.check_login
def view_genetic_data_history(wa_code: str, locus: str):
    with fn.conn_alchemy().connect() as con:
        # get info about WA code
        row = (
            con.execute(
                text("SELECT sex_id, genotype_id FROM wa_results WHERE wa_code = :wa_code"),
                {"wa_code": wa_code},
            )
            .mappings()
            .fetchone()
        )
        sex = row["sex_id"]
        genotype_id = row["genotype_id"]

        # get locus value
        locus_values = (
            con.execute(
                text(
                    (
                        "SELECT allele, val, to_char(timestamp, 'YYYY-MM-DD HH24:MI:SS') AS timestamp, notes, user_id, "
                        "CASE WHEN definitive IS NULL THEN ''::text ELSE definitive::text END "
                        "FROM wa_locus WHERE wa_code = :wa_code and locus = :locus ORDER BY allele, timestamp ASC"
                    )
                ),
                {"wa_code": wa_code, "locus": locus},
            )
            .mappings()
            .all()
        )

        return render_template(
            "view_genetic_data_history.html",
            header_title=f"{wa_code} genetic data",
            wa_code=wa_code,
            locus=locus,
            locus_values=locus_values,
            sex=sex,
            genotype_id=genotype_id,
        )


@app.route(
    "/locus_note/<wa_code>/<locus>/<allele>",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def wa_locus_note(wa_code: str, locus: str, allele: str):
    """
    let authorized user to add a note on wa_code locus_name allele timestamp
    user with 'allele modifier' permission can set 'definitive' value
    """

    session["view_wa_code"] = wa_code

    with fn.conn_alchemy().connect() as con:
        data = {"wa_code": wa_code, "locus": locus, "allele": allele}

        if request.method == "GET":
            data["allele_modifier"] = fn.get_allele_modifier(session["email"])

            notes = (
                con.execute(
                    text(
                        "SELECT wa_code, locus, allele, notes, user_id, "
                        "val, definitive, "
                        "date_trunc('second', timestamp) AS timestamp "
                        "FROM wa_locus WHERE wa_code = :wa_code AND locus = :locus AND allele = :allele "
                        "ORDER BY timestamp ASC"
                    ),
                    data,
                )
                .mappings()
                .all()
            )
            if not notes:
                flash(fn.alert_danger("Error with allele value"))
                return redirect(session["url_wa_list"])

            data["value"] = notes[-1]["val"]
            data["definitive"] = notes[-1]["definitive"]
            data["user_id"] = notes[-1]["user_id"]

            # other allele value
            other_allele = (
                con.execute(
                    text(
                        "SELECT val, definitive "
                        "FROM wa_locus WHERE wa_code = :wa_code AND locus = :locus AND allele != :allele "
                        "ORDER BY timestamp DESC "
                        "LIMIT 1"
                    ),
                    data,
                )
                .mappings()
                .fetchone()
            )
            data["other_allele_value"] = other_allele["val"] if other_allele is not None else "-"

            # genotype id
            query_result = (
                con.execute(
                    text("SELECT genotype_id, sex_id FROM wa_results WHERE wa_code = :wa_code "),
                    data,
                )
                .mappings()
                .fetchone()
            )
            data["genotype_id"] = query_result["genotype_id"] if query_result is not None else ""
            data["genotype_sex"] = query_result["sex_id"] if query_result is not None else ""

            # genotype allele value
            genotype_loci = fn.get_genotype_loci_values_redis(data["genotype_id"])
            data["genotype_allele"] = genotype_loci[locus].get(allele, "")

            return render_template(
                "add_wa_locus_note.html",
                header_title="Allele's notes",
                data=data,
                notes=notes,
            )

        if request.method == "POST":
            # check if allele value is numeric or -

            if request.form.get("new_value", None):  # allele modifier
                try:
                    new_value = int(request.form["new_value"])
                    if new_value < 0:
                        flash(
                            fn.alert_danger(
                                f"The allele value <b>{request.form['new_value']}</b> is not allowed. Must be <b>numeric (positive)</b> or <b>empty</b>."
                            )
                        )
                        return redirect(f"/locus_note/{wa_code}/{locus}/{allele}")

                except ValueError:
                    flash(
                        fn.alert_danger(
                            f"The allele value <b>{request.form['new_value']}</b> is not allowed. Must be <b>numeric</b> or <b>empty</b>."
                        )
                    )
                    return redirect(f"/locus_note/{wa_code}/{locus}/{allele}")

            else:
                # get last value for locus / allele
                last_note = (
                    con.execute(
                        text(
                            "SELECT val "
                            "FROM wa_locus WHERE wa_code = :wa_code AND locus = :locus AND allele = :allele "
                            "ORDER BY timestamp DESC"
                        ),
                        data,
                    )
                    .mappings()
                    .fetchone()
                )
                if not last_note:
                    flash(fn.alert_danger("Error with allele value"))
                    return redirect(session["url_wa_list"])

                new_value = last_note["val"]

            sql = text(
                "INSERT INTO wa_locus "
                "(wa_code, locus, allele, val, timestamp, notes, user_id, definitive) "
                "VALUES ("
                ":wa_code,"
                ":locus,"
                ":allele,"
                ":new_value,"
                "NOW(),"
                ":new_note,"
                ":user_id,"
                ":definitive"
                ")",
            )

            data["new_value"] = new_value
            data["new_note"] = request.form["new_note"]
            data["user_id"] = session.get("user_name", session["email"])
            data["definitive"] = "definitive" in request.form

            con.execute(sql, data)

            rdis.set(
                wa_code,
                json.dumps(fn.get_wa_loci_values(wa_code, fn.get_loci_list())[0]),
            )

            return redirect(f"/locus_note/{wa_code}/{locus}/{allele}")


@app.route(
    "/genotype_locus_note/<genotype_id>/<locus>/<allele>",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def genotype_locus_note(genotype_id: str, locus: str, allele: str):
    """
    let user add a note on genotype_id locus allele timestamp
    """

    session["view_genotype_id"] = genotype_id

    with fn.conn_alchemy().connect() as con:
        data = {"genotype_id": genotype_id, "locus": locus, "allele": allele}

        genotype_locus = (
            con.execute(
                text(
                    "SELECT * FROM genotype_locus WHERE genotype_id = :genotype_id AND locus = :locus AND allele = :allele ORDER BY timestamp DESC LIMIT 1"
                ),
                data,
            )
            .mappings()
            .fetchone()
        )

        if genotype_locus is None:
            return "Genotype ID / Locus / allele / timestamp not found"

        data["allele"] = allele
        data["value"] = genotype_locus["val"] if genotype_locus["val"] is not None else "-"
        data["validated"] = genotype_locus["validated"] if genotype_locus["validated"] is not None else ""
        data["notes"] = "" if genotype_locus["notes"] is None else genotype_locus["notes"]
        data["user_id"] = "" if genotype_locus["user_id"] is None else genotype_locus["user_id"]

        data["allele_modifier"] = fn.get_allele_modifier(session["email"])

        if request.method == "GET":
            values_history = (
                con.execute(
                    text(
                        "SELECT val AS value, "
                        "CASE WHEN notes IS NULL THEN '' ELSE notes END, "
                        "CASE WHEN user_id IS NULL THEN '' ELSE user_id END, "
                        "date_trunc('second', timestamp) AS timestamp, "
                        "CASE WHEN validated IS TRUE THEN 'Yes' ELSE '' END AS validated "
                        "FROM genotype_locus "
                        "WHERE genotype_id = :genotype_id "
                        "AND locus = :locus "
                        "AND allele = :allele "
                        "ORDER BY timestamp ASC "
                    ),
                    data,
                )
                .mappings()
                .all()
            )

            # other allele value
            other_allele = (
                con.execute(
                    text(
                        "SELECT val "
                        "FROM genotype_locus WHERE genotype_id = :genotype_id AND locus = :locus AND allele != :allele "
                        "ORDER BY timestamp DESC "
                        "LIMIT 1"
                    ),
                    data,
                )
                .mappings()
                .fetchone()
            )
            data["other_allele_value"] = other_allele["val"] if other_allele is not None else "-"

            return render_template(
                "add_genotype_locus_note.html",
                header_title="Add note on genotype id",
                data=data,
                values_history=values_history,
            )

        if request.method == "POST":
            sql = text(
                "INSERT INTO genotype_locus "
                "(genotype_id, locus, allele, "
                "val, "
                "validated, "
                "timestamp, "
                "notes, user_id) "
                "VALUES ("
                ":genotype_id,"
                ":locus,"
                ":allele,"
                ":value,"
                ":validated,"
                "NOW(),"
                ":notes,"
                ":user_id"
                ")",
            )

            # allele validation
            data["validated"] = False
            if data["allele_modifier"] and "validated" in request.form:
                data["validated"] = True

            data["notes"] = request.form["notes"]
            data["user_id"] = session.get("user_name", session["email"])

            con.execute(sql, data)

            # update cache
            loci_list: dict = fn.get_loci_list()

            rdis.set(
                genotype_id,
                json.dumps(fn.get_genotype_loci_values(genotype_id, loci_list)),
            )

            # update wa_code with genotype note
            sql = text(
                "SELECT id, wa_locus.wa_code AS wa_code FROM wa_locus, wa_results "
                "WHERE wa_locus.wa_code = wa_results.wa_code "
                "AND wa_results.genotype_id = :genotype_id "
                "AND wa_locus.locus = :locus "
                "AND allele = :allele "
                "AND val = :value "
            )
            for row in (
                con.execute(
                    sql,
                    {
                        "genotype_id": genotype_id,
                        "locus": locus,
                        "allele": allele,
                        "value": data["value"],
                    },
                )
                .mappings()
                .all()
            ):
                con.execute(
                    text("UPDATE wa_locus SET notes = :notes, user_id = :user_id WHERE id = :id "),
                    {
                        "notes": data["notes"],
                        "id": row["id"],
                        "user_id": session.get("user_name", session["email"]),
                    },
                )

                # update wa loci
                # [0] for accessing values
                rdis.set(
                    row["wa_code"],
                    json.dumps(fn.get_wa_loci_values(row["wa_code"], loci_list)[0]),
                )

            return redirect(f"/genotype_locus_note/{genotype_id}/{locus}/{allele}")


@app.route(
    "/genotype_note/<genotype_id>",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def genotype_note(genotype_id: str):
    """
    let user add a note on genotype_id (working_notes)
    """

    data = {"genotype_id": genotype_id}

    if request.method == "GET":
        with fn.conn_alchemy().connect() as con:
            notes_row = (
                con.execute(
                    text("SELECT working_notes FROM genotypes WHERE genotype_id = :genotype_id"),
                    {"genotype_id": genotype_id},
                )
                .mappings()
                .fetchone()
            )
            if notes_row is None:
                flash(fn.alert_danger(f"Genotype ID not found: {genotype_id}"))
                return redirect(request.referrer)

            data["working_notes"] = "" if notes_row["working_notes"] is None else notes_row["working_notes"]

            session["redirect_url"] = request.referrer

            return render_template(
                "add_genotype_note.html",
                header_title=f"Add note to genotype {genotype_id}",
                data=data,
                back_url=session["redirect_url"],
            )

    if request.method == "POST":
        with fn.conn_alchemy().connect() as con:
            sql = text("UPDATE genotypes SET working_notes = :working_notes WHERE genotype_id = :genotype_id")
            data["working_notes"] = request.form["working_notes"]
            con.execute(sql, data)

            after_genotype_modif()

            if "redirect_url" in session:
                redirect_url = session["redirect_url"]
                del session["redirect_url"]
                return redirect(redirect_url)
            else:
                return redirect("/")


def after_genotype_modif() -> None:
    """
    refresh materialized views after modification of genotypes table
    """

    with fn.conn_alchemy().connect() as con:
        con.execute(text("REFRESH MATERIALIZED VIEW genotypes_list_mat"))
        con.execute(text("REFRESH MATERIALIZED VIEW wa_genetic_samples_mat"))


def after_wa_results_modif() -> None:
    """
    refresh materialized views after modification of wa_results table
    """

    with fn.conn_alchemy().connect() as con:
        con.execute(text("REFRESH MATERIALIZED VIEW wa_scat_dw_mat"))
        con.execute(text("REFRESH MATERIALIZED VIEW scats_list_mat"))

    after_genotype_modif()


@app.route(
    "/set_wa_genotype/<wa_code>",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def set_wa_genotype(wa_code: str):
    """
    set wa genotype
    """

    session["view_wa_code"] = wa_code

    with fn.conn_alchemy().connect() as con:
        if request.method == "GET":
            with fn.conn_alchemy().connect() as con:
                result = (
                    con.execute(
                        text("SELECT genotype_id FROM wa_results WHERE wa_code = :wa_code "),
                        {"wa_code": wa_code},
                    )
                    .mappings()
                    .fetchone()
                )
            if result is None:
                flash(fn.alert_danger(f"WA code not found: {wa_code}"))
                return redirect(session["url_wa_list"])

            genotype_id = "" if result["genotype_id"] is None else result["genotype_id"]

            return render_template(
                "set_wa_genotype.html",
                header_title=f"Set genotype ID for WA code {wa_code}",
                wa_code=wa_code,
                current_genotype_id=genotype_id,
                return_url=request.referrer,
            )

        if request.method == "POST":
            # check if genotype exists
            with fn.conn_alchemy().connect() as con:
                genotype_exists = (
                    con.execute(
                        text("SELECT genotype_id FROM genotypes WHERE genotype_id = :genotype_id"),
                        {"genotype_id": request.form["genotype_id"].strip()},
                    )
                    .mappings()
                    .fetchone()
                )

                if genotype_exists is None:
                    flash(
                        fn.alert_danger(
                            f"<strong>Attention!</strong><br>The genotype <strong>{request.form['genotype_id']}</strong> does not exits."
                        )
                    )
                    return redirect(url_for("genetic.set_wa_genotype", wa_code=wa_code))

            with fn.conn_alchemy().connect() as con:
                sql = text("UPDATE wa_results SET genotype_id = :genotype_id WHERE wa_code = :wa_code")
                con.execute(
                    sql,
                    {
                        "genotype_id": request.form["genotype_id"].strip(),
                        "wa_code": wa_code,
                    },
                )

            after_wa_results_modif()

            return redirect(session["url_wa_list"])


@app.route(
    "/set_status/<genotype_id>",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def set_status(genotype_id):
    """
    let user set the status of the individual
    """

    with fn.conn_alchemy().connect() as con:
        if request.method == "GET":
            result = (
                con.execute(
                    text("SELECT status FROM genotypes WHERE genotype_id = :genotype_id"),
                    {"genotype_id": genotype_id},
                )
                .mappings()
                .fetchone()
            )

            if result is None:
                flash(fn.alert_danger(f"Genotype ID not found: {genotype_id}"))
                return redirect(request.referrer)

            status = "" if result["status"] is None else result["status"]

            session["redirect_url"] = request.referrer

            return render_template(
                "set_status.html",
                header_title="Set status",
                genotype_id=genotype_id,
                current_status=status,
                back_url=session["redirect_url"],
            )

        if request.method == "POST":
            sql = text("UPDATE genotypes SET status = :status WHERE genotype_id = :genotype_id")
            con.execute(
                sql,
                {
                    "status": request.form["status"].strip().lower(),
                    "genotype_id": genotype_id,
                },
            )
            after_genotype_modif()

            if "redirect_url" in session:
                redirect_url = session["redirect_url"]
                del session["redirect_url"]
                return redirect(redirect_url)
            else:
                return redirect("/")


@app.route(
    "/set_pack/<genotype_id>",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def set_pack(genotype_id):
    """
    let user set the pack of the individual
    """

    with fn.conn_alchemy().connect() as con:
        if request.method == "GET":
            result = (
                con.execute(
                    text("SELECT pack FROM genotypes WHERE genotype_id = :genotype_id"),
                    {"genotype_id": genotype_id},
                )
                .mappings()
                .fetchone()
            )

            if result is None:
                flash(fn.alert_danger(f"Genotype ID not found: {genotype_id}"))
                return redirect(request.referrer)

            pack = "" if result["pack"] is None else result["pack"]

            session["redirect_url"] = request.referrer

            return render_template(
                "set_pack.html",
                header_title=f"Set pack for {genotype_id}",
                genotype_id=genotype_id,
                current_pack=pack,
                back_url=session["redirect_url"],
            )

        if request.method == "POST":
            sql = text("UPDATE genotypes SET pack = :pack WHERE genotype_id = :genotype_id")
            con.execute(
                sql,
                {
                    "pack": request.form["pack"].lower().strip(),
                    "genotype_id": genotype_id,
                },
            )
            after_genotype_modif()

            if "redirect_url" in session:
                redirect_url = session["redirect_url"]
                del session["redirect_url"]
                return redirect(redirect_url)
            else:
                return redirect("/")


@app.route(
    "/set_sex/<genotype_id>",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def set_sex(genotype_id):
    """
    let user set the sex of the individual
    """

    with fn.conn_alchemy().connect() as con:
        if request.method == "GET":
            result = (
                con.execute(
                    text("SELECT sex FROM genotypes WHERE genotype_id = :genotype_id"),
                    {"genotype_id": genotype_id},
                )
                .mappings()
                .fetchone()
            )

            if result is None:
                flash(fn.alert_danger(f"Genotype ID not found: {genotype_id}"))
                return redirect(session["url_genotypes_list"])

            sex = "" if result["sex"] is None else result["sex"]

            session["redirect_url"] = request.referrer

            return render_template(
                "set_sex.html",
                header_title=f"Set sex for {genotype_id}",
                genotype_id=genotype_id,
                current_sex=sex,
                back_url=session["redirect_url"],
            )

        if request.method == "POST":
            if request.form["sex"].upper().strip() not in ("F", "M", ""):
                flash(fn.alert_danger(f"<big>Sex value <b>{request.form['sex'].upper().strip()}</b> not available.</big>"))

                if "redirect_url" in session:
                    redirect_url = session["redirect_url"]
                    del session["redirect_url"]
                    return redirect(redirect_url)
                else:
                    return redirect("/")

            sql = text("UPDATE genotypes SET sex = :sex WHERE genotype_id = :genotype_id")
            con.execute(
                sql,
                {
                    "sex": request.form["sex"].upper().strip(),
                    "genotype_id": genotype_id,
                },
            )
            after_genotype_modif()

            # update WA results
            sql = text("UPDATE wa_results SET sex_id = :sex WHERE genotype_id = :genotype_id")
            con.execute(
                sql,
                {
                    "sex": request.form["sex"].upper().strip(),
                    "genotype_id": genotype_id,
                },
            )
            after_wa_results_modif()

            if "redirect_url" in session:
                redirect_url = session["redirect_url"]
                del session["redirect_url"]
                return redirect(redirect_url)
            else:
                return redirect("/")


@app.route(
    "/set_status_1st_recap/<genotype_id>",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def set_status_1st_recap(genotype_id):
    """
    let user set the status_1st_recap of the individual
    """

    with fn.conn_alchemy().connect() as con:
        if request.method == "GET":
            result = (
                con.execute(
                    text("SELECT status_first_capture FROM genotypes WHERE genotype_id = :genotype_id"),
                    {"genotype_id": genotype_id},
                )
                .mappings()
                .fetchone()
            )

            if result is None:
                flash(fn.alert_danger(f"Genotype ID not found: {genotype_id}"))
                return redirect(request.referrer)

            status_first_capture = "" if result["status_first_capture"] is None else result["status_first_capture"]

            session["redirect_url"] = request.referrer

            return render_template(
                "set_status_1st_recap.html",
                header_title=f"Set status at 1st capture for {genotype_id}",
                genotype_id=genotype_id,
                current_status_first_capture=status_first_capture,
                return_url=request.referrer,
                back_url=session["redirect_url"],
            )

        if request.method == "POST":
            sql = text("UPDATE genotypes SET status_first_capture = :status_first_capture WHERE genotype_id = :genotype_id")
            con.execute(
                sql,
                {
                    "status_first_capture": request.form["status_first_capture"],
                    "genotype_id": genotype_id,
                },
            )
            after_genotype_modif()
            if "redirect_url" in session:
                redirect_url = session["redirect_url"]
                del session["redirect_url"]
                return redirect(redirect_url)
            else:
                return redirect("/")


@app.route(
    "/set_dispersal/<genotype_id>",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def set_dispersal(genotype_id):
    """
    let user set the dispersal of the individual
    """
    with fn.conn_alchemy().connect() as con:
        if request.method == "GET":
            result = (
                con.execute(
                    text("SELECT dispersal FROM genotypes WHERE genotype_id = :genotype_id"),
                    {"genotype_id": genotype_id},
                )
                .mappings()
                .fetchone()
            )

            if result is None:
                flash(fn.alert_danger(f"Genotype ID not found: {genotype_id}"))
                return redirect(request.referrer)

            session["redirect_url"] = request.referrer

            return render_template(
                "set_dispersal.html",
                header_title=f"Set dispersal for {genotype_id}",
                genotype_id=genotype_id,
                current_dispersal="" if result["dispersal"] is None else result["dispersal"],
                back_url=session["redirect_url"],
            )

        if request.method == "POST":
            sql = text("UPDATE genotypes SET dispersal = :dispersal WHERE genotype_id = :genotype_id")
            con.execute(
                sql,
                {
                    "dispersal": request.form["dispersal"].strip(),
                    "genotype_id": genotype_id,
                },
            )
            after_genotype_modif()
            if "redirect_url" in session:
                redirect_url = session["redirect_url"]
                del session["redirect_url"]
                return redirect(redirect_url)
            else:
                return redirect("/")


@app.route(
    "/set_parent/<genotype_id>/<parent_type>",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def set_parent(genotype_id, parent_type):
    """
    let user set the parent (father or mother) of the individual
    """

    with fn.conn_alchemy().connect() as con:
        if request.method == "GET":
            if parent_type not in ("father", "mother"):
                flash(fn.alert_danger(f"Error in {parent_type} parameter (must be 'father' or 'mother')"))
                return redirect(request.referrer)

            result = (
                con.execute(
                    text("SELECT mother, father FROM genotypes WHERE genotype_id = :genotype_id"),
                    {"genotype_id": genotype_id},
                )
                .mappings()
                .fetchone()
            )

            if result is None:
                flash(fn.alert_danger(f"Genotype ID not found: {genotype_id}"))
                return redirect(request.referrer)

            session["redirect_url"] = request.referrer

            return render_template(
                "set_parent.html",
                header_title=f"Set {parent_type} of {genotype_id}",
                genotype_id=genotype_id,
                parent=parent_type,
                current_parent="" if result[parent_type] is None else result[parent_type],
                back_url=session["redirect_url"],
            )

        if request.method == "POST":
            if parent_type not in ("father", "mother"):
                flash(fn.alert_danger(f"Error in {parent_type} parameter (must be 'father' or 'mother')"))
                if "redirect_url" in session:
                    redirect_url = session["redirect_url"]
                    del session["redirect_url"]
                    return redirect(redirect_url)
                else:
                    return redirect("/")

            # check if parent identical to genotype
            if genotype_id.strip() == request.form["parent"].strip():
                flash(fn.alert_danger(f"The parent genotype <b>{request.form['parent'].strip()}</b> cannot be the same genotype"))
                if "redirect_url" in session:
                    redirect_url = session["redirect_url"]
                    del session["redirect_url"]
                    return redirect(redirect_url)
                else:
                    return redirect("/")

            # check if parent genotype is present in genotypes table
            if request.form["parent"].strip():
                sql = text("SELECT genotype_id FROM genotypes WHERE genotype_id = :genotype_id")
                if con.execute(sql, {"genotype_id": request.form["parent"].strip()}).mappings().fetchone() is None:
                    flash(fn.alert_danger(f"The genotype <b>{request.form['parent'].strip()}</b> is not present in the genotypes table."))
                    if "redirect_url" in session:
                        redirect_url = session["redirect_url"]
                        del session["redirect_url"]
                        return redirect(redirect_url)
                    else:
                        return redirect("/")

            sql = text(f"UPDATE genotypes SET {parent_type} = :parent WHERE genotype_id = :genotype_id")
            con.execute(
                sql,
                {
                    "parent": request.form["parent"].strip(),
                    "genotype_id": genotype_id.strip(),
                },
            )
            after_genotype_modif()

            flash(
                fn.alert_success(
                    f"The <b>{parent_type}</b> of the genotype <b>{genotype_id}</b> was changed to <b>{request.form['parent'].strip()}</b>."
                )
            )

            if "redirect_url" in session:
                redirect_url = session["redirect_url"]
                del session["redirect_url"]
                return redirect(redirect_url)
            else:
                return redirect("/")


@app.route(
    "/set_hybrid/<genotype_id>",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def set_hybrid(genotype_id):
    """
    let user set the hybrid state of the individual
    """

    with fn.conn_alchemy().connect() as con:
        if request.method == "GET":
            result = (
                con.execute(
                    text("SELECT hybrid FROM genotypes WHERE genotype_id = :genotype_id"),
                    {"genotype_id": genotype_id},
                )
                .mappings()
                .fetchone()
            )

            if result is None:
                flash(fn.alert_danger(f"Genotype ID not found: {genotype_id}"))
                return redirect(request.referrer)

            hybrid = "" if result["hybrid"] is None else result["hybrid"]

            session["redirect_url"] = request.referrer

            return render_template(
                "set_hybrid.html",
                header_title=f"Set hybrid state for {genotype_id}",
                genotype_id=genotype_id,
                current_hybrid=hybrid,
                back_url=session["redirect_url"],
            )

        if request.method == "POST":
            sql = text("UPDATE genotypes SET hybrid = :hybrid WHERE genotype_id = :genotype_id")
            con.execute(
                sql,
                {"hybrid": request.form["hybrid"].strip(), "genotype_id": genotype_id},
            )
            after_genotype_modif()
            if "redirect_url" in session:
                redirect_url = session["redirect_url"]
                del session["redirect_url"]
                return redirect(redirect_url)
            else:
                return redirect("/")


@app.route(
    "/load_definitive_genotypes_xlsx",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def load_definitive_genotypes_xlsx():
    """
    allow user to load definitive genotypes from XLSX/ODS file
    parse XLSX/ODS file and load the confirm page
    """

    if request.method == "GET":
        return render_template(
            "load_definitive_genotypes_xlsx.html",
            header_title="Load genetic data for genotypes from XLSX/ODS file",
        )

    if request.method == "POST":
        new_file = request.files["new_file"]

        # check file extension
        if pl.Path(new_file.filename).suffix.upper() not in params["excel_allowed_extensions"]:
            flash(fn.alert_danger("The uploaded file does not have an allowed extension (must be <b>.xlsx</b> or <b>.ods</b>)"))
            return redirect("/load_definitive_genotypes_xlsx")

        try:
            filename = str(uuid.uuid4()) + str(pl.Path(new_file.filename).suffix.upper())
            new_file.save(pl.Path(params["upload_folder"]) / pl.Path(filename))
        except Exception:
            flash(fn.alert_danger("Error with the uploaded file"))
            return redirect("/load_definitive_genotypes_xlsx")

        # loci list
        loci_list = fn.get_loci_list()

        r, msg, data = import_.extract_genotypes_data_from_xlsx(filename, loci_list)

        if r:
            flash(msg)
            return redirect("/load_definitive_genotypes_xlsx")

        with fn.conn_alchemy().connect() as con:
            # check if genotype_id already in DB
            genotypes_list = "','".join([data[idx]["genotype_id"] for idx in data])
            sql = text(f"SELECT genotype_id FROM genotypes WHERE genotype_id IN ('{genotypes_list}')")
            genotypes_to_update = [row["genotype_id"] for row in con.execute(sql).mappings().all()]

            return render_template(
                "confirm_load_definitive_genotypes_xlsx.html",
                genotypes_to_update=genotypes_to_update,
                loci_list=loci_list,
                data=data,
                filename=filename,
            )


@app.route(
    "/confirm_load_definitive_genotypes_xlsx/<filename>",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def confirm_load_definitive_genotypes_xlsx(filename):
    """
    Load new definitive genotypes from XLSX file
    """
    from threading import Thread

    thread = Thread(target=import_.import_definitive_genotypes, args=(filename,))
    thread.start()

    flash(fn.alert_success("The genotypes are being updated.<br>It will take several minutes to complete."))

    return redirect("/")


@app.route("/select_on_map/<samples>", methods=["GET", "POST"])
@fn.check_login
def select_on_map(samples: str):
    """
    allow user to select scats and dead wolves by drawing a polygon
    """

    def close_polygon(geojson_polygon):
        """
        close polygon
        """
        coordinates = geojson_polygon["coordinates"][0]

        # check if first and last point are identical
        if coordinates[0] != coordinates[-1]:
            coordinates.append(coordinates[0])  # Add first point at the end

        return geojson_polygon

    if request.method == "GET":
        return plot_all_wa(add_polygon=True, samples=samples)

    if request.method == "POST":
        # Retrieve coordinates
        data = request.get_json()

        if "coordinates" in data:
            # print(Polygon([data["coordinates"]]))

            with fn.conn_alchemy().connect() as con:
                result = (
                    con.execute(
                        text(
                            "SELECT count(wa_code) AS wa_codes_number FROM wa_scat_dw_mat WHERE "
                            "ST_Within(geometry_utm, st_transform(ST_GeomFromGeoJSON(:geojson_polygon), 32632))"
                        ),
                        {"geojson_polygon": str(Polygon([data["coordinates"]]))},
                    )
                    .mappings()
                    .fetchone()
                )

            if result["wa_codes_number"] == 0:
                return jsonify(
                    {
                        "status": "error",
                        "message": "No WA codes were found in the polygon",
                    }
                ), 400

            # convert polygon in WKT
            with fn.conn_alchemy().connect() as con:
                wkt_polygon = (
                    con.execute(
                        text("SELECT ST_AsText(ST_GeomFromGeoJSON(:geojson_polygon))"),
                        {"geojson_polygon": str(close_polygon(Polygon([data["coordinates"]])))},
                    )
                    .mappings()
                    .fetchone()
                )

            if wkt_polygon:
                return jsonify({"status": "success", "message": wkt_polygon["st_astext"]}), 200
            else:
                return jsonify({"status": "error", "message": "Error in polygon"}), 400

        else:
            return jsonify({"status": "error", "message": "no coordinates"}), 400
