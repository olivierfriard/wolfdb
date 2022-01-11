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

import functions as fn
from . import export

app = flask.Blueprint("genetic", __name__, template_folder="templates")

app.debug = True

params = config()


def get_cmap(n, name='viridis'):
    '''Returns a function that maps each index in 0, 1, ..., n-1 to a distinct
    RGB color; the keyword argument name must be a standard mpl colormap name.'''

    return plt.cm.get_cmap(name, n)


@app.route("/view_genotype/<genotype_id>")
@fn.check_login
def view_genotype(genotype_id):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("SELECT * FROM genotypes WHERE genotype_id = %s ", [genotype_id])
    genotype = cursor.fetchone()


    cursor.execute(("SELECT distinct wa_code FROM genotypes, wa_results "
                    "WHERE genotypes.genotype_id = wa_results.genotype_id "
                    "AND wa_results.genotype_id = %s ORDER BY wa_results.wa_code"),
                    [genotype_id])
    wa_codes = cursor.fetchall()

    # genetic data
    #cursor.execute("", [genotype_id])

    return render_template("view_genotype.html",
                           header_title=f"Genotype ID: {genotype_id}",
                           result=genotype,
                           n_recap=len(wa_codes),
                           wa_codes=wa_codes)



@app.route("/genotypes")
@fn.check_login
def genotypes():

    return render_template("genotypes.html",
                           header_title="Genotypes")


def get_loci_value(genotype_id, loci_list):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    loci_values = {}
    for locus in loci_list:
        loci_values[locus] = {}
        loci_values[locus]['a'] = {"value": "-", "notes": "" }
        loci_values[locus]['b'] = {"value": "-", "notes": "" }

    for locus in loci_list:

        cursor.execute(("SELECT *, extract(epoch from timestamp)::integer AS epoch FROM genotype_locus "
                        "WHERE genotype_id = %(genotype_id)s AND locus = %(locus)s AND allele = 'a' "
                        "UNION "
                        "SELECT *, extract(epoch from timestamp)::integer AS epoch FROM genotype_locus "
                        "WHERE genotype_id = %(genotype_id)s AND locus = %(locus)s AND allele = 'b' "
                        ),
                        {"genotype_id": genotype_id, "locus": locus})

        locus_val = cursor.fetchall()

        for row2 in locus_val:
            val = row2["val"] if row2["val"] is not None else "-"
            notes = row2["notes"] if row2["notes"] is not None else ""
            epoch = row2["epoch"] if row2["epoch"] is not None else ""

            loci_values[locus][row2["allele"]] = {"value": val, "notes": notes, "epoch": epoch}

    return loci_values


@app.route("/genotypes_list/<type>")
@app.route("/genotypes_list/<type>/<mode>")
@fn.check_login
def genotypes_list(type, mode="web"):
    """
    list of genotypes: all, temp, definitive
    """
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # loci list
    cursor.execute("SELECT name, n_alleles FROM loci ORDER BY position ASC")
    loci_list = {}
    for row in cursor.fetchall():
        loci_list[row["name"]] = row["n_alleles"]

    if type == "all":
        cursor.execute("SELECT * FROM genotypes ORDER BY genotype_id")
        results = cursor.fetchall()
        title = f"List of all {len(results)} genotypes"

    if type == "definitive":
        cursor.execute("SELECT * FROM genotypes WHERE status = 'OK' ORDER BY genotype_id")
        results = cursor.fetchall()
        title = f"List of {len(results)} definitive genotypes"

    if type == "temp":
        cursor.execute("SELECT * FROM genotypes WHERE status != 'OK' ORDER BY genotype_id")
        results = cursor.fetchall()
        title = f"List of {len(results)} temporary genotypes"

    loci_values = {}
    for row in results:
        loci_values[row["genotype_id"]] = dict(get_loci_value(row['genotype_id'], loci_list))

    if mode == "export":

        file_content = export.export_genotypes_list(loci_list, results, loci_values)

        response = make_response(file_content, 200)
        response.headers["Content-type"] = "application/application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        response.headers["Content-disposition"] = "attachment; filename=genotypes_list.xlsx"

        return response


    else:
        return render_template("genotypes_list.html",
                           header_title="List of genotypes",
                           title=title,
                           type=type,
                           results=results,
                           loci_list=loci_list,
                           loci_values=loci_values)



