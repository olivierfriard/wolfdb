"""
WolfDB web service
(c) Olivier Friard

flask blueprint for scats management
"""


import flask
from flask import render_template, redirect, request, Markup, flash, session, make_response
import psycopg2
import psycopg2.extras
from config import config
import json
import matplotlib
import matplotlib.pyplot as plt
import subprocess
import redis
import pathlib as pl
import uuid
import pandas as pd

import functions as fn
from . import export

app = flask.Blueprint("genetic", __name__, template_folder="templates")

params = config()
app.debug = params["debug"]

params["excel_allowed_extensions"] = json.loads(params["excel_allowed_extensions"])


# db wolf -> db 0
rdis = redis.Redis(db=(0 if params["database"] == "wolf" else 1))


def get_cmap(n, name="viridis"):
    """Returns a function that maps each index in 0, 1, ..., n-1 to a distinct
    RGB color; the keyword argument name must be a standard mpl colormap name."""

    return plt.cm.get_cmap(name, n)


@app.route("/del_genotype/<genotype_id>")
@fn.check_login
def del_genotype(genotype_id):
    """
    set genotype as deleted (record_status field)
    """
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("UPDATE genotypes SET record_status = 'deleted' WHERE genotype_id = %s", [genotype_id])
    connection.commit()

    cursor.execute("UPDATE wa_results SET genotype_id = NULL WHERE genotype_id = %s", [genotype_id])
    connection.commit()

    flash(fn.alert_danger(f"<b>Genotype {genotype_id} deleted</b>"))

    return redirect(request.referrer)


@app.route("/def_genotype/<genotype_id>")
@fn.check_login
def def_genotype(genotype_id):
    """
    set genotype as definitive (record_status field)
    """
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("UPDATE genotypes SET record_status = 'OK' WHERE genotype_id = %s", [genotype_id])
    connection.commit()

    flash(fn.alert_danger(f"<b>Genotype {genotype_id} set as definitive</b>"))

    return redirect(request.referrer)


@app.route("/temp_genotype/<genotype_id>")
@fn.check_login
def temp_genotype(genotype_id):
    """
    set genotype as temporary (record_status field)
    """
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("UPDATE genotypes SET record_status = 'temp' WHERE genotype_id = %s", [genotype_id])
    connection.commit()

    flash(fn.alert_danger(f"<b>Genotype {genotype_id} set as temporary</b>"))

    return redirect(request.referrer)


@app.route("/view_genotype/<genotype_id>")
@fn.check_login
def view_genotype(genotype_id):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute(
        (
            "SELECT *, "
            "(SELECT 'Yes' FROM wa_scat_dw WHERE (sample_id like 'T%%' OR sample_id like 'M%%') AND genotype_id=genotypes.genotype_id LIMIT 1) AS dead_recovery "
            "FROM genotypes WHERE genotype_id = %s "
        ),
        [genotype_id],
    )

    genotype = cursor.fetchone()

    cursor.execute(
        (
            "SELECT wa_code, sample_id, "
            "ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS sample_lonlat "
            "FROM wa_scat_dw "
            "WHERE genotype_id = %s "
            "ORDER BY wa_code"
        ),
        [genotype_id],
    )

    wa_codes = cursor.fetchall()

    samples_features = []
    count, sum_lon, sum_lat = 0, 0, 0
    for row in wa_codes:

        sample_geojson = json.loads(row["sample_lonlat"])
        count += 1
        lon, lat = sample_geojson["coordinates"]
        sum_lon += lon
        sum_lat += lat

        if row["sample_id"].startswith("E"):
            color = "orange"
        elif row["sample_id"].startswith("T"):
            color = "purple"
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
        map = Markup(fn.leaflet_geojson(center, samples_features, transect_features=[], zoom=8))
    else:
        map = ""

    # genetic data
    # cursor.execute("", [genotype_id])

    return render_template(
        "view_genotype.html",
        header_title=f"Genotype ID: {genotype_id}",
        result=genotype,
        n_recap=len(wa_codes),
        wa_codes=wa_codes,
        map=map,
    )


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
def web_update_redis_with_genotypes_loci():
    """
    web interface to update redis with the genotypes loci values

    !require the update_redis_with_genotypes_loci_values file
    """
    update_redis_with_genotypes_loci()

    flash(fn.alert_danger(f"Redis updating with genotypes loci in progress"))

    return redirect("/admin")


@app.route("/update_redis_wa")
def update_redis_with_wa_loci():
    """
    update redis with the WA loci values

    !require the update_redis_with_wa_loci_values.py file
    """
    _ = subprocess.Popen(["python3", "update_redis_with_wa_loci_values.py"])

    flash(fn.alert_danger(f"Redis updating with WA loci in progress"))

    return redirect("/admin")


