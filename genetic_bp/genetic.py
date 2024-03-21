"""
WolfDB web service
(c) Olivier Friard

flask blueprint for genetic data management
"""

import flask
from flask import render_template, redirect, request, flash, session, make_response, url_for
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
import pandas as pd
import datetime as dt
import time

import functions as fn
from . import export

app = flask.Blueprint("genetic", __name__, template_folder="templates")

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


@app.route("/del_genotype/<genotype_id>")
@fn.check_login
def del_genotype(genotype_id):
    """
    set genotype as deleted (record_status field)
    """
    with fn.conn_alchemy().connect() as con:
        con.execute(text("UPDATE genotypes SET record_status = 'deleted' WHERE genotype_id = :genotype_id"), {"genotype_id": genotype_id})
        con.execute(text("UPDATE wa_results SET genotype_id = NULL WHERE genotype_id = :genotype_id"), {"genotype_id": genotype_id})

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
        con.execute(text("UPDATE genotypes SET record_status = 'temp' WHERE genotype_id = :genotype_id"), {"genotype_id": genotype_id})
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
        con.execute(text("UPDATE genotypes SET record_status = 'OK' WHERE genotype_id = :genotype_id"), {"genotype_id": genotype_id})
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
        con.execute(text("UPDATE genotypes SET record_status = 'temp' WHERE genotype_id = :genotype_id"), {"genotype_id": genotype_id})
        after_genotype_modif()

    flash(fn.alert_success(f"<b>Genotype {genotype_id} set as temporary</b>"))

    return redirect(f"{request.referrer}#{genotype_id}")