@app.route("/view_wa/<wa_code>")
@fn.check_login
def view_wa(wa_code):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute(("SELECT *, ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat,"
                    "ROUND(st_x(st_transform(geometry_utm, 4326))::numeric, 6) as longitude, "
                    "ROUND(st_y(st_transform(geometry_utm, 4326))::numeric, 6) as latitude "
                    " FROM scats WHERE wa_code = %s "), [wa_code]
    )
    result = cursor.fetchone()

    if result is not None:

        return redirect(f"/view_scat/{result['scat_id']}")

        '''
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
        '''


    else:

        cursor.execute(("SELECT *, ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat,"
                        "ROUND(st_x(st_transform(geometry_utm, 4326))::numeric, 6) as longitude, "
                        "ROUND(st_y(st_transform(geometry_utm, 4326))::numeric, 6) as latitude "
                        "FROM dead_wolves "
                        "WHERE wa_code = %s "), [wa_code]
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

    cursor.execute(("SELECT wa_code, sample_id, genotype_id, "
                   "ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat "
                   "FROM wa_scat_tissue "
                   "WHERE mtdna not like '%poor%' "
                   )
    )

    scat_features = []
    count, sum_lon, sum_lat  = 0, 0, 0
    for row in cursor.fetchall():

        scat_geojson = json.loads(row["scat_lonlat"])
        count += 1
        lon, lat = scat_geojson["coordinates"]
        sum_lon += lon
        sum_lat += lat

        if row['sample_id'].startswith("E"):
            color = "orange"
        elif row['sample_id'].startswith("T"):
            color = "purple"
        else:
            color = "red"

        scat_feature = {"geometry": dict(scat_geojson),
                        "type": "Feature",
                        "properties": {"style": {"color": color, "fillColor": color, "fillOpacity": 1},
                                       "popupContent": (f"""Scat ID: <a href="/view_scat/{row['sample_id']}" target="_blank">{row['sample_id']}</a><br>"""
                                                        f"""WA code: <a href="/view_wa/{row['wa_code']}" target="_blank">{row['wa_code']}</a><br>"""
                                                        f"""Genotype ID: {row['genotype_id']}""")
                                  },
                    "id": row['sample_id']
                   }

        scat_features.append(scat_feature)

    center = f"{sum_lat / count}, {sum_lon / count}"

    transect_features = []

    return render_template("plot_all_wa.html",
                           header_title="Plot of WA codes",
                           title=Markup(f"<h3>Plot of {len(scat_features)} WA codes. orange: scats, purple: tissues, red: other sample</h3>"),
                           map=Markup(fn.leaflet_geojson(center, scat_features, transect_features, zoom=8)),
                           distance=0
                           )


@app.route("/plot_wa_clusters/<distance>")
@fn.check_login
def plot_wa_clusters(distance):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute(("SELECT wa_code, sample_id, municipality, genotype_id, "
                    "ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat, "
                    f"ST_ClusterDBSCAN(geometry_utm, eps:={distance}, minpoints:=1) over() AS cid "
                    "FROM wa_scat_tissue "
                    "WHERE mtdna not like '%poor%'"
                    )
                   )

    max_cid = 0
    results = cursor.fetchall()
    for row in results:
        max_cid = max(max_cid, row["cid"])

    cmap = get_cmap(max_cid)

    scat_features = []
    min_lon, min_lat, max_lon, max_lat  = 180, 180, 0, 0
    for row in results:

        scat_geojson = json.loads(row["scat_lonlat"])
        lon, lat = scat_geojson["coordinates"]
        min_lon = min(min_lon, lon)
        min_lat = min(min_lat, lat)
        max_lon = max(max_lon, lon)
        max_lat = max(max_lat, lat)

        color = matplotlib.colors.to_hex(cmap(row['cid']), keep_alpha=False)
        scat_feature = {"geometry": dict(scat_geojson),
                    "type": "Feature",
                    "properties": { "style": {"color": color, "fillColor": color, "fillOpacity": 1},
                                       "popupContent": (f"""Sample ID: <a href="/view_scat/{row['sample_id']}" target="_blank">{row['sample_id']}</a><br>"""
                                                        f"""WA code: <a href="/view_wa/{row['wa_code']}" target="_blank">{row['wa_code']}</a><br>"""
                                                        f"""Genotype ID: {row['genotype_id']}<br>"""
                                                        f"""Cluster ID {row['cid']}:  <a href="/wa_analysis/{distance}/{row['cid']}">samples</a><br>"""
                                                        f"""<a href="/wa_analysis_group/web/{distance}/{row['cid']}">genotypes</a>""")

                                  },
                    "id": row["sample_id"]
                   }

        scat_features.append(scat_feature)

    center = f"{(min_lat + max_lat) / 2}, {(min_lon + max_lon) / 2}"

    return render_template("plot_all_wa.html",
                           header_title=f"WA codes clusters ({distance} m)",
                           title=Markup(f"<h3>Plot of {len(scat_features)} WA codes clusters</h3>DBSCAN: {distance} m<br>number of wa codes: {len(results)}"),
                           map=Markup(fn.leaflet_geojson(center, scat_features, [], zoom=7)),
                           distance=int(distance)
                           )


@app.route("/genetic_samples")
@fn.check_login
def genetic_samples():

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

    # union of scat and tissue samples
    '''
    cursor.execute(("SELECT wa_results.wa_code AS wa_code, scat_id AS sample_id, date, municipality, coord_east, coord_north, mtdna, wa_results.genotype_id AS genotype_id, sex_id "
                    "FROM wa_results, scats "
                    "WHERE wa_results.wa_code != ''  AND wa_results.wa_code = scats.wa_code  AND mtdna not like '%poor%' "
                    "UNION "
                    "SELECT wa_results.wa_code AS wa_code, tissue_id AS sample_id, data_ritrovamento AS date, municipality, coord_x AS coord_east, coord_y AS coord_north, mtdna, wa_results.genotype_id AS genotype_id, sex_id "
                    "FROM wa_results, dead_wolves WHERE wa_results.wa_code != ''  AND wa_results.wa_code = dead_wolves.wa_code  AND mtdna not like '%poor%'  "
                    "ORDER BY wa_code"))
    '''

    # TODO: check why 583 and 585
    cursor.execute("SELECT * FROM wa_scat_tissue WHERE mtdna NOT LIKE '%poor%' ORDER BY wa_code")

    wa_scats = cursor.fetchall()

    out = []
    loci_values = {}
    for row in wa_scats:
        loci_values[row["wa_code"]] = {}
        for locus in loci_list:
            loci_values[row["wa_code"]][locus] = {}
            loci_values[row["wa_code"]][locus]['a'] = {"value": "-", "notes": "" }
            loci_values[row["wa_code"]][locus]['b'] = {"value": "-", "notes": "" }

        has_notes = False

        for locus in loci_list:

            for allele in  ['a', 'b'][:loci_list[locus]]:

                cursor.execute(("SELECT val, notes, extract(epoch from timestamp)::integer AS epoch "
                                "FROM wa_locus "
                                "WHERE wa_code = %(wa_code)s AND locus = %(locus)s AND allele = %(allele)s "
                                "ORDER BY timestamp DESC LIMIT 1"
                               ),
                               {"wa_code": row["wa_code"], "locus": locus, "allele": allele})

                row2 = cursor.fetchone()

                if row2 is not None:
                    val = row2["val"] if row2["val"] is not None else "-"
                    notes = row2["notes"] if row2["notes"] is not None else ""
                    if notes:
                        has_notes = True
                    epoch = row2["epoch"] if row2["epoch"] is not None else ""

                else:
                    val = "-"
                    notes = ""
                    epoch = ""

                loci_values[row["wa_code"]][locus][allele] = {"value": val, "notes": notes, "epoch": epoch}


        if (with_notes == "all") or (with_notes == "with_notes" and has_notes == True):
            out.append(dict(row))

    if mode == "export":
        file_content = export.export_wa_genetic_samples(loci_list, out, loci_values, with_notes)

        response = make_response(file_content, 200)
        response.headers['Content-type'] = 'application/application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-disposition'] = "attachment; filename=wa_genetic_samples.xlsx"

        return response

    else:

        print(f"{loci_values['WA3246']=}")

        return render_template("wa_genetic_samples_list.html",
                            header_title="Genetic data of WA codes",
                            title=Markup(f"<h2>Genetic data of {len(out)} WA codes{' with notes' * (with_notes == 'with_notes')}</h2>"),
                            loci_list=loci_list,
                            wa_scats=out,
                            loci_values=loci_values,
                            with_notes=with_notes)