@app.route("/genotypes_list/<type>")
@app.route("/genotypes_list/<type>/<mode>")
@fn.check_login
def genotypes_list(type, mode="web"):
    """
    list of genotypes: all, temp, definitive

    read loci values from redis
    """

    if type not in ["all", "definitive", "temp", "deleted"]:
        return f"{type} not found"

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # loci list
    loci_list = {}
    cursor.execute("SELECT name, n_alleles FROM loci ORDER BY position ASC")
    for row in cursor.fetchall():
        loci_list[row["name"]] = row["n_alleles"]

    if "all" in type:
        filter = "WHERE record_status != 'deleted'"
        header_title = f"List of all genotypes"

    if "definitive" in type:
        filter = "WHERE record_status = 'OK'"
        header_title = f"List of definitive genotypes"

    if "temp" in type:
        filter = "WHERE record_status = 'temp'"
        header_title = f"List of temporary genotypes"

    if "deleted" in type:
        filter = "WHERE record_status = 'deleted'"
        header_title = f"List of temporary genotypes"

    cursor.execute(
        (
            "SELECT *, "
            "(SELECT count(sample_id) FROM wa_scat_dw WHERE genotype_id=genotypes.genotype_id) AS n_recaptures, "
            "(SELECT 'Yes' FROM wa_scat_dw WHERE (sample_id like 'T%' OR sample_id like 'M%') AND genotype_id=genotypes.genotype_id LIMIT 1) AS dead_recovery "
            f"FROM genotypes {filter} "
            "ORDER BY genotype_id"
        )
    )

    results = cursor.fetchall()

    loci_values = {}
    for row in results:
        loci_val = rdis.get(row["genotype_id"])
        if loci_val is not None:
            loci_values[row["genotype_id"]] = json.loads(loci_val)
        else:
            loci_values[row["genotype_id"]] = fn.get_loci_value(row["genotype_id"], loci_list)

    if mode == "export":

        file_content = export.export_genotypes_list(loci_list, results, loci_values)

        response = make_response(file_content, 200)
        response.headers[
            "Content-type"
        ] = "application/application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        response.headers["Content-disposition"] = "attachment; filename=genotypes_list.xlsx"

        return response

    else:

        return render_template(
            "genotypes_list.html",
            header_title=header_title,
            title=f"List of {len(results)} {type} genotypes".replace(" all", "").replace("_short", ""),
            type=type,
            results=results,
            loci_list=loci_list,
            loci_values=loci_values,
            short="",
        )


@app.route("/view_wa/<wa_code>")
@fn.check_login
def view_wa(wa_code):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute(
        (
            "SELECT *, ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat,"
            "ROUND(st_x(st_transform(geometry_utm, 4326))::numeric, 6) as longitude, "
            "ROUND(st_y(st_transform(geometry_utm, 4326))::numeric, 6) as latitude "
            " FROM wa_scat_dw WHERE wa_code = %s "
        ),
        [wa_code],
    )

    result = cursor.fetchone()

    if result is not None:

        if result["sample_id"].startswith("E"):
            return redirect(f"/view_scat/{result['sample_id']}")

        if result["sample_id"].startswith("T") or result["sample_id"].startswith("M"):
            return redirect(f"/view_tissue/{result['sample_id']}")

        """
        scat_geojson = json.loads(results["scat_lonlat"])
        scat_feature = {"geometry": dict(scat_geojson),
                        "type": "Feature",
                        "properties": {
                                    "popupContent": f"WA code: <b>{wa_code}</b>"
                                    },
                        "id": wa_code
                    }
        scat_features = [scat_feature]
        center = f"{results['latitude']}, {results['longitude']}"

        # genetic data
        cursor.execute("SELECT * FROM wa_results WHERE wa_code = %s", [wa_code])
        wa_result = cursor.fetchone()


        return render_template("view_wa.html",
                               header_title=f"WA code: {wa_code}",
                               go_back_url=request.referrer,
                               results=results,
                               wa_result=wa_result,
                               map=Markup(fn.leaflet_geojson(center, scat_features, []))
                               )
        """

    else:

        cursor.execute(
            (
                "SELECT *, ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat,"
                "ROUND(st_x(st_transform(geometry_utm, 4326))::numeric, 6) as longitude, "
                "ROUND(st_y(st_transform(geometry_utm, 4326))::numeric, 6) as latitude "
                "FROM dead_wolves "
                "WHERE wa_code = %s "
            ),
            [wa_code],
        )
        result = cursor.fetchone()

        if result is not None:
            return redirect(f"/view_tissue/{result['tissue_id']}")

        else:

            flash(fn.alert_danger(f"WA code not found: {wa_code}"))
            return redirect(request.referrer)


@app.route("/plot_all_wa")
@fn.check_login
def plot_all_wa():

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute(
        (
            "SELECT wa_code, sample_id, genotype_id, "
            "ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat "
            "FROM wa_scat_dw "
            "WHERE UPPER(mtdna) not like '%POOR DNA%' "
        )
    )

    scat_features = []
    count, sum_lon, sum_lat = 0, 0, 0
    for row in cursor.fetchall():

        scat_geojson = json.loads(row["scat_lonlat"])
        count += 1
        lon, lat = scat_geojson["coordinates"]
        sum_lon += lon
        sum_lat += lat

        if row["sample_id"].startswith("E"):
            color = "orange"
        elif row["sample_id"].startswith("T"):
            color = "purple"
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

    center = f"{sum_lat / count}, {sum_lon / count}"

    transect_features = []

    return render_template(
        "plot_all_wa.html",
        header_title="Plot of WA codes",
        title=Markup(
            f"<h3>Plot of {len(scat_features)} WA codes. orange: scats, purple: tissues, red: other sample</h3>"
        ),
        map=Markup(fn.leaflet_geojson(center, scat_features, transect_features, zoom=8)),
        distance=0,
    )