@app.route("/view_genotype/<genotype_id>")
@fn.check_login
def view_genotype(genotype_id: str):
    """
    visualize genotype's data
    """
    con = fn.conn_alchemy().connect()

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
        if "url_genotypes_list" in session:
            return redirect(session["url_genotypes_list"])
        if "url_wa_list" in session:
            return redirect(session["url_wa_list"])
        return "Error on genotype"

    genotype_loci = json.loads(rdis.get(genotype_id))

    # samples
    wa_codes = (
        con.execute(
            text(
                "SELECT wa_code, sample_id, sample_type, "
                "ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS sample_lonlat "
                "FROM wa_scat "
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
    count_wa_code, sum_lon, sum_lat = 0, 0, 0
    for row in wa_codes:
        sample_geojson = json.loads(row["sample_lonlat"])
        count_wa_code += 1
        lon, lat = sample_geojson["coordinates"]
        sum_lon += lon
        sum_lat += lat

        if row["sample_type"] == "scat":
            color = params["scat_color"]
        elif row["sample_type"] == "tissue":
            color = params["dead_wolf_color"]
        else:
            color = "red"

        sample_feature = {
            "geometry": dict(sample_geojson),
            "type": "Feature",
            "properties": {
                "style": {"color": color, "fillColor": color, "fillOpacity": 1},
                "popupContent": (
                    f"""Scat ID: <a href="/view_scat/{row['sample_id']}" target="_blank">{row['sample_id']}</a><br>"""
                    f"""WA code: <a href="/view_wa/{row['wa_code']}" target="_blank">{row['wa_code']}</a><br>"""
                    # f"""Genotype ID: {row['genotype_id']}"""
                ),
            },
            "id": row["sample_id"],
        }
        samples_features.append(sample_feature)

        loci_val = get_wa_loci_values_redis(row["wa_code"])
        if loci_val is not None:
            loci_values[row["wa_code"]] = loci_val
        else:
            loci_values[row["wa_code"]] = fn.get_wa_loci_values(row["wa_code"], loci_list)

    if count_wa_code:
        center = f"{sum_lat / count_wa_code}, {sum_lon / count_wa_code}"
        map = Markup(
            fn.leaflet_geojson2(
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


'''
@app.route("/view_genotype/<genotype_id>")
@fn.check_login
def view_genotype(genotype_id):
    """
    visualize genotype's data
    """
    con = fn.conn_alchemy().connect()

    genotype = (
        con.execute(
            text(
                "SELECT *, "
                "(SELECT 'Yes' FROM wa_scat_dw_mat "
                "       WHERE (sample_id LIKE 'T%' OR sample_id like 'M%') "
                "             AND genotype_id=genotypes.genotype_id LIMIT 1) AS dead_recovery "
                "FROM genotypes WHERE genotype_id = :genotype_id"
            ),
            {"genotype_id": genotype_id},
        )
        .mappings()
        .fetchone()
    )

    if genotype is None:
        flash(fn.alert_danger(f"The genotype <b>{genotype_id}</b> was not found in Genotypes table"))
        return redirect("/dead_wolves_list")

    # sample
    wa_codes = (
        con.execute(
            text(
                "SELECT wa_code, sample_id, "
                "ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS sample_lonlat "
                "FROM wa_scat_dw_mat "
                "WHERE genotype_id = :genotype_id "
                "ORDER BY wa_code"
            ),
            {"genotype_id": genotype_id},
        )
        .mappings()
        .all()
    )

    samples_features: list = []
    count, sum_lon, sum_lat = 0, 0, 0
    for row in wa_codes:
        sample_geojson = json.loads(row["sample_lonlat"])
        count += 1
        lon, lat = sample_geojson["coordinates"]
        sum_lon += lon
        sum_lat += lat

        if row["sample_id"].startswith("E"):
            color = params["scat_color"]
        elif row["sample_id"].startswith("T") or row["sample_id"].startswith("M"):
            color = params["dead_wolf_color"]
        else:
            color = "red"

        sample_feature = {
            "geometry": dict(sample_geojson),
            "type": "Feature",
            "properties": {
                "style": {"color": color, "fillColor": color, "fillOpacity": 1},
                "popupContent": (
                    f"""Scat ID: <a href="/view_scat/{row['sample_id']}" target="_blank">{row['sample_id']}</a><br>"""
                    f"""WA code: <a href="/view_wa/{row['wa_code']}" target="_blank">{row['wa_code']}</a><br>"""
                    # f"""Genotype ID: {row['genotype_id']}"""
                ),
            },
            "id": row["sample_id"],
        }

        samples_features.append(sample_feature)

    if count:
        center = f"{sum_lat / count}, {sum_lon / count}"
        map = Markup(
            fn.leaflet_geojson2(
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
        "view_genotype.html",
        header_title=f"Genotype ID: {genotype_id}",
        result=genotype,
        n_recap=len(wa_codes),
        wa_codes=wa_codes,
        map=map,
        scat_color=params["scat_color"],
        dead_wolf_color=params["dead_wolf_color"],
        transect_color=params["transect_color"],
        track_color=params["track_color"],
    )
'''


@app.route("/genotypes")
@fn.check_login
def genotypes():
    return render_template("genotypes.html", header_title="Genotypes")


def update_redis_with_genotypes_loci():
    """
    update redis with the genotypes loci values

    !require the update_redis_with_genotypes_loci_values file
    """

    _ = subprocess.Popen(["python3", "update_redis_with_genotypes_loci_values.py"])


@app.route("/update_redis_genotypes")
@fn.check_login
def web_update_redis_with_genotypes_loci():
    """
    web interface to update redis with the genotypes loci values

    !require the update_redis_with_genotypes_loci_values file
    """
    update_redis_with_genotypes_loci()

    flash(fn.alert_danger("Redis updating with genotypes loci in progress"))

    return redirect("/admin")


@app.route("/update_redis_wa")
@fn.check_login
def update_redis_with_wa_loci():
    """
    update redis with the WA loci values

    !require the update_redis_with_wa_loci_values.py file
    """
    _ = subprocess.Popen(["python3", "update_redis_with_wa_loci_values.py"])

    flash(fn.alert_danger("Redis updating with WA loci in progress"))

    return redirect("/admin")


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

    # check type of genotype
    match type:
        case "all":
            filter = "WHERE record_status != 'deleted'"
            header_title = "List of all genotypes"

        case "definitive":
            filter = "WHERE record_status = 'OK'"
            header_title = "List of definitive genotypes"

        case "temp":
            filter = "WHERE record_status = 'temp'"
            header_title = "List of temporary genotypes"

        case "deleted":
            filter = "WHERE record_status = 'deleted'"
            header_title = "List of temporary genotypes"
        case _:
            return f"{type} not found"

    # test limit value: must be ALL or int
    if limit != "ALL":
        try:
            limit = int(limit)
        except Exception:
            return "An error has occured. Check the URL"

    if limit == "ALL":
        offset = 0

    con = fn.conn_alchemy().connect()

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
        field, value = [x.strip().lower() for x in search_term.split(":")]
        if field == "genotype":
            field = "genotype id"
        if field not in ("genotype id", "notes", "tmp id", "date", "pack", "sex", "status", "working notes"):
            flash(
                fn.alert_danger(
                    "<b>Search term not found</b>. Must be 'genotype id', 'notes', 'tmp id', 'date', 'pack', 'sex', 'status' or 'working notes'"
                )
            )
            return redirect(session["url_genotypes_list"])

        field = field.replace(" ", "_")
        sql_search = "SELECT *, count(*) OVER() AS n_genotypes FROM genotypes_list_mat " + (f"WHERE {field} ILIKE :search")
    else:
        value = search_term

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
            {
                "search": f"%{value}%",
                "start_date": session["start_date"],
                "end_date": session["end_date"],
            },
        )
        .mappings()
        .all()
    )

    # loci list
    loci_list: dict = fn.get_loci_list()

    loci_values: dict = {}
    for row in results:
        loci_val = rdis.get(row["genotype_id"])
        if loci_val is not None:
            loci_values[row["genotype_id"]] = json.loads(loci_val)
        else:
            loci_values[row["genotype_id"]] = fn.get_genotype_loci_values(row["genotype_id"], loci_list)

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

        return render_template(
            "genotypes_list.html",
            header_title=header_title,
            title=f"List of {results[0]['n_genotypes'] if results else 0} {type} genotypes".replace(" all", "").replace("_short", ""),
            limit=limit,
            offset=offset,
            type=type,
            n_genotypes=results[0]["n_genotypes"] if results else 0,
            results=results,
            loci_list=loci_list,
            loci_values=loci_values,
            short="",
            search_term=search_term,
        )


@app.route("/view_wa/<wa_code>")
@fn.check_login
def view_wa(wa_code):
    con = fn.conn_alchemy().connect()

    result = (
        con.execute(
            text(
                "SELECT *, ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat,"
                "ROUND(st_x(st_transform(geometry_utm, 4326))::numeric, 6) as longitude, "
                "ROUND(st_y(st_transform(geometry_utm, 4326))::numeric, 6) as latitude "
                " FROM wa_scat_dw_mat WHERE wa_code = :wa_code"
            ),
            {"wa_code": wa_code},
        )
        .mappings()
        .fetchone()
    )

    if result is not None:
        if result["sample_id"].startswith("T") or result["sample_id"].startswith("M"):
            return redirect(f"/view_tissue/{result['sample_id']}")
        else:  # E or other
            return redirect(f"/view_scat/{result['sample_id']}")

    else:
        result = (
            con.execute(
                text(
                    "SELECT *, ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat,"
                    "ROUND(st_x(st_transform(geometry_utm, 4326))::numeric, 6) as longitude, "
                    "ROUND(st_y(st_transform(geometry_utm, 4326))::numeric, 6) as latitude "
                    "FROM dead_wolves_mat "
                    "WHERE wa_code = :wa_code"
                ),
                {"wa_code": wa_code},
            )
            .mappings()
            .fetchone()
        )

        if result is not None:
            return redirect(f"/view_tissue/{result['tissue_id']}")

        else:
            flash(fn.alert_danger(f"WA code not found: {wa_code}"))
            return redirect(request.referrer)


@app.route("/plot_all_wa")
@fn.check_login
def plot_all_wa():
    """
    plot all WA codes (scats and dead wolves)
    """
    con = fn.conn_alchemy().connect()

    scat_features: list = []

    tot_min_lat, tot_min_lon = 90, 90
    tot_max_lat, tot_max_lon = -90, -90

    for row in (
        con.execute(
            text(
                "SELECT wa_code, sample_id, genotype_id, "
                "ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat "
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
        scat_geojson = json.loads(row["scat_lonlat"])

        lon, lat = scat_geojson["coordinates"]

        tot_min_lat = min([tot_min_lat, lat])
        tot_max_lat = max([tot_max_lat, lat])
        tot_min_lon = min([tot_min_lon, lon])
        tot_max_lon = max([tot_max_lon, lon])

        if row["sample_id"].startswith("E"):
            color = params["scat_color"]
        elif row["sample_id"][0] in "TM":
            color = params["dead_wolf_color"]
        else:
            color = "red"

        scat_feature = {
            "geometry": dict(scat_geojson),
            "type": "Feature",
            "properties": {
                "style": {"color": color, "fillColor": color, "fillOpacity": 1},
                "popupContent": (
                    f"""Scat ID: <a href="/view_scat/{row['sample_id']}" target="_blank">{row['sample_id']}</a><br>"""
                    f"""WA code: <a href="/view_wa/{row['wa_code']}" target="_blank">{row['wa_code']}</a><br>"""
                    f"""Genotype ID: {row['genotype_id']}"""
                ),
            },
            "id": row["sample_id"],
        }

        scat_features.append(scat_feature)

    return render_template(
        "plot_all_wa.html",
        header_title="Locations of WA codes",
        title=Markup(f"<h3>Locations of {len(scat_features)} samples WA codes.</h3>"),
        map=Markup(
            fn.leaflet_geojson2(
                {
                    "scats": scat_features,
                    "scats_color": params["scat_color"],
                    "fit": [[tot_min_lat, tot_min_lon], [tot_max_lat, tot_max_lon]],
                }
            )
        ),
        distance=0,
        scat_color=params["scat_color"],
        dead_wolf_color=params["dead_wolf_color"],
        transect_color=params["transect_color"],
        track_color=params["track_color"],
    )


@app.route("/plot_wa_clusters/<int:distance>")
@fn.check_login
def plot_wa_clusters(distance: int):
    with fn.conn_alchemy().connect() as con:
        results = (
            con.execute(
                text(
                    "SELECT wa_code, sample_id, genotype_id, "
                    "ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat, "
                    f"ST_ClusterDBSCAN(geometry_utm, eps:={distance}, minpoints:=1) over() AS cid "
                    "FROM wa_scat_dw_mat "
                    "WHERE mtdna != 'Poor DNA' "
                    "AND date BETWEEN :start_date AND :end_date"
                ),
                {
                    "start_date": session["start_date"],
                    "end_date": session["end_date"],
                },
            )
            .mappings()
            .all()
        )

    # max cluster id
    max_cluster_id = max([row["cid"] for row in results])
    cmap = get_cmap(max_cluster_id)

    scat_features: list = []
    min_lon, min_lat, max_lon, max_lat = 90, 90, -90, -90
    for row in results:
        # skip loci with value  0 or -
        loci_val = rdis.get(row["wa_code"])
        if loci_val is not None:
            flag_ok = False
            d = json.loads(loci_val)
            for locus in d:
                for allele in d[locus]:
                    if d[locus][allele]["value"] not in ("-", 0):
                        flag_ok = True
                        break
                if flag_ok:
                    break
            else:  # not broken
                continue

        scat_geojson = json.loads(row["scat_lonlat"])
        lon, lat = scat_geojson["coordinates"]
        min_lon = min(min_lon, lon)
        min_lat = min(min_lat, lat)
        max_lon = max(max_lon, lon)
        max_lat = max(max_lat, lat)

        color = matplotlib.colors.to_hex(cmap(row["cid"]), keep_alpha=False)
        scat_feature = {
            "geometry": dict(scat_geojson),
            "type": "Feature",
            "properties": {
                "style": {"color": color, "fillColor": color, "fillOpacity": 1},
                "popupContent": (
                    f"""Sample ID: <a href="/view_scat/{row['sample_id']}" target="_blank">{row['sample_id']}</a><br>"""
                    f"""WA code: <a href="/view_wa/{row['wa_code']}" target="_blank">{row['wa_code']}</a><br>"""
                    f"""Genotype ID: {row['genotype_id']}<br>"""
                    f"""Cluster ID {row['cid']}:  <a href="/wa_analysis/{distance}/{row['cid']}">samples</a><br>"""
                    f"""<a href="/wa_analysis_group/web/{distance}/{row['cid']}">genotypes</a>"""
                ),
            },
            "id": row["sample_id"],
        }

        scat_features.append(scat_feature)

    return render_template(
        "plot_clusters.html",
        header_title=f"WA codes clusters ({distance} m)",
        title=Markup(f"<h3>Plot of {len(scat_features)} WA codes clusters</h3>DBSCAN: {distance} m"),
        map=Markup(
            fn.leaflet_geojson2(
                {
                    "scats": scat_features,
                    "scats_color": params["scat_color"],
                    "fit": [[min_lat, min_lon], [max_lat, max_lon]],
                }
            )
        ),
        distance=int(distance),
    )


def get_wa_loci_values_redis(wa_code: str) -> dict | None:
    r = rdis.get(wa_code)
    if r is None:
        return None
    return json.loads(r)


def get_genotype_loci_values_redis(genotype_id: str) -> dict | None:
    r = rdis.get(genotype_id)
    if r is None:
        return None
    return json.loads(r)


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

    con = fn.conn_alchemy().connect()

    sql_all = "SELECT * FROM wa_genetic_samples_mat "

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

    if ":" in search_term:
        field, value = [x.strip().lower() for x in search_term.split(":")]
        if field == "wa":
            field = "wa code"
        if field not in ("wa code", "date", "sample id", "municipality", "genotype id", "sex", "tmp id", "notes", "pack"):
            flash(
                fn.alert_danger(
                    "Search term not found. Must be 'wa code', 'date', 'sample id', 'municipality', 'genotype id', 'sex', 'tmp id', 'notes' or 'pack'"
                )
            )
            return redirect(session["url_wa_list"])

        field = field.replace(" ", "_")
        if field == "sex":
            field = "sex_id"

        sql_search = sql_all + (f"WHERE {field} ILIKE :search")
    else:
        value = search_term
        sql_search = sql_all + (
            "WHERE ("
            "wa_code ILIKE :search "
            "OR sample_id ILIKE :search "
            "OR date::text ILIKE :search "
            "OR municipality ILIKE :search "
            "OR genotype_id ILIKE :search "
            "OR tmp_id ILIKE :search "
            "OR notes ILIKE :search "
            "OR pack ILIKE :search "
            ") "
        )

    wa_scats = (
        con.execute(
            text(sql_all if not search_term else sql_search),
            {
                "search": f"%{value}%",
                "start_date": session["start_date"],
                "end_date": session["end_date"],
            },
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

        # get loci values from redis cache
        # loci_val = rdis.get(row["wa_code"])
        loci_val = get_wa_loci_values_redis(row["wa_code"])

        has_loci_notes = False
        has_orange_loci_notes = False
        has_loci_values = False

        if loci_val is None:
            loci_values[row["wa_code"]], has_loci_notes = fn.get_wa_loci_values(row["wa_code"], loci_list)
        else:
            loci_values[row["wa_code"]] = dict(loci_val)

        # check if loci have notes and values and corresponds to genotype loci
        for x in loci_values[row["wa_code"]]:
            for allele in ("a", "b"):
                loci_values[row["wa_code"]][x][allele]["divergent_allele"] = ""

                if loci_values[row["wa_code"]][x][allele]["notes"] and not loci_values[row["wa_code"]][x][allele]["user_id"].startswith(
                    "OK|"
                ):
                    has_loci_notes = True
                    loci_values[row["wa_code"]][x][allele]["color"] = params["red_note"]
                elif loci_values[row["wa_code"]][x][allele]["user_id"].startswith("OK|"):
                    loci_values[row["wa_code"]][x][allele]["color"] = params["green_note"]
                else:
                    loci_values[row["wa_code"]][x][allele]["color"] = "#ffffff00"

                if loci_values[row["wa_code"]][x][allele]["value"] not in (0, "-"):
                    has_loci_values = True

                # check if wa loci corresponds to genotype loci (if not the background colo will be orange)
                if row["genotype_id"]:
                    genotype_loci_val = {}
                    if mem_genotype_loci.get(row["genotype_id"], False):
                        genotype_loci_val = mem_genotype_loci[row["genotype_id"]]
                    else:
                        genotype_loci_val = get_genotype_loci_values_redis(row["genotype_id"])
                        if genotype_loci_val is not None:
                            mem_genotype_loci[row["genotype_id"]] = genotype_loci_val
                        else:
                            print(f'Loci not found {row["genotype_id"]=}  {row["wa_code"]=}')

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
                        """
                        print(f'{row["genotype_id"]=}')
                        print(f"{x=}")
                        print(f"{allele=}")
                        print(f"{genotype_loci_val[x][allele]=}")
                        print()
                        print(f"{loci_val[x][allele]=}")
                        """

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
        )


@app.route(
    "/search_wa",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def search_wa():
    if request.method == "GET":
        with fn.conn_alchemy().connect() as con:
            sql = text("SELECT * FROM wa_genetic_samples_mat ")
            results = con.execute(sql).mappings().all()
            return render_template(
                "wa_genetic_samples_list.html",
                header_title="Search WA codes",
                title="TITOLO",
                wa_scats=results,
                with_notes="",
            )


@app.route("/wa_analysis/<distance>/<int:cluster_id>")
@app.route("/wa_analysis/<distance>/<int:cluster_id>/<mode>")
@fn.check_login
def wa_analysis(distance: int, cluster_id: int, mode: str = "web"):
    con = fn.conn_alchemy().connect()

    # loci list
    loci_list: list = fn.get_loci_list()

    # DBScan
    wa_list: list = []
    for row in (
        con.execute(
            text(
                "SELECT wa_code, sample_id, municipality, "
                "ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat, "
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
    wa_list_str = "','".join(wa_list)

    wa_scats = (
        con.execute(
            text(
                "SELECT wa_code, sample_id, date, municipality, coord_east, coord_north, "
                "mtdna, genotype_id, tmp_id, sex_id, "
                "(SELECT working_notes FROM genotypes WHERE genotype_id=wa_scat_dw_mat.genotype_id) AS notes, "
                "(SELECT status FROM genotypes WHERE genotype_id=wa_scat_dw_mat.genotype_id) AS status, "
                "(SELECT pack FROM genotypes WHERE genotype_id=wa_scat_dw_mat.genotype_id) AS pack, "
                "(SELECT 'Yes' FROM dead_wolves_mat WHERE tissue_id = sample_id LIMIT 1) as dead_recovery "
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
    out: list = []
    for row in wa_scats:
        loci_values[row["wa_code"]], _ = fn.get_wa_loci_values(row["wa_code"], loci_list)
        has_loci_values = False
        # check if loci have values
        for x in loci_values[row["wa_code"]]:
            for allele in ["a", "b"]:
                if loci_values[row["wa_code"]][x][allele]["value"] not in (0, "-"):
                    has_loci_values = True
            if has_loci_values:
                break

        if has_loci_values:
            out.append(row)

    if mode == "export":
        file_content = export.export_wa_analysis(loci_list, out, loci_values, distance, cluster_id)

        response = make_response(file_content, 200)
        response.headers["Content-type"] = "application/application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        response.headers["Content-disposition"] = f"attachment; filename=wa_analysis_{dt.datetime.now():%Y-%m-%d_%H%M%S}.xlsx"

        return response

    else:
        session["go_back_url"] = f"/wa_analysis/{distance}/{cluster_id}"

        return render_template(
            "wa_analysis.html",
            header_title=f"WA matches (cluster ID: {cluster_id} _ {distance} m))",
            title=Markup(f"Matches (cluster id: {cluster_id} _ {distance} m)"),
            loci_list=loci_list,
            wa_scats=out,
            loci_values=loci_values,
            distance=distance,
            cluster_id=cluster_id,
        )


@app.route("/wa_analysis_group/<mode>/<distance>/<cluster_id>")
@fn.check_login
def wa_analysis_group(mode: str, distance: int, cluster_id: int):
    con = fn.conn_alchemy().connect()

    # loci list
    loci_list: dict = fn.get_loci_list()

    # DBScan
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
        if row["cluster_id"] == int(cluster_id):
            wa_list.append(row["wa_code"])
    wa_list_str = "','".join(wa_list)

    # fetch grouped genotypes
    genotype_id = (
        con.execute(
            text(
                "SELECT genotype_id, count(wa_code) AS n_recap "
                "FROM wa_scat_dw_mat "
                f"WHERE wa_code in ('{wa_list_str}') "
                "GROUP BY genotype_id "
                "ORDER BY genotype_id ASC"
            )
        )
        .mappings()
        .all()
    )

    loci_values: dict = {}
    data: dict = {}
    for row in genotype_id:
        if row["genotype_id"] is None:
            continue

        result = (
            con.execute(
                text(
                    "SELECT *, "
                    "(SELECT 'Yes' FROM wa_scat_dw_mat WHERE (sample_id like 'T%' OR sample_id like 'M%')AND genotype_id=genotypes.genotype_id LIMIT 1) AS dead_recovery "
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

        loci_val = rdis.get(row["genotype_id"])
        if loci_val is not None:
            loci_values[row["genotype_id"]] = json.loads(loci_val)
        else:
            loci_values[row["genotype_id"]] = fn.get_genotype_loci_values(row["genotype_id"], loci_list)

    if mode == "export":
        file_content = export.export_wa_analysis_group(loci_list, data, loci_values)
        response = make_response(file_content, 200)
        response.headers["Content-type"] = "application/application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        response.headers["Content-disposition"] = f"attachment; filename=genotypes_matches_{dt.datetime.now():%Y-%m-%d_%H%M%S}.xlsx"
        return response

    else:
        return render_template(
            "wa_analysis_group.html",
            header_title=f"Genotypes matches (cluster ID: {cluster_id} _ {distance} m))",
            title=Markup(f"Genotypes matches (cluster id: {cluster_id} _ {distance} m)"),
            loci_list=loci_list,
            genotype_id=genotype_id,
            data=data,
            loci_values=loci_values,
            distance=distance,
            cluster_id=cluster_id,
        )


@app.route("/view_genetic_data/<wa_code>")
@fn.check_login
def view_genetic_data(wa_code: str):
    """
    visualize genetic data for WA code
    """
    with fn.conn_alchemy().connect() as con:
        # get info about WA code
        row = (
            con.execute(text("SELECT sex_id, genotype_id FROM wa_results WHERE wa_code = :wa_code"), {"wa_code": wa_code})
            .mappings()
            .fetchone()
        )
        sex = row["sex_id"]
        genotype_id = row["genotype_id"]

        # loci list
        loci_list = fn.get_loci_list()

        wa_loci, _ = fn.get_wa_loci_values(wa_code, loci_list)

        genotype_loci = fn.get_genotype_loci_values(row["genotype_id"], loci_list)

        for locus in loci_list:
            for allele in ("a", "b"):
                if genotype_loci and genotype_loci[locus][allele]["value"] != wa_loci[locus][allele]["value"]:
                    wa_loci[locus][allele]["divergent_allele"] = Markup(
                        f"""<button type="button" class="btn btn-warning btn-sm">{genotype_loci[locus][allele]['value']}</button>"""
                    )

        return render_template(
            "view_genetic_data.html",
            header_title=f"{wa_code} genetic data",
            wa_code=wa_code,
            loci_list=loci_list,
            sex=sex,
            genotype_id=genotype_id,
            data=wa_loci,
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
    con = fn.conn_alchemy().connect()

    # get info about WA code
    row = (
        con.execute(text("SELECT sex_id, genotype_id FROM wa_results WHERE wa_code = :wa_code"), {"wa_code": wa_code}).mappings().fetchone()
    )

    loci = con.execute(text("SELECT * FROM loci ORDER BY position ASC")).mappings().all()

    # loci list
    loci_list = fn.get_loci_list()

    loci_val = get_wa_loci_values_redis(wa_code)
    if loci_val is None:
        loci_val, _ = fn.get_wa_loci_values(wa_code, loci_list)

    if request.method == "GET":
        return render_template(
            "add_genetic_data.html",
            header_title=f"Add genetic data for {wa_code}",
            go_back_url=request.referrer,
            wa_code=wa_code,
            loci=loci,
            loci_values=loci_val,
            sex=row["sex_id"],
            genotype_id=row["genotype_id"],
        )

    if request.method == "POST":
        # set sex
        con.execute(
            text("UPDATE wa_results SET sex_id = :sex_id WHERE wa_code = :wa_code"), {"sex_id": request.form["sex"], "wa_code": wa_code}
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
                text("UPDATE genotypes SET sex = :sex WHERE genotype_id = (SELECT genotype_id FROM wa_results WHERE wa_code = :wa_code)"),
                {"sex": rows[0]["sex_id"], "wa_code": wa_code},
            )
            after_genotype_modif()

        # 'OK|' is inserted before the user_id field to demonstrate that allele value has changed (or not) -> green
        current_epoch = int(time.time())
        for locus in loci:
            for allele in ("a", "b"):
                if locus["name"] + f"_{allele}" in request.form and request.form[locus["name"] + f"_{allele}"]:
                    con.execute(
                        text(
                            "INSERT INTO wa_locus "
                            "(wa_code, locus, allele, val, timestamp, user_id) "
                            "VALUES (:wa_code, :locus, :allele, :val, to_timestamp(:current_epoch), :user_id)"
                        ),
                        {
                            "wa_code": wa_code,
                            "locus": locus["name"],
                            "allele": allele,
                            "val": int(request.form[locus["name"] + f"_{allele}"]) if request.form[locus["name"] + f"_{allele}"] else None,
                            "current_epoch": current_epoch,
                            "user_id": "OK|" + session.get("user_name", session["email"]),
                        },
                    )

                    # set note in wa_loci_notes
                    if request.form[locus["name"] + f"_{allele}_notes"]:
                        con.execute(
                            text(
                                (
                                    "INSERT INTO wa_loci_notes (wa_code, locus, allele, timestamp, note, user_id) "
                                    "VALUES (:wa_code, :locus, :allele, to_timestamp(:current_epoch), :note, :user_id)"
                                )
                            ),
                            {
                                "wa_code": wa_code,
                                "locus": locus["name"],
                                "allele": allele,
                                "note": request.form[locus["name"] + f"_{allele}_notes"]
                                if request.form[locus["name"] + f"_{allele}_notes"]
                                else None,
                                "current_epoch": current_epoch,
                                "user_id": session.get("user_name", session["email"]),
                            },
                        )

        # update redis
        rdis.set(wa_code, json.dumps(fn.get_wa_loci_values(wa_code, loci_list)[0]))

        # update genotype_locus
        loci_list: dict = fn.get_loci_list()

        for locus in loci:
            for allele in ["a", "b"]:
                if locus["name"] + f"_{allele}" in request.form and request.form[locus["name"] + f"_{allele}"]:
                    sql = text(
                        "SELECT DISTINCT (SELECT val FROM wa_locus WHERE locus = :locus AND allele = :allele AND wa_code = wa_scat_dw_mat.wa_code ORDER BY timestamp DESC LIMIT 1) AS val "
                        "FROM wa_scat_dw_mat "
                        "WHERE genotype_id = (SELECT genotype_id FROM wa_results WHERE wa_code = :wa_code)"
                    )
                    rows = con.execute(sql, {"locus": locus["name"], "allele": allele, "wa_code": wa_code}).mappings().all()

                    if len(rows) == 1:  # all wa code have the same value
                        sql = text(
                            "SELECT distinct (SELECT id FROM genotype_locus where locus = :locus AND allele = :allele AND genotype_id = wa_scat_dw_mat.genotype_id ORDER BY timestamp DESC LIMIT 1) AS id "
                            "FROM wa_scat_dw_mat "
                            "WHERE genotype_id = (SELECT genotype_id FROM wa_results where wa_code = :wa_code)"
                        )

                        rows2 = con.execute(sql, {"locus": locus["name"], "allele": allele, "wa_code": wa_code}).mappings().all()

                        # 'OK|' is inserted before the user_id field to demonstrate that allele value has changed (or not) -> green
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
                                    "user_id": "OK|" + session.get("user_name", session["email"]),
                                },
                            )

                            # get genotype id
                            genotype_id = (
                                con.execute(text("SELECT genotype_id FROM genotype_locus WHERE id = :id"), {"id": row2["id"]})
                                .mappings()
                                .fetchone()["genotype_id"]
                            )

                            rdis.set(genotype_id, json.dumps(fn.get_genotype_loci_values(genotype_id, loci_list)))

        return redirect(f"/view_genetic_data/{wa_code}")


@app.route("/view_genetic_data_history/<wa_code>/<locus>")
@fn.check_login
def view_genetic_data_history(wa_code: str, locus: str):
    with fn.conn_alchemy().connect() as con:
        # get info about WA code
        row = (
            con.execute(text("SELECT sex_id, genotype_id FROM wa_results WHERE wa_code = :wa_code"), {"wa_code": wa_code})
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
                        "SELECT allele, val, to_char(timestamp, 'YYYY-MM-DD HH24:MI:SS') AS timestamp "
                        "FROM wa_locus WHERE wa_code = :wa_code and locus = :locus ORDER BY allele,timestamp ASC"
                    )
                ),
                {"wa_code": wa_code, "locus": locus},
            )
            .mappings()
            .all()
        )

        locus_notes = {"a": {"value": "-", "notes": "", "user_id": ""}, "b": {"value": "-", "notes": "", "user_id": ""}}
        locus_notes = (
            con.execute(
                text(
                    (
                        "SELECT allele,note,user_id, to_char(timestamp, 'YYYY-MM-DD HH24:MI:SS') AS timestamp "
                        "FROM wa_loci_notes WHERE wa_code = :wa_code AND locus = :locus ORDER BY timestamp ASC"
                    )
                ),
                {"wa_code": wa_code, "locus": locus},
            )
            .mappings()
            .all()
        )

        """
        locus_values = (
            con.execute(
                text(
                    "SELECT *, extract(epoch from timestamp)::integer AS epoch, "
                    "to_char(timestamp, 'YYYY-MM-DD HH24:MI:SS') AS formatted_timestamp, notes "
                    "FROM wa_locus "
                    "WHERE wa_code = :wa_code AND locus = :locus "
                    "ORDER BY timestamp DESC, allele ASC"
                ),
                {"wa_code": wa_code, "locus": locus},
            )
            .mappings()
            .all()
        )
        """

        return render_template(
            "view_genetic_data_history.html",
            header_title=f"{wa_code} genetic data",
            wa_code=wa_code,
            locus=locus,
            locus_values=locus_values,
            locus_notes=locus_notes,
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
    let user add a note on wa_code locus_name allele timestamp
    """

    con = fn.conn_alchemy().connect()

    data = {"wa_code": wa_code, "locus": locus, "allele": allele}

    if request.method == "GET":
        row = (
            con.execute(
                text("SELECT val FROM wa_locus WHERE wa_code = :wa_code AND locus = :locus AND allele = :allele "),
                data,
            )
            .mappings()
            .fetchone()
        )

        if row is None:
            return "WA code / Locus / allele not found"

        data["value"] = row["val"]

        notes = (
            con.execute(
                text(
                    (
                        "SELECT "
                        "CASE WHEN note IS NULL THEN '' ELSE note END, "
                        "CASE WHEN user_id IS NULL THEN '' ELSE user_id END, "
                        "date_trunc('second', timestamp) AS timestamp "
                        "FROM wa_loci_notes "
                        "WHERE wa_code = :wa_code AND locus = :locus AND allele = :allele ORDER BY timestamp"
                    )
                ),
                data,
            )
            .mappings()
            .all()
        )

        return render_template(
            "add_wa_locus_note.html",
            header_title="Allele's notes",
            data=data,
            notes=notes,
        )

    if request.method == "POST":
        sql = text(
            "INSERT INTO wa_loci_notes (wa_code, locus, allele, timestamp, note, user_id) "
            "VALUES ("
            ":wa_code, :locus, :allele, "
            "NOW(), "
            ":new_note, "
            ":user_id "
            ")"
        )

        data["new_note"] = request.form["new_note"]
        data["user_id"] = session.get("user_name", session["email"])

        con.execute(sql, data)

        rdis.set(wa_code, json.dumps(fn.get_wa_loci_values(wa_code, fn.get_loci_list())[0]))

        # return redirect(session["url_wa_list"])
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

    con = fn.conn_alchemy().connect()

    data = {"genotype_id": genotype_id, "locus": locus, "allele": allele}

    genotype_locus = (
        con.execute(
            text("SELECT * FROM genotype_locus WHERE genotype_id = :genotype_id AND locus = :locus AND allele = :allele "),
            data,
        )
        .mappings()
        .fetchone()
    )

    if genotype_locus is None:
        return "Genotype ID / Locus / allele / timestamp not found"

    data["allele"] = allele
    data["value"] = genotype_locus["val"]
    data["notes"] = "" if genotype_locus["notes"] is None else genotype_locus["notes"]
    data["user_id"] = "" if genotype_locus["user_id"] is None else genotype_locus["user_id"]

    if request.method == "GET":
        values_history = (
            con.execute(
                text(
                    "SELECT val, "
                    "CASE WHEN notes IS NULL THEN '' ELSE notes END, "
                    "CASE WHEN user_id IS NULL THEN '' ELSE user_id END, "
                    "date_trunc('second', timestamp) AS timestamp "
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

        # notes history
        notes_history = (
            con.execute(
                text(
                    (
                        "SELECT * FROM  genotypes_loci_notes "
                        "WHERE genotype_id = :genotype_id "
                        "AND locus = :locus "
                        "AND allele = :allele "
                        "ORDER BY timestamp ASC "
                    )
                ),
                data,
            )
            .mappings()
            .all()
        )

        return render_template(
            "add_genotype_locus_note.html",
            header_title="Add note on genotype id",
            data=data,
            values_history=values_history,
            notes_history=notes_history,
        )

    if request.method == "POST":
        sql = text(
            "UPDATE genotype_locus "
            "SET notes = :notes, "
            "user_id = :user_id "
            "WHERE genotype_id = :genotype_id AND locus = :locus AND allele = :allele "
            "AND extract(epoch from timestamp)::integer = :timestamp"
        )

        data["notes"] = request.form["notes"]
        data["user_id"] = session.get("user_name", session["email"])

        con.execute(sql, data)

        # update cache
        loci_list: dict = fn.get_loci_list()

        rdis.set(genotype_id, json.dumps(fn.get_genotype_loci_values(genotype_id, loci_list)))

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
            con.execute(sql, {"genotype_id": genotype_id, "locus": locus, "allele": allele, "value": data["value"]}).mappings().all()
        ):
            con.execute(
                text("UPDATE wa_locus SET notes = :notes, user_id = :user_id WHERE id = :id "),
                {"notes": data["notes"], "id": row["id"], "user_id": session.get("user_name", session["email"])},
            )

            # update wa loci
            # [0] for accessing values
            rdis.set(row["wa_code"], json.dumps(fn.get_wa_loci_values(row["wa_code"], loci_list)[0]))

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
                con.execute(text("SELECT working_notes FROM genotypes WHERE genotype_id = :genotype_id"), {"genotype_id": genotype_id})
                .mappings()
                .fetchone()
            )
            if notes_row is None:
                return "Genotype ID not found"

            data["working_notes"] = "" if notes_row["working_notes"] is None else notes_row["working_notes"]

            return render_template("add_genotype_note.html", header_title=f"Add note to genotype {genotype_id}", data=data)

    if request.method == "POST":
        with fn.conn_alchemy().connect() as con:
            sql = text("UPDATE genotypes SET working_notes = :working_notes WHERE genotype_id = :genotype_id")
            data["working_notes"] = request.form["working_notes"]
            con.execute(sql, data)

            after_genotype_modif()

            return redirect(session["url_genotypes_list"])


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
        con.execute(text("REFRESH MATERIALIZED VIEW genotypes_list_mat"))
        con.execute(text("REFRESH MATERIALIZED VIEW wa_genetic_samples_mat"))


@app.route(
    "/set_wa_genotype/<wa_code>",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def set_wa_genotype(wa_code):
    """
    set wa genotype
    """
    con = fn.conn_alchemy().connect()

    if request.method == "GET":
        with fn.conn_alchemy().connect() as con:
            result = (
                con.execute(text("SELECT genotype_id FROM wa_results WHERE wa_code = :wa_code "), {"wa_code": wa_code})
                .mappings()
                .fetchone()
            )
        if result is None:
            flash(fn.alert_danger(f"WA code not found: {wa_code}"))
            return redirect(request.referrer)

        genotype_id = "" if result["genotype_id"] is None else result["genotype_id"]

        return render_template(
            "set_wa_genotype.html",
            header_title=f"Set genotype ID for WA code {wa_code}",
            wa_code=wa_code,
            current_genotype_id=genotype_id,
            return_url=request.referrer,
        )

    if request.method == "POST":
        with fn.conn_alchemy().connect() as con:
            sql = text("UPDATE wa_results SET genotype_id = :genotype_id WHERE wa_code = :wa_code")
            con.execute(sql, {"genotype_id": request.form["genotype_id"].strip(), "wa_code": wa_code})

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

    con = fn.conn_alchemy().connect()

    if request.method == "GET":
        result = (
            con.execute(text("SELECT status FROM genotypes WHERE genotype_id = :genotype_id"), {"genotype_id": genotype_id})
            .mappings()
            .fetchone()
        )

        if result is None:
            flash(fn.alert_danger(f"Genotype ID not found: {genotype_id}"))
            return redirect(session["url_genotypes_list"])

        status = "" if result["status"] is None else result["status"]

        return render_template(
            "set_status.html",
            header_title="Set status",
            genotype_id=genotype_id,
            current_status=status,
        )

    if request.method == "POST":
        sql = text("UPDATE genotypes SET status = :status WHERE genotype_id = :genotype_id")
        con.execute(sql, {"status": request.form["status"].strip().lower(), "genotype_id": genotype_id})
        after_genotype_modif()
        return redirect(session["url_genotypes_list"])


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

    con = fn.conn_alchemy().connect()

    if request.method == "GET":
        result = (
            con.execute(text("SELECT pack FROM genotypes WHERE genotype_id = :genotype_id"), {"genotype_id": genotype_id})
            .mappings()
            .fetchone()
        )

        if result is None:
            flash(fn.alert_danger(f"Genotype ID not found: {genotype_id}"))
            return redirect(session["url_genotypes_list"])

        pack = "" if result["pack"] is None else result["pack"]

        return render_template(
            "set_pack.html",
            header_title=f"Set pack for {genotype_id}",
            genotype_id=genotype_id,
            current_pack=pack,
        )

    if request.method == "POST":
        sql = text("UPDATE genotypes SET pack = :pack WHERE genotype_id = :genotype_id")
        con.execute(sql, {"pack": request.form["pack"].lower().strip(), "genotype_id": genotype_id})
        after_genotype_modif()
        return redirect(session["url_genotypes_list"])


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

    con = fn.conn_alchemy().connect()

    if request.method == "GET":
        result = (
            con.execute(text("SELECT sex FROM genotypes WHERE genotype_id = :genotype_id"), {"genotype_id": genotype_id})
            .mappings()
            .fetchone()
        )

        if result is None:
            flash(fn.alert_danger(f"Genotype ID not found: {genotype_id}"))
            return redirect(session["url_genotypes_list"])

        sex = "" if result["sex"] is None else result["sex"]

        return render_template(
            "set_sex.html",
            header_title=f"Set sex for {genotype_id}",
            genotype_id=genotype_id,
            current_sex=sex,
        )

    if request.method == "POST":
        if request.form["sex"].upper().strip() not in ("F", "M", ""):
            flash(fn.alert_danger(f"<big><b>Sex value not available ({request.form['sex'].upper().strip()})</b></big>"))
            return redirect(session["url_genotypes_list"])

        sql = text("UPDATE genotypes SET sex = :sex WHERE genotype_id = :genotype_id")
        con.execute(sql, {"sex": request.form["sex"].upper().strip(), "genotype_id": genotype_id})
        after_genotype_modif()

        # update WA results
        sql = text("UPDATE wa_results SET sex_id = :sex WHERE genotype_id = :genotype_id")
        con.execute(sql, {"sex": request.form["sex"].upper().strip(), "genotype_id": genotype_id})
        after_wa_results_modif()

        return redirect(session["url_genotypes_list"])


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

    con = fn.conn_alchemy().connect()

    if request.method == "GET":
        result = (
            con.execute(text("SELECT status_first_capture FROM genotypes WHERE genotype_id = :genotype_id"), {"genotype_id": genotype_id})
            .mappings()
            .fetchone()
        )

        if result is None:
            flash(fn.alert_danger(f"Genotype ID not found: {genotype_id}"))
            return redirect(session["url_genotypes_list"])

        status_first_capture = "" if result["status_first_capture"] is None else result["status_first_capture"]

        return render_template(
            "set_status_1st_recap.html",
            header_title=f"Set status at 1st capture for {genotype_id}",
            genotype_id=genotype_id,
            current_status_first_capture=status_first_capture,
            return_url=request.referrer,
        )

    if request.method == "POST":
        sql = text("UPDATE genotypes SET status_first_capture = :status_first_capture WHERE genotype_id = :genotype_id")
        con.execute(sql, {"status_first_capture": request.form["status_first_capture"], "genotype_id": genotype_id})
        after_genotype_modif()
        return redirect(session["url_genotypes_list"])


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
    con = fn.conn_alchemy().connect()

    if request.method == "GET":
        result = (
            con.execute(text("SELECT dispersal FROM genotypes WHERE genotype_id = :genotype_id"), {"genotype_id": genotype_id})
            .mappings()
            .fetchone()
        )

        if result is None:
            flash(fn.alert_danger(f"Genotype ID not found: {genotype_id}"))
            return redirect(session["url_genotypes_list"])

        dispersal = "" if result["dispersal"] is None else result["dispersal"]

        return render_template(
            "set_dispersal.html",
            header_title=f"Set dispersal for {genotype_id}",
            genotype_id=genotype_id,
            current_dispersal=dispersal,
        )

    if request.method == "POST":
        sql = text("UPDATE genotypes SET dispersal = :dispersal WHERE genotype_id = :genotype_id")
        con.execute(sql, {"dispersal": request.form["dispersal"].strip(), "genotype_id": genotype_id})
        after_genotype_modif()
        return redirect(session["url_genotypes_list"])


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

    con = fn.conn_alchemy().connect()

    if request.method == "GET":
        result = (
            con.execute(text("SELECT hybrid FROM genotypes WHERE genotype_id = :genotype_id"), {"genotype_id": genotype_id})
            .mappings()
            .fetchone()
        )

        if result is None:
            flash(fn.alert_danger(f"Genotype ID not found: {genotype_id}"))
            return redirect(session["url_genotypes_list"])

        hybrid = "" if result["hybrid"] is None else result["hybrid"]

        return render_template(
            "set_hybrid.html",
            header_title=f"Set hybrid state for {genotype_id}",
            genotype_id=genotype_id,
            current_hybrid=hybrid,
        )

    if request.method == "POST":
        sql = text("UPDATE genotypes SET hybrid = :hybrid WHERE genotype_id = :genotype_id")
        con.execute(sql, {"hybrid": request.form["hybrid"].strip(), "genotype_id": genotype_id})
        after_genotype_modif()
        return redirect(session["url_genotypes_list"])


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
    Ask for loading new definitive genotypes from XLSX file
    parse XLSX file and load the confirm page
    """

    if request.method == "GET":
        return render_template("load_definitive_genotypes_xlsx.html", header_title="Load genetic data for genotypes from XLSX/ODS file")

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

        con = fn.conn_alchemy().connect()

        # loci list
        loci_list = fn.get_loci_list()

        r, msg, data = extract_genotypes_data_from_xlsx(filename, loci_list)

        if r:
            flash(msg)
            return redirect("/load_definitive_genotypes_xlsx")

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

    con = fn.conn_alchemy().connect()

    # loci list
    loci_list = fn.get_loci_list()

    _, _, data = extract_genotypes_data_from_xlsx(filename, loci_list)

    sql = text(
        "INSERT INTO genotypes ("
        "genotype_id,"
        "date,"
        "pack,"
        "sex,"
        "age_first_capture,"
        "status_first_capture,"
        "dispersal,"
        "dead_recovery,"
        "status,"
        "tmp_id,"
        "notes,"
        "changed_status,"
        "hybrid,"
        "mtdna,"
        "record_status"
        ") VALUES ("
        ":genotype_id,"
        ":date,"
        ":pack,"
        ":sex,"
        ":age_first_capture,"
        ":status_first_capture,"
        ":dispersal,"
        ":dead_recovery,"
        ":status,"
        ":tmp_id,"
        ":notes,"
        ":changed_status,"
        ":hybrid,"
        ":mtdna,"
        "'OK'"
        ") "
        "ON CONFLICT (genotype_id) DO UPDATE "
        "SET "
        "date = EXCLUDED.date,"
        "pack = EXCLUDED.pack,"
        "sex = EXCLUDED.sex,"
        "age_first_capture = EXCLUDED.age_first_capture,"
        "status_first_capture = EXCLUDED.status_first_capture,"
        "dispersal = EXCLUDED.dispersal,"
        "dead_recovery = EXCLUDED.dead_recovery,"
        "status = EXCLUDED.status,"
        "tmp_id = EXCLUDED.tmp_id,"
        "notes = EXCLUDED.notes,"
        "changed_status = EXCLUDED.changed_status,"
        "hybrid = EXCLUDED.hybrid,"
        "mtdna = EXCLUDED.mtdna,"
        "record_status = 'OK'"
    )

    for idx in data:
        d = dict(data[idx])

        con.execute(sql, d)

        # insert loci
        for locus in loci_list:
            sql_loci = text(
                "INSERT INTO genotype_locus (genotype_id, locus, allele, val, timestamp) VALUES (:genotype_id, :locus, :allele, :val, NOW())"
            )
            for allele in ("a", "b"):
                if allele in d[locus]:
                    con.execute(sql_loci, {"genotype_id": d["genotype_id"], "locus": locus, "allele": allele, "val": d[locus][allele]})

    con.execute(text("CALL refresh_materialized_views()"))

    update_redis_with_genotypes_loci()

    flash(fn.alert_danger("Updating the new genotypes in progress. Wait for 5 minutes..."))

    return redirect("/genotypes")


def extract_genotypes_data_from_xlsx(filename, loci_list):
    """
    Extract and check data from a XLSX file
    """

    def test_nan(v):
        if str(v) == "NaT":
            return True
        return isinstance(v, float) and str(v) == "nan"

    if pl.Path(filename).suffix == ".XLSX":
        engine = "openpyxl"
    if pl.Path(filename).suffix == ".ODS":
        engine = "odf"

    try:
        df = pd.read_excel(pl.Path(params["upload_folder"]) / pl.Path(filename), sheet_name=0, engine=engine)
    except Exception:
        return True, fn.alert_danger("Error reading the file. Check your XLSX/ODS file"), {}

    for column in [
        "genotype_id",
        "date",
        "pack",
        "sex",
        "age_first_capture",
        "status_first_capture",
        "dispersal",
        "n_recaptures",
        "dead_recovery",
        "tmp_id",
        "notes",
        "status",
        "changed_status",
        "hybrid",
        "mtdna",
    ]:
        if column not in list(df.columns):
            return True, fn.alert_danger(f"Column {column} is missing"), {}

    all_data = {}
    for index, row in df.iterrows():
        data = {}
        for column in [
            "genotype_id",
            "date",
            "pack",
            "sex",
            "age_first_capture",
            "status_first_capture",
            "dispersal",
            "n_recaptures",
            "dead_recovery",
            "tmp_id",
            "notes",
            "status",
            "changed_status",
            "hybrid",
            "mtdna",
        ]:
            if column == "date":
                if str(row[column]) == "nan" or str(row[column]) == "NaT":
                    data[column] = None
                else:
                    data[column] = str(row[column])
            else:
                if isinstance(row[column], float) and str(row[column]) == "nan":
                    data[column] = ""
                else:
                    data[column] = str(row[column])

        loci_dict = {}
        for locus in loci_list:
            if locus in row:
                loci_dict[locus] = {}
                loci_dict[locus]["a"] = row[locus] if not test_nan(row[locus]) else None

            if loci_list[locus] == 2:
                if locus + ".1" in row:
                    if locus not in loci_dict:
                        loci_dict[locus] = {}
                    loci_dict[locus]["b"] = row[locus + ".1"] if not test_nan(row[locus + ".1"]) else None

        all_data[index] = {**data, **loci_dict}

    return 0, "OK", all_data