@app.route("/wa_analysis/<distance>/<cluster_id>")
@app.route("/wa_analysis/<distance>/<cluster_id>/<mode>")
@fn.check_login
def wa_analysis(distance: int, cluster_id: int, mode: str="web"):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # loci list
    cursor.execute("SELECT name, n_alleles FROM loci ORDER BY position ASC")
    loci_list = {}
    for row in cursor.fetchall():
        loci_list[row["name"]] = row["n_alleles"]

    # DBScan
    cursor.execute(("SELECT wa_code, sample_id, municipality, "
                    "ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat, "
                    f"ST_ClusterDBSCAN(geometry_utm, eps:={distance}, minpoints:=1) over() AS cluster_id "
                    "FROM wa_scat_tissue "
                    "WHERE mtdna not like '%poor%'"
                    )
                   )

    wa_list = []
    for row in cursor.fetchall():
        if row["cluster_id"] == int(cluster_id):
            wa_list.append(row["wa_code"])
    wa_list_str = "','".join(wa_list)


    cursor.execute(("SELECT wa_code, sample_id, date, municipality, coord_east, coord_north, mtdna, genotype_id, tmp_id, sex_id "
                    "FROM wa_scat_tissue "
                    f"WHERE wa_code in ('{wa_list_str}') "
                    "ORDER BY wa_code ASC"))

    wa_scats = cursor.fetchall()

    loci_values = {}
    for row in wa_scats:
        loci_values[row["wa_code"]] = {}
        for locus in loci_list:
            loci_values[row["wa_code"]][locus] = {}
            loci_values[row["wa_code"]][locus]['a'] = {"value": "-", "notes": "" }
            loci_values[row["wa_code"]][locus]['b'] = {"value": "-", "notes": "" }
        for locus in loci_list:

            for allele in  ['a', 'b'][:loci_list[locus]]:

                cursor.execute(("SELECT val, notes, extract(epoch from timestamp)::integer AS epoch "
                                "FROM wa_locus "
                                "WHERE wa_code = %(wa_code)s AND locus = %(locus)s AND allele = %(allele)s "
                                "ORDER BY timestamp DESC LIMIT 1"
                               ),
                               {"wa_code": row["wa_code"], "locus": locus, "allele": allele})

                row2 = cursor.fetchone()
                if row2 is not None:
                    val = row2["val"] if row2["val"] is not None else "-"
                    notes = row2["notes"] if row2["notes"] is not None else ""
                    epoch = row2["epoch"] if row2["epoch"] is not None else ""
                else:
                    val = "-"
                    notes = ""
                    epoch = ""

                loci_values[row["wa_code"]][locus][allele] = {"value": val, "notes": notes, "epoch": epoch}


    if mode == "export":

        file_content = export.export_wa_analysis(loci_list, wa_scats, loci_values, distance, cluster_id)

        response = make_response(file_content, 200)
        response.headers['Content-type'] = 'application/application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-disposition'] = "attachment; filename=wa_analysis.xlsx"

        return response

    else:

        return render_template("wa_analysis.html",
                                header_title = f"WA matches (cluster ID: {cluster_id} _ {distance} m))",
                                title=Markup(f"<h2>Matches (cluster id: {cluster_id} _ {distance} m)</h2>"),
                                loci_list=loci_list,
                                wa_scats=wa_scats,
                                loci_values=loci_values,
                                distance=distance,
                                cluster_id=cluster_id)



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
    cursor.execute(("SELECT wa_code, "
                    f"ST_ClusterDBSCAN(geometry_utm, eps:={distance}, minpoints:=1) over() AS cluster_id "
                    "FROM wa_scat_tissue WHERE mtdna not like '%poor%'"
                    )
    )

    wa_list = []
    for row in cursor.fetchall():
        if row["cluster_id"] == int(cluster_id):
            wa_list.append(row["wa_code"])
    wa_list_str = "','".join(wa_list)

    # fetch grouped genotypes
    cursor.execute(("SELECT genotype_id, count(wa_code) AS n_recap "
                    "FROM wa_scat_tissue "
                    f"WHERE wa_code in ('{wa_list_str}') "
                    "GROUP BY genotype_id "
                    "ORDER BY genotype_id ASC"))

    genotype_id = cursor.fetchall()

    loci_values = {}
    data = {}
    for row in genotype_id:

        if row['genotype_id'] is None:
            continue

        cursor.execute("SELECT * FROM genotypes WHERE genotype_id = %s",
                        [row['genotype_id']])
        result = cursor.fetchone()
        if result is None:
            continue
        data[row['genotype_id']] = dict(result)
        data[row['genotype_id']]["n_recap"] = row["n_recap"]

        loci_values[row["genotype_id"]] = dict(get_loci_value(row['genotype_id'], loci_list))

    if mode == "export":

        file_content = export.export_wa_analysis_group(loci_list, data, loci_values)

        response = make_response(file_content, 200)
        response.headers['Content-type'] = 'application/application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-disposition'] = "attachment; filename=genotypes_matches.xlsx"

        return response

    else:
        return render_template("wa_analysis_group.html",
                                header_title = f"Genotypes matches (cluster ID: {cluster_id} _ {distance} m))",
                                title=Markup(f"<h2>Genotypes matches (cluster id: {cluster_id} _ {distance} m)</h2>"),
                                loci_list=loci_list,
                                genotype_id=genotype_id,
                                data=data,
                                loci_values=loci_values,
                                distance=distance,
                                cluster_id=cluster_id)