@app.route("/plot_wa_clusters/<distance>")
@fn.check_login
def plot_wa_clusters(distance):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute(
        (
            "SELECT wa_code, sample_id, municipality, genotype_id, "
            "ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat, "
            f"ST_ClusterDBSCAN(geometry_utm, eps:={distance}, minpoints:=1) over() AS cid "
            "FROM wa_scat_dw "
            "WHERE UPPER(mtdna) not like '%POOR DNA%' "
        )
    )

    max_cid = 0
    results = cursor.fetchall()
    for row in results:
        max_cid = max(max_cid, row["cid"])

    cmap = get_cmap(max_cid)

    scat_features = []
    min_lon, min_lat, max_lon, max_lat = 180, 180, 0, 0
    for row in results:

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

    center = f"{(min_lat + max_lat) / 2}, {(min_lon + max_lon) / 2}"

    return render_template(
        "plot_all_wa.html",
        header_title=f"WA codes clusters ({distance} m)",
        title=Markup(
            f"<h3>Plot of {len(scat_features)} WA codes clusters</h3>DBSCAN: {distance} m<br>number of wa codes: {len(results)}"
        ),
        map=Markup(fn.leaflet_geojson(center, scat_features, [], zoom=7)),
        distance=int(distance),
    )


@app.route("/genetic_samples")
@fn.check_login
def genetic_samples():
    """
    genetic samples home page
    """
    return render_template("genetic_samples.html", header_title="Genetic samples")


@app.route("/wa_genetic_samples")
@app.route("/wa_genetic_samples/<with_notes>")
@app.route("/wa_genetic_samples/<with_notes>/<mode>")
@fn.check_login
def wa_genetic_samples(with_notes="all", mode="web"):
    """
    display genetic data for WA code
    with_notes: all / with notes
    wa_genetic_samples_list.html
    """

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # loci list
    cursor.execute("SELECT name, n_alleles FROM loci ORDER BY position ASC")
    loci_list = {}
    for row in cursor.fetchall():
        loci_list[row["name"]] = row["n_alleles"]

    cursor.execute(
        (
            "SELECT wa_code, sample_id, date, municipality, coord_east, coord_north, genotype_id, tmp_id, mtdna, sex_id, "
            "(SELECT working_notes FROM genotypes WHERE genotype_id=wa_scat_dw.genotype_id) AS notes, "
            "(SELECT status FROM genotypes WHERE genotype_id=wa_scat_dw.genotype_id) AS status, "
            "(SELECT pack FROM genotypes WHERE genotype_id=wa_scat_dw.genotype_id) AS pack, "
            "(SELECT 'Yes' FROM dead_wolves WHERE tissue_id = sample_id LIMIT 1) as dead_recovery "
            "FROM wa_scat_dw "
            "WHERE UPPER(mtdna) not like '%POOR DNA%' "
            "ORDER BY wa_code"
        )
    )

    wa_scats = cursor.fetchall()

    out = []
    loci_values = {}
    for row in wa_scats:

        has_notes = False
        # genotype working notes
        if row["notes"] is not None and row["notes"]:
            has_notes = True

        loci_val = rdis.get(row["wa_code"])
        if loci_val is not None:
            loci_values[row["wa_code"]] = json.loads(loci_val)

            # check if loci have notes
            has_loci_notes = set(
                [
                    loci_values[row["wa_code"]][x][allele]["notes"]
                    for x in loci_values[row["wa_code"]]
                    for allele in ["a", "b"]
                ]
            ) != {""}

        else:
            loci_values[row["wa_code"]], has_loci_notes = fn.get_wa_loci_values(row["wa_code"], loci_list)

        if (with_notes == "all") or (with_notes == "with_notes" and (has_notes or has_loci_notes)):
            out.append(dict(row))

    if mode == "export":
        file_content = export.export_wa_genetic_samples(loci_list, out, loci_values, with_notes)

        response = make_response(file_content, 200)
        response.headers[
            "Content-type"
        ] = "application/application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        response.headers["Content-disposition"] = "attachment; filename=wa_genetic_samples.xlsx"

        return response

    else:

        session["go_back_url"] = f"/wa_genetic_samples"

        return render_template(
            "wa_genetic_samples_list.html",
            header_title="Genetic data of WA codes",
            title=Markup(f"<h2>Genetic data of {len(out)} WA codes{' with notes' * (with_notes == 'with_notes')}</h2>"),
            loci_list=loci_list,
            wa_scats=out,
            loci_values=loci_values,
            with_notes=with_notes,
        )


@app.route("/wa_analysis/<distance>/<cluster_id>")
@app.route("/wa_analysis/<distance>/<cluster_id>/<mode>")
@fn.check_login
def wa_analysis(distance: int, cluster_id: int, mode: str = "web"):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # loci list
    cursor.execute("SELECT name, n_alleles FROM loci ORDER BY position ASC")
    loci_list = {}
    for row in cursor.fetchall():
        loci_list[row["name"]] = row["n_alleles"]

    # DBScan
    cursor.execute(
        (
            "SELECT wa_code, sample_id, municipality, "
            "ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat, "
            f"ST_ClusterDBSCAN(geometry_utm, eps:={distance}, minpoints:=1) over() AS cluster_id "
            "FROM wa_scat_dw "
            "WHERE UPPER(mtdna) not like '%POOR DNA%' "
        )
    )

    wa_list = []
    for row in cursor.fetchall():
        if row["cluster_id"] == int(cluster_id):
            wa_list.append(row["wa_code"])
    wa_list_str = "','".join(wa_list)

    cursor.execute(
        (
            "SELECT wa_code, sample_id, date, municipality, coord_east, coord_north, "
            "mtdna, genotype_id, tmp_id, sex_id, "
            "(SELECT working_notes FROM genotypes WHERE genotype_id=wa_scat_dw.genotype_id) AS notes, "
            "(SELECT status FROM genotypes WHERE genotype_id=wa_scat_dw.genotype_id) AS status, "
            "(SELECT pack FROM genotypes WHERE genotype_id=wa_scat_dw.genotype_id) AS pack, "
            "(SELECT 'Yes' FROM dead_wolves WHERE tissue_id = sample_id LIMIT 1) as dead_recovery "
            "FROM wa_scat_dw "
            f"WHERE wa_code in ('{wa_list_str}') "
            "ORDER BY wa_code ASC"
        )
    )

    wa_scats = cursor.fetchall()

    loci_values = {}
    for row in wa_scats:
        loci_values[row["wa_code"]], _ = fn.get_wa_loci_values(row["wa_code"], loci_list)

    if mode == "export":

        file_content = export.export_wa_analysis(loci_list, wa_scats, loci_values, distance, cluster_id)

        response = make_response(file_content, 200)
        response.headers[
            "Content-type"
        ] = "application/application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        response.headers["Content-disposition"] = "attachment; filename=wa_analysis.xlsx"

        return response

    else:

        session["go_back_url"] = f"/wa_analysis/{distance}/{cluster_id}"

        return render_template(
            "wa_analysis.html",
            header_title=f"WA matches (cluster ID: {cluster_id} _ {distance} m))",
            title=Markup(f"<h2>Matches (cluster id: {cluster_id} _ {distance} m)</h2>"),
            loci_list=loci_list,
            wa_scats=wa_scats,
            loci_values=loci_values,
            distance=distance,
            cluster_id=cluster_id,
        )


@app.route("/wa_analysis_group/<mode>/<distance>/<cluster_id>")
@fn.check_login
def wa_analysis_group(mode: str, distance: int, cluster_id: int):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # loci list
    cursor.execute("SELECT name, n_alleles FROM loci ORDER BY position ASC")
    loci_list = {}
    for row in cursor.fetchall():
        loci_list[row["name"]] = row["n_alleles"]

    # DBScan
    cursor.execute(
        (
            "SELECT wa_code, "
            f"ST_ClusterDBSCAN(geometry_utm, eps:={distance}, minpoints:=1) over() AS cluster_id "
            "FROM wa_scat_dw "
            "WHERE UPPER(mtdna) not like '%POOR DNA%' "
        )
    )

    wa_list = []
    for row in cursor.fetchall():
        if row["cluster_id"] == int(cluster_id):
            wa_list.append(row["wa_code"])
    wa_list_str = "','".join(wa_list)

    # fetch grouped genotypes
    cursor.execute(
        (
            "SELECT genotype_id, count(wa_code) AS n_recap "
            "FROM wa_scat_dw "
            f"WHERE wa_code in ('{wa_list_str}') "
            "GROUP BY genotype_id "
            "ORDER BY genotype_id ASC"
        )
    )

    genotype_id = cursor.fetchall()

    loci_values = {}
    data = {}
    for row in genotype_id:

        if row["genotype_id"] is None:
            continue

        cursor.execute(
            (
                "SELECT *, "
                "(SELECT 'Yes' FROM wa_scat_dw WHERE (sample_id like 'T%%' OR sample_id like 'M%%')AND genotype_id=genotypes.genotype_id LIMIT 1) AS dead_recovery "
                "FROM genotypes WHERE genotype_id = %s"
            ),
            [row["genotype_id"]],
        )

        result = cursor.fetchone()
        if result is None:
            continue
        data[row["genotype_id"]] = dict(result)
        data[row["genotype_id"]]["n_recap"] = row["n_recap"]

        loci_val = rdis.get(row["genotype_id"])
        if loci_val is not None:
            loci_values[row["genotype_id"]] = json.loads(loci_val)
        else:
            loci_values[row["genotype_id"]] = fn.get_loci_value(row["genotype_id"], loci_list)

    if mode == "export":

        file_content = export.export_wa_analysis_group(loci_list, data, loci_values)
        response = make_response(file_content, 200)
        response.headers[
            "Content-type"
        ] = "application/application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        response.headers["Content-disposition"] = "attachment; filename=genotypes_matches.xlsx"
        return response

    else:
        return render_template(
            "wa_analysis_group.html",
            header_title=f"Genotypes matches (cluster ID: {cluster_id} _ {distance} m))",
            title=Markup(f"<h2>Genotypes matches (cluster id: {cluster_id} _ {distance} m)</h2>"),
            loci_list=loci_list,
            genotype_id=genotype_id,
            data=data,
            loci_values=loci_values,
            distance=distance,
            cluster_id=cluster_id,
        )


@app.route("/view_genetic_data/<wa_code>")
@fn.check_login
def view_genetic_data(wa_code):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # get sex of WA code
    cursor.execute("SELECT sex_id FROM wa_results WHERE wa_code = %s", [wa_code])
    sex = cursor.fetchone()["sex_id"]

    # loci list
    cursor.execute("SELECT name, n_alleles FROM loci ORDER BY position ASC")
    loci_list = {}
    for row in cursor.fetchall():
        loci_list[row["name"]] = row["n_alleles"]

    loci_values, _ = fn.get_wa_loci_values(wa_code, loci_list)

    return render_template(
        "view_genetic_data.html",
        header_title=f"{wa_code} genetic data",
        go_back_url=session.get("go_back_url", ""),
        wa_code=wa_code,
        loci_list=loci_list,
        sex=sex,
        data=loci_values,
    )