@app.route("/view_genetic_data/<wa_code>")
@fn.check_login
def view_genetic_data(wa_code):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # loci list
    cursor.execute("SELECT name, n_alleles FROM loci ORDER BY position ASC")
    loci_list = {}
    for row in cursor.fetchall():
        loci_list[row["name"]] = row["n_alleles"]

    loci_values = {}
    for locus in loci_list:
        loci_values[locus] = {}
        loci_values[locus]['a'] = {"value": "-", "notes": "" }
        loci_values[locus]['b'] = {"value": "-", "notes": "" }

    for locus in loci_list:

        '''
        cursor.execute(("SELECT *, extract(epoch from timestamp)::integer AS epoch, "
                        "to_char(timestamp, 'YYYY-MM-DD HH24:MI:SS') AS formated_timestamp, notes "
                        "FROM wa_locus "
                        "WHERE wa_code = %(wa_code)s AND locus = %(locus)s AND allele = 'a' "
                        "UNION "
                        "SELECT *, extract(epoch from timestamp)::integer AS epoch, "
                        "to_char(timestamp, 'YYYY-MM-DD HH24:MI:SS') AS formated_timestamp, notes "
                        "FROM wa_locus "
                        "WHERE wa_code = %(wa_code)s AND locus = %(locus)s AND allele = 'b' "
                        "ORDER BY timestamp DESC LIMIT 2"
                        ),
                        {"wa_code": wa_code, "locus": locus})
        '''

        for allele in  ['a', 'b'][:loci_list[locus]]:

            cursor.execute(("SELECT val, notes, extract(epoch from timestamp)::integer AS epoch, "
                            "to_char(timestamp, 'YYYY-MM-DD HH24:MI:SS') AS formatted_timestamp "
                            "FROM wa_locus "
                            "WHERE wa_code = %(wa_code)s AND locus = %(locus)s AND allele = %(allele)s "
                            "ORDER BY timestamp DESC LIMIT 1"
                            ),
                            {"wa_code": wa_code, "locus": locus, "allele": allele})

            row2 = cursor.fetchone()
            if row2 is not None:
                val = row2["val"] if row2["val"] is not None else "-"
                notes = row2["notes"] if row2["notes"] is not None else ""
                epoch = row2["epoch"] if row2["epoch"] is not None else ""
                date = row2["formatted_timestamp"] if row2["formatted_timestamp"] is not None else ""
            else:
                val = "-"
                notes = ""
                epoch = ""
                date = ""

            loci_values[locus][allele] = {"value": val, "notes": notes, "epoch": epoch, "date": date}

    return render_template("view_genetic_data.html",
                           header_title=f"{wa_code} genetic data",
                           wa_code=wa_code,
                           loci_list=loci_list,
                           data=loci_values)