@app.route(
    "/add_genetic_data/<wa_code>",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def add_genetic_data(wa_code):
    """
    Let user add loci values for WA code
    """

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # get sex of WA code
    cursor.execute("SELECT sex_id FROM wa_results WHERE wa_code = %s", [wa_code])
    sex = cursor.fetchone()["sex_id"]

    cursor.execute("SELECT * FROM loci ORDER BY position ASC")
    loci = cursor.fetchall()

    # loci list
    cursor.execute("SELECT name, n_alleles FROM loci ORDER BY position ASC")
    loci_list = {}
    for row in cursor.fetchall():
        loci_list[row["name"]] = row["n_alleles"]

    loci_val = rdis.get(wa_code)
    if loci_val is not None:
        print("from redis")
        loci_values = json.loads(loci_val)
    else:
        print("from db")
        loci_values, _ = fn.get_wa_loci_values(wa_code, loci_list)

    if request.method == "GET":

        return render_template(
            "add_genetic_data.html",
            header_title=f"Add genetic data for {wa_code}",
            go_back_url=session.get("go_back_url", ""),
            wa_code=wa_code,
            loci=loci,
            loci_values=loci_values,
            sex=sex,
        )

    if request.method == "POST":

        # set sex
        cursor.execute("UPDATE wa_results SET sex_id = %s WHERE wa_code = %s", [request.form["sex"], wa_code])
        connection.commit()
        # test sex for all WA codes
        cursor.execute(
            "SELECT DISTINCT sex_id FROM wa_results WHERE genotype_id in (SELECT genotype_id FROM wa_results where wa_code = %s)",
            [wa_code],
        )
        rows = cursor.fetchall()
        if len(rows) == 1:  # same sex value for all WA codes -> Set genotype
            cursor.execute(
                "UPDATE genotypes SET sex = %s WHERE genotype_id = (SELECT genotype_id FROM wa_results WHERE wa_code = %s)",
                [rows[0]["sex_id"], wa_code],
            )
            connection.commit()

        # 'OK|' is inserted before the email in the user_id field to demonstrate that allele value has changed (or not) -> green
        for locus in loci:
            for allele in ["a", "b"]:
                if locus["name"] + f"_{allele}" in request.form and request.form[locus["name"] + f"_{allele}"]:
                    cursor.execute(
                        (
                            "INSERT INTO wa_locus "
                            "(wa_code, locus, allele, val, timestamp, notes, user_id) "
                            "VALUES (%s, %s, %s, %s, NOW(), %s, %s)"
                        ),
                        [
                            wa_code,
                            locus["name"],
                            allele,
                            int(request.form[locus["name"] + f"_{allele}"])
                            if request.form[locus["name"] + f"_{allele}"]
                            else None,
                            request.form[locus["name"] + f"_{allele}_notes"]
                            if request.form[locus["name"] + f"_{allele}_notes"]
                            else None,
                            "OK|" + session["email"],
                        ],
                    )

        connection.commit()

        # update redis
        rdis.set(wa_code, json.dumps(fn.get_wa_loci_values(wa_code, loci_list)[0]))

        # update genotype_locus
        loci_list = {}
        cursor.execute("SELECT name, n_alleles FROM loci ORDER BY position ASC")
        for row in cursor.fetchall():
            loci_list[row["name"]] = row["n_alleles"]

        for locus in loci:
            for allele in ["a", "b"]:
                if locus["name"] + f"_{allele}" in request.form and request.form[locus["name"] + f"_{allele}"]:

                    sql = (
                        "SELECT DISTINCT (SELECT val FROM wa_locus WHERE locus = %(locus)s AND allele = %(allele)s AND wa_code =wa_scat_dw.wa_code ORDER BY timestamp DESC LIMIT 1) AS val "
                        "FROM wa_scat_dw "
                        "WHERE genotype_id = (SELECT genotype_id FROM wa_results WHERE wa_code = %(wa_code)s)"
                    )

                    cursor.execute(sql, {"locus": locus["name"], "allele": allele, "wa_code": wa_code})
                    rows = cursor.fetchall()

                    if len(rows) == 1:  # all wa code have the same value

                        sql = (
                            "SELECT distinct (SELECT id FROM genotype_locus where locus = %(locus)s AND allele = %(allele)s AND genotype_id =wa_scat_dw.genotype_id ORDER BY timestamp DESC LIMIT 1) AS id "
                            "FROM wa_scat_dw "
                            "WHERE genotype_id = (SELECT genotype_id FROM wa_results where wa_code = %(wa_code)s)"
                        )

                        cursor.execute(sql, {"locus": locus["name"], "allele": allele, "wa_code": wa_code})

                        rows2 = cursor.fetchall()

                        for row2 in rows2:

                            cursor.execute(
                                (
                                    "UPDATE genotype_locus "
                                    "SET notes = %(notes)s, "
                                    "val = %(val)s, "
                                    "timestamp = NOW(), "
                                    "user_id = %(user_id)s "
                                    "WHERE id = %(id)s "
                                ),
                                {
                                    "notes": request.form[locus["name"] + f"_{allele}_notes"]
                                    if request.form[locus["name"] + f"_{allele}_notes"]
                                    else None,
                                    "id": row2["id"],
                                    "val": int(request.form[locus["name"] + f"_{allele}"])
                                    if request.form[locus["name"] + f"_{allele}"]
                                    else None,
                                    "user_id": "OK|" + session["email"],
                                },
                            )
                            connection.commit()

                            # get genotype id
                            cursor.execute("SELECT genotype_id FROM genotype_locus WHERE id = %s ", [row2["id"]])
                            genotype_id = cursor.fetchone()["genotype_id"]

                            rdis.set(genotype_id, json.dumps(fn.get_loci_value(genotype_id, loci_list)))

        connection.commit()

        return redirect(f"/view_genetic_data/{wa_code}")


@app.route("/view_genetic_data_history/<wa_code>/<locus>")
@fn.check_login
def view_genetic_data_history(wa_code, locus):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    locus_values = {"a": {"value": "-", "notes": "", "user_id": ""}, "b": {"value": "-", "notes": "", "user_id": ""}}

    cursor.execute(
        (
            "SELECT *, extract(epoch from timestamp)::integer AS epoch, "
            "to_char(timestamp, 'YYYY-MM-DD HH24:MI:SS') AS formatted_timestamp, notes "
            "FROM wa_locus "
            "WHERE wa_code = %(wa_code)s AND locus = %(locus)s "
            "ORDER BY timestamp DESC, allele ASC"
        ),
        {"wa_code": wa_code, "locus": locus},
    )

    locus_values = cursor.fetchall()

    return render_template(
        "view_genetic_data_history.html",
        header_title=f"{wa_code} genetic data",
        wa_code=wa_code,
        locus=locus,
        locus_values=locus_values,
    )


@app.route(
    "/locus_note/<wa_code>/<locus>/<allele>/<timestamp>",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def locus_note(wa_code, locus, allele, timestamp):
    """
    let user add a note on wa_code locus_name allele timestamp
    """

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    data = {"wa_code": wa_code, "locus": locus, "allele": allele, "timestamp": int(timestamp)}

    if request.method == "GET":

        cursor.execute(
            (
                "SELECT * FROM wa_locus "
                "WHERE wa_code = %(wa_code)s "
                "AND locus = %(locus)s "
                "AND allele = %(allele)s "
                "AND extract(epoch from timestamp)::integer = %(timestamp)s "
            ),
            data,
        )
        wa_locus = cursor.fetchone()

        if wa_locus is None:
            return "WA code / Locus / allele / timestamp not found"

        data["value"] = wa_locus["val"]
        data["allele"] = allele
        data["notes"] = "" if wa_locus["notes"] is None else wa_locus["notes"]
        data["user_id"] = "" if wa_locus["user_id"] is None else wa_locus["user_id"]

        return render_template(
            "add_wa_locus_note.html",
            header_title=f"Add note on {wa_code} {locus} {allele}",
            data=data,
            return_url=request.referrer,
        )

    if request.method == "POST":

        sql = (
            "UPDATE wa_locus SET notes = %(notes)s, "
            "user_id = %(user_id)s "
            "WHERE wa_code = %(wa_code)s "
            "AND locus = %(locus)s AND allele = %(allele)s "
            "AND extract(epoch from timestamp)::integer = %(timestamp)s"
        )

        data["notes"] = request.form["notes"]
        data["user_id"] = session["email"]

        cursor.execute(sql, data)
        connection.commit()

        return redirect(request.form["return_url"])


@app.route(
    "/genotype_locus_note/<genotype_id>/<locus>/<allele>/<timestamp>",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def genotype_locus_note(genotype_id, locus, allele, timestamp):
    """
    let user add a note on genotype_id locus allele timestamp
    """

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    data = {"genotype_id": genotype_id, "locus": locus, "allele": allele, "timestamp": int(timestamp)}

    cursor.execute(
        (
            "SELECT * FROM genotype_locus "
            "WHERE genotype_id = %(genotype_id)s AND locus = %(locus)s AND allele = %(allele)s "
            "AND extract(epoch from timestamp)::integer = %(timestamp)s "
        ),
        data,
    )
    wa_locus = cursor.fetchone()

    if wa_locus is None:
        return "Genotype ID / Locus / allele / timestamp not found"

    data["allele"] = allele
    data["value"] = wa_locus["val"]
    data["notes"] = "" if wa_locus["notes"] is None else wa_locus["notes"]
    data["user_id"] = "" if wa_locus["user_id"] is None else wa_locus["user_id"]

    if request.method == "GET":

        return render_template(
            "add_genotype_locus_note.html",
            header_title=f"Add note on {genotype_id} {locus} {allele}",
            data=data,
            return_url=request.referrer,
        )

    if request.method == "POST":

        sql = (
            "UPDATE genotype_locus "
            "SET notes = %(notes)s, "
            "user_id = %(user_id)s "
            "WHERE genotype_id = %(genotype_id)s AND locus = %(locus)s AND allele = %(allele)s "
            "AND extract(epoch from timestamp)::integer = %(timestamp)s"
        )

        data["notes"] = request.form["notes"]
        data["user_id"] = session["email"]

        cursor.execute(sql, data)
        connection.commit()

        # update cache
        loci_list = {}
        cursor.execute("SELECT name, n_alleles FROM loci ORDER BY position ASC")
        for row in cursor.fetchall():
            loci_list[row["name"]] = row["n_alleles"]

        rdis.set(genotype_id, json.dumps(fn.get_loci_value(genotype_id, loci_list)))

        # update wa_code
        sql = (
            "SELECT id FROM wa_locus, wa_results "
            "WHERE wa_locus.wa_code = wa_results.wa_code "
            "AND wa_results.genotype_id = %(genotype_id)s "
            "AND wa_locus.locus = %(locus)s "
            "AND allele = %(allele)s "
            "AND val = %(value)s "
        )
        cursor.execute(sql, {"genotype_id": genotype_id, "locus": locus, "allele": allele, "value": data["value"]})
        rows = cursor.fetchall()
        for row in rows:

            cursor.execute(
                ("UPDATE wa_locus " "SET notes = %(notes)s, " "user_id = %(user_id)s " "WHERE id = %(id)s "),
                {"notes": data["notes"], "id": row["id"], "user_id": session["email"]},
            )

        connection.commit()

        return redirect(request.form["return_url"])


@app.route(
    "/genotype_note/<genotype_id>",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def genotype_note(genotype_id):
    """
    let user add a note on genotype_id (working_notes)
    """

    data = {"genotype_id": genotype_id, "return_url": request.referrer}

    if request.method == "GET":
        connection = fn.get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cursor.execute(("SELECT working_notes FROM genotypes WHERE genotype_id = %s"), [genotype_id])

        notes_row = cursor.fetchone()
        if notes_row is None:
            return "Genotype ID not found"

        data["working_notes"] = "" if notes_row["working_notes"] is None else notes_row["working_notes"]

        return render_template("add_genotype_note.html", header_title=f"Add note to genotype {genotype_id}", data=data)

    if request.method == "POST":

        connection = fn.get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

        sql = "UPDATE genotypes SET working_notes = %(working_notes)s " "WHERE genotype_id = %(genotype_id)s"

        data["working_notes"] = request.form["working_notes"]

        cursor.execute(sql, data)
        connection.commit()

        return redirect(request.form["return_url"])


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
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if request.method == "GET":
        cursor.execute(("SELECT genotype_id FROM wa_results WHERE wa_code = %s "), [wa_code])
        result = cursor.fetchone()
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

        sql = "UPDATE wa_results SET genotype_id = %(genotype_id)s " "WHERE wa_code = %(wa_code)s "

        cursor.execute(sql, {"genotype_id": request.form["genotype_id"].strip(), "wa_code": wa_code})
        connection.commit()

        flash(
            fn.alert_danger(
                f"<b>Genotype ID modified for {wa_code}. New value is: {request.form['genotype_id'].strip()}</b>"
            )
        )

        return redirect(request.form["return_url"])


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

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if request.method == "GET":

        cursor.execute(("SELECT status FROM genotypes WHERE genotype_id = %s"), [genotype_id])
        result = cursor.fetchone()

        if result is None:
            flash(fn.alert_danger(f"Genotype ID not found: {genotype_id}"))
            return redirect(request.referrer)

        status = "" if result["status"] is None else result["status"]

        return render_template(
            "set_status.html",
            header_title="Set status",
            genotype_id=genotype_id,
            current_status=status,
            return_url=request.referrer,
        )

    if request.method == "POST":

        sql = "UPDATE genotypes SET status = %(status)s " "WHERE genotype_id = %(genotype_id)s "

        cursor.execute(sql, {"status": request.form["status"].strip().lower(), "genotype_id": genotype_id})

        connection.commit()

        return redirect(request.form["return_url"])


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

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if request.method == "GET":

        cursor.execute(("SELECT pack FROM genotypes WHERE genotype_id = %s  "), [genotype_id])
        result = cursor.fetchone()

        if result is None:
            flash(fn.alert_danger(f"Genotype ID not found: {genotype_id}"))
            return redirect(request.referrer)

        pack = "" if result["pack"] is None else result["pack"]

        return render_template(
            "set_pack.html",
            header_title=f"Set pack for {genotype_id}",
            genotype_id=genotype_id,
            current_pack=pack,
            return_url=request.referrer,
        )

    if request.method == "POST":

        sql = "UPDATE genotypes SET pack = %(pack)s " "WHERE genotype_id = %(genotype_id)s "

        cursor.execute(sql, {"pack": request.form["pack"].lower().strip(), "genotype_id": genotype_id})

        connection.commit()

        return redirect(request.form["return_url"])


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

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if request.method == "GET":

        cursor.execute(("SELECT sex FROM genotypes " "WHERE genotype_id = %s  "), [genotype_id])
        result = cursor.fetchone()

        if result is None:
            flash(fn.alert_danger(f"Genotype ID not found: {genotype_id}"))
            return redirect(request.referrer)

        sex = "" if result["sex"] is None else result["sex"]

        return render_template(
            "set_sex.html",
            header_title=f"Set sex for {genotype_id}",
            genotype_id=genotype_id,
            current_sex=sex,
            return_url=request.referrer,
        )

    if request.method == "POST":

        sql = "UPDATE genotypes SET sex = %(sex)s " "WHERE genotype_id = %(genotype_id)s "

        cursor.execute(sql, {"sex": request.form["sex"].upper().strip(), "genotype_id": genotype_id})

        connection.commit()

        # update WA results
        sql = "UPDATE wa_results SET sex_id = %(sex)s " "WHERE genotype_id = %(genotype_id)s "

        cursor.execute(sql, {"sex": request.form["sex"].upper().strip(), "genotype_id": genotype_id})

        connection.commit()

        return redirect(request.form["return_url"])


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

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if request.method == "GET":

        cursor.execute(("SELECT status_first_capture FROM genotypes " "WHERE genotype_id = %s  "), [genotype_id])
        result = cursor.fetchone()

        if result is None:
            flash(fn.alert_danger(f"Genotype ID not found: {genotype_id}"))
            return redirect(request.referrer)

        status_first_capture = "" if result["status_first_capture"] is None else result["status_first_capture"]

        return render_template(
            "set_status_1st_recap.html",
            header_title=f"Set status at 1st capture for {genotype_id}",
            genotype_id=genotype_id,
            current_status_first_capture=status_first_capture,
            return_url=request.referrer,
        )

    if request.method == "POST":

        sql = (
            "UPDATE genotypes SET status_first_capture = %(status_first_capture)s "
            "WHERE genotype_id = %(genotype_id)s "
        )

        cursor.execute(sql, {"status_first_capture": request.form["status_first_capture"], "genotype_id": genotype_id})

        connection.commit()

        return redirect(request.form["return_url"])


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

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if request.method == "GET":

        cursor.execute(("SELECT dispersal FROM genotypes " "WHERE genotype_id = %s  "), [genotype_id])
        result = cursor.fetchone()

        if result is None:
            flash(fn.alert_danger(f"Genotype ID not found: {genotype_id}"))
            return redirect(request.referrer)

        dispersal = "" if result["dispersal"] is None else result["dispersal"]

        return render_template(
            "set_dispersal.html",
            header_title=f"Set dispersal for {genotype_id}",
            genotype_id=genotype_id,
            current_dispersal=dispersal,
            return_url=request.referrer,
        )

    if request.method == "POST":

        sql = "UPDATE genotypes SET dispersal = %(dispersal)s " "WHERE genotype_id = %(genotype_id)s "

        cursor.execute(sql, {"dispersal": request.form["dispersal"].strip(), "genotype_id": genotype_id})

        connection.commit()

        return redirect(request.form["return_url"])


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

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if request.method == "GET":

        cursor.execute(("SELECT hybrid FROM genotypes " "WHERE genotype_id = %s  "), [genotype_id])
        result = cursor.fetchone()

        if result is None:
            flash(fn.alert_danger(f"Genotype ID not found: {genotype_id}"))
            return redirect(request.referrer)

        hybrid = "" if result["hybrid"] is None else result["hybrid"]

        return render_template(
            "set_hybrid.html",
            header_title=f"Set hybrid state for {genotype_id}",
            genotype_id=genotype_id,
            current_hybrid=hybrid,
            return_url=request.referrer,
        )

    if request.method == "POST":

        sql = "UPDATE genotypes SET hybrid = %(hybrid)s " "WHERE genotype_id = %(genotype_id)s "

        cursor.execute(sql, {"hybrid": request.form["hybrid"].strip(), "genotype_id": genotype_id})

        connection.commit()

        return redirect(request.form["return_url"])


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
        return render_template("load_definitive_genotypes_xlsx.html")

    if request.method == "POST":

        new_file = request.files["new_file"]

        # check file extension
        if pl.Path(new_file.filename).suffix.upper() not in params["excel_allowed_extensions"]:
            flash(
                fn.alert_danger(
                    "The uploaded file does not have an allowed extension (must be <b>.xlsx</b> or <b>.ods</b>)"
                )
            )
            return redirect(f"/load_definitive_genotypes_xlsx")

        try:
            filename = str(uuid.uuid4()) + str(pl.Path(new_file.filename).suffix.upper())
            new_file.save(pl.Path(params["upload_folder"]) / pl.Path(filename))
        except Exception:
            flash(fn.alert_danger("Error with the uploaded file"))
            return redirect(f"/load_definitive_genotypes_xlsx")

        connection = fn.get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # loci list
        loci_list = {}
        cursor.execute("SELECT name, n_alleles FROM loci ORDER BY position ASC")
        for row in cursor.fetchall():
            loci_list[row["name"]] = row["n_alleles"]

        r, msg, data = extract_genotypes_data_from_xlsx(filename, loci_list)

        if r:
            flash(msg)
            return redirect(f"/load_definitive_genotypes_xlsx")

        # check if genotype_id already in DB
        genotypes_list = "','".join([data[idx]["genotype_id"] for idx in data])
        sql = f"SELECT genotype_id FROM genotypes WHERE genotype_id IN ('{genotypes_list}')"
        cursor.execute(sql)
        genotypes_to_update = [row["genotype_id"] for row in cursor.fetchall()]

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

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # loci list
    loci_list = {}
    cursor.execute("SELECT name, n_alleles FROM loci ORDER BY position ASC")
    for row in cursor.fetchall():
        loci_list[row["name"]] = row["n_alleles"]

    _, _, data = extract_genotypes_data_from_xlsx(filename, loci_list)

    sql = (
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
        "%(genotype_id)s,"
        "%(date)s,"
        "%(pack)s,"
        "%(sex)s,"
        "%(age_first_capture)s,"
        "%(status_first_capture)s,"
        "%(dispersal)s,"
        "%(dead_recovery)s,"
        "%(status)s,"
        "%(tmp_id)s,"
        "%(notes)s,"
        "%(changed_status)s,"
        "%(hybrid)s,"
        "%(mtdna)s,"
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

        cursor.execute(sql, d)
        connection.commit()

        # insert loci
        for locus in loci_list:
            sql_loci = (
                "INSERT INTO genotype_locus (genotype_id, locus, allele, val, timestamp) VALUES "
                "(%s, %s, %s, %s, NOW())"
            )

            if "a" in d[locus]:
                cursor.execute(sql_loci, [d["genotype_id"], locus, "a", d[locus]["a"]])
                connection.commit()

            if "b" in d[locus]:
                cursor.execute(sql_loci, [d["genotype_id"], locus, "b", d[locus]["b"]])
                connection.commit()

    update_redis_with_genotypes_loci()

    flash(fn.alert_danger(f"Updating the new genotypes in progress. Wait for 5 minutes..."))

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
        return True, fn.alert_danger(f"Error reading the file. Check your XLSX/ODS file"), {}

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