@app.route("/add_genetic_data/<wa_code>", methods=("GET", "POST",))
@fn.check_login
def add_genetic_data(wa_code):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM loci ORDER BY position")
    loci=cursor.fetchall()

    if request.method == "GET":

        return render_template("add_genetic_data.html",
                                wa_code=wa_code,
                                mode="modify",
                                loci=loci,
                                )

    if request.method == "POST":
        for locus in loci:
            for allele in ["a", "b"]:
                if locus['name'] + f"_{allele}" in request.form and request.form[locus['name'] + f"_{allele}"]:
                    cursor.execute("INSERT INTO wa_locus (wa_code, locus, allele, val, timestamp, notes) VALUES (%s, %s, %s, %s, NOW(), %s) ",
                           [wa_code, locus['name'], allele,
                           int(request.form[locus['name'] + f"_{allele}"]) if request.form[locus['name'] +f"_{allele}"] else None,
                           request.form[locus['name'] + f"_{allele}_notes"] if request.form[locus['name'] + f"_{allele}_notes"] else None
                           ])

        cursor.execute("UPDATE scats SET genetic_sample = 'Yes' WHERE wa_code = %s", [wa_code])

        connection.commit()
        return redirect(f"/view_genetic_data/{wa_code}")



@app.route("/view_genetic_data_history/<wa_code>/<locus>")
@fn.check_login
def view_genetic_data_history(wa_code, locus):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    locus_values = {"a": {"value": "-", "notes": ""}, "b": {"value": "-", "notes": ""}}

    cursor.execute(("SELECT *, extract(epoch from timestamp)::integer AS epoch, "
                    "to_char(timestamp, 'YYYY-MM-DD HH24:MI:SS') AS formatted_timestamp, notes "
                    "FROM wa_locus "
                    "WHERE wa_code = %(wa_code)s AND locus = %(locus)s "
                    "ORDER BY timestamp DESC, allele ASC"
                    ),
                    {"wa_code": wa_code, "locus": locus})

    locus_values = cursor.fetchall()

    return render_template("view_genetic_data_history.html",
                           header_title=f"{wa_code} genetic data",
                           wa_code=wa_code,
                           locus=locus,
                           locus_values=locus_values)



@app.route("/locus_note/<wa_code>/<locus>/<allele>/<timestamp>", methods=("GET", "POST",))
@fn.check_login
def locus_note(wa_code, locus, allele, timestamp):
    """
    let user add a note on wa_code locus_name allele timestamp
    """

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    data = {"wa_code": wa_code, "locus": locus, "allele": allele, "timestamp": int(timestamp)}

    if request.method == "GET":

        cursor.execute(("SELECT * FROM wa_locus "
                        "WHERE wa_code = %(wa_code)s "
                        "AND locus = %(locus)s "
                        "AND allele = %(allele)s "
                        "AND extract(epoch from timestamp)::integer = %(timestamp)s "
                        ),
                       data)
        wa_locus = cursor.fetchone()

        if wa_locus is None:
            return "WA code / Locus / allele / timestamp not found"

        data["value"] = wa_locus["val"]
        data["allele"] = allele
        data["notes"] = "" if wa_locus["notes"] is None else wa_locus["notes"]

        return render_template("add_wa_locus_note.html",
                               header_title=f"Add note on {wa_code} {locus} {allele}",
                               data=data,
                               return_url=request.referrer)


    if request.method == "POST":

        sql = ("UPDATE wa_locus SET notes = %(notes)s "
               "WHERE wa_code = %(wa_code)s "
               "AND locus = %(locus)s AND allele = %(allele)s "
               "AND extract(epoch from timestamp)::integer = %(timestamp)s"
        )

        data["notes"] = request.form["notes"]

        cursor.execute(sql, data)
        connection.commit()

        return redirect(request.form["return_url"])



@app.route("/genotype_locus_note/<genotype_id>/<locus>/<allele>/<timestamp>", methods=("GET", "POST",))
@fn.check_login
def genotype_locus_note(genotype_id, locus, allele, timestamp):
    """
    let user add a note on genotype_id locus allele timestamp
    """

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    data = {"genotype_id": genotype_id, "locus": locus, "allele": allele, "timestamp": int(timestamp)}


    cursor.execute(("SELECT * FROM genotype_locus "
                    "WHERE genotype_id = %(genotype_id)s AND locus = %(locus)s AND allele = %(allele)s "
                    "AND extract(epoch from timestamp)::integer = %(timestamp)s "
                    ),
                    data)
    wa_locus = cursor.fetchone()

    if wa_locus is None:
        return "Genotype ID / Locus / allele / timestamp not found"

    data["allele"] = allele
    data["value"] = wa_locus["val"]
    data["notes"] = "" if wa_locus["notes"] is None else wa_locus["notes"]

    if request.method == "GET":

        return render_template("add_genotype_locus_note.html",
                               header_title=f"Add note on {genotype_id} {locus} {allele}",
                               data=data,
                               return_url=request.referrer)


    if request.method == "POST":

        sql = ("UPDATE genotype_locus SET notes = %(notes)s "
               "WHERE genotype_id = %(genotype_id)s AND locus = %(locus)s AND allele = %(allele)s "
               "AND extract(epoch from timestamp)::integer = %(timestamp)s"
        )

        data["notes"] = request.form["notes"]

        cursor.execute(sql, data)
        connection.commit()

        # update wa_code

        sql = ("select id from wa_locus, wa_results "
               "WHERE wa_locus.wa_code = wa_results.wa_code "
               "AND wa_results.genotype_id = %(genotype_id)s "
               "AND wa_locus.locus = %(locus)s "
               "AND allele = %(allele)s "
               "AND val = %(value)s ")
        cursor.execute(sql, {"genotype_id": genotype_id, "locus": locus, "allele": allele, "value": data["value"]})
        rows = cursor.fetchall()
        for row in rows:

            cursor.execute(("UPDATE wa_locus "
                            "SET notes = %(notes)s "
                            "WHERE id = %(id)s "),
                            {"notes": data["notes"], "id": row["id"]})

        connection.commit()

        return redirect(request.form["return_url"])



@app.route("/genotype_note/<genotype_id>", methods=("GET", "POST",))
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
        return render_template("add_genotype_note.html",
                               data=data)

    if request.method == "POST":

        connection = fn.get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

        sql = ("UPDATE genotypes SET working_notes = %(working_notes)s "
               "WHERE genotype_id = %(genotype_id)s")

        data["working_notes"] = request.form["working_notes"]

        cursor.execute(sql, data)
        connection.commit()

        return redirect(request.form["return_url"])



@app.route("/set_status/<genotype_id>", methods=("GET", "POST",))
def set_status(genotype_id):
    """
    let user set the status of the individual
    """

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if request.method == "GET":

        # 'status' field used for definitive / temp
        cursor.execute(("SELECT position FROM genotypes "
                        "WHERE genotype_id = %s  "),
                       [genotype_id])
        result = cursor.fetchone()

        if result is None:
            flash(fn.alert_danger(f"Genotype ID not found: {genotype_id}"))
            return redirect(request.referrer)

        position = "" if result["position"] is None else result["position"]

        return render_template("set_status.html",
                               genotype_id=genotype_id,
                               current_position=position,
                               return_url=request.referrer)

    if request.method == "POST":

        sql = ("UPDATE genotypes SET position = %(position)s "
               "WHERE genotype_id = %(genotype_id)s ")

        cursor.execute(sql,
                       {"position": request.form["position"],
                        "genotype_id": genotype_id})

        connection.commit()

        return redirect(request.form["return_url"])



@app.route("/set_pack/<genotype_id>", methods=("GET", "POST",))
def set_pack(genotype_id):
    """
    let user set the pack of the individual
    """

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if request.method == "GET":

        # 'status' field used for definitive / temp
        cursor.execute(("SELECT pack FROM genotypes "
                        "WHERE genotype_id = %s  "),
                       [genotype_id])
        result = cursor.fetchone()

        if result is None:
            flash(fn.alert_danger(f"Genotype ID not found: {genotype_id}"))
            return redirect(request.referrer)

        pack = "" if result["pack"] is None else result["pack"]

        return render_template("set_pack.html",
                               genotype_id=genotype_id,
                               current_pack=pack,
                               return_url=request.referrer)

    if request.method == "POST":

        sql = ("UPDATE genotypes SET pack = %(pack)s "
               "WHERE genotype_id = %(genotype_id)s ")

        cursor.execute(sql,
                       {"pack": request.form["pack"],
                        "genotype_id": genotype_id})

        connection.commit()

        return redirect(request.form["return_url"])
