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
import json
import matplotlib
import matplotlib.pyplot as plt

import functions as fn

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


    cursor.execute("SELECT distinct wa_code FROM genotypes, wa_results WHERE genotypes.genotype_id = wa_results.genotype_id AND wa_results.genotype_id = %s ORDER BY wa_results.wa_code", [genotype_id])
    wa_codes = cursor.fetchall()

    # genetic data
    #cursor.execute("", [genotype_id])

    return render_template("view_genotype.html",
                           result=genotype,
                           n_recap=len(wa_codes),
                           wa_codes=wa_codes)


@app.route("/genotypes_list")
@fn.check_login
def genotypes_list():
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT distinct * from genotypes ORDER BY genotype_id")


    return render_template("genotypes_list.html",
                           results=cursor.fetchall())




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
    results = dict(cursor.fetchone())
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
                           results=results,
                           wa_result=wa_result,
                           map=Markup(fn.leaflet_geojson(center, scat_features, []))
                          )




@app.route("/plot_all_wa")
@fn.check_login
def plot_all_wa():

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute(("SELECT wa_results.wa_code AS wa_code, scat_id, ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat "
                   "FROM wa_results, scats "
                   "WHERE wa_results.wa_code != '' AND wa_results.wa_code = scats.wa_code "
                   "AND quality_genotype in ('yes', 'Yes') "
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

        scat_feature = {"geometry": dict(scat_geojson),
                        "type": "Feature",
                        "properties": {
                                       "popupContent": (f"""Scat ID: <a href="/view_scat/{row['scat_id']}" target="_blank">{row['scat_id']}</a><br>"""
                                                        f"""WA code: <a href="/view_wa/{row['wa_code']}" target="_blank">{row['wa_code']}</a> """)
                                  },
                    "id": row['scat_id']
                   }

        scat_features.append(scat_feature)

    center = f"{sum_lat / count}, {sum_lon / count}"

    transect_features = []

    return render_template("plot_all_wa.html",
                           title="Plot of WA codes",
                           map=Markup(fn.leaflet_geojson(center, scat_features, transect_features, zoom=8))
                           )


@app.route("/plot_wa_clusters/<distance>")
@fn.check_login
def plot_wa_clusters(distance):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    '''
    cursor.execute(("SELECT wa_code, scat_id, municipality, "
                    "ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat, "
                    f"ST_ClusterDBSCAN(geometry_utm, eps:={distance}, minpoints:=1) over() AS cid "
                    "FROM wa_scat "
                    "WHERE quality_genotype in ('yes', 'Yes') "
                    )
                   )
    '''

    cursor.execute(("SELECT wa_code, sample_id, municipality, "
                    "ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat, "
                    f"ST_ClusterDBSCAN(geometry_utm, eps:={distance}, minpoints:=1) over() AS cid "
                    "FROM wa_scat_tissue "
                    "WHERE quality_genotype in ('yes', 'Yes') "
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
                                                        f"""Cluster ID {row['cid']}:  <a href="/wa_analysis/2500/{row['cid']}">samples</a><br>"""
                                                        f"""<a href="/wa_analysis_group/2500/{row['cid']}">genotypes</a>""")

                                  },
                    "id": row["sample_id"]
                   }

        scat_features.append(scat_feature)

    center = f"{(min_lat + max_lat) / 2}, {(min_lon + max_lon) / 2}"

    return render_template("plot_all_wa.html",
                           title=Markup(f"<h3>Plot of WA codes clusters</h3>DBSCAN: {distance} m<br>number of wa codes: {len(results)}"),
                           map=Markup(fn.leaflet_geojson(center, scat_features, [], zoom=7))
                           )




@app.route("/wa_genetic_samples")
@fn.check_login
def genetic_samples():

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # loci list
    cursor.execute("SELECT name, n_alleles FROM loci ORDER BY position ASC")
    loci_list = {}
    for row in cursor.fetchall():
        loci_list[row["name"]] = row["n_alleles"]

    '''
    cursor.execute(("SELECT wa_results.wa_code AS wa_code, scat_id, date, municipality, coord_east, coord_north, mtdna, wa_results.genotype_id AS genotype_id "
                    "FROM wa_results, scats "
                    "WHERE "
                    "wa_results.wa_code != '' "
                    "AND wa_results.wa_code = scats.wa_code "
                    "AND quality_genotype in ('yes', 'Yes') "
                    "ORDER BY wa_results.wa_code ASC")
    )
    '''

    cursor.execute("""
SELECT wa_results.wa_code AS wa_code, scat_id AS sample_id, date, municipality, coord_east, coord_north, mtdna, wa_results.genotype_id AS genotype_id  FROM wa_results, scats WHERE wa_results.wa_code != ''  AND wa_results.wa_code = scats.wa_code  AND quality_genotype in ('yes', 'Yes')

UNION

SELECT wa_results.wa_code AS wa_code, tissue_id AS sample_id, data_ritrovamento AS date, municipality, coord_x AS coord_east, coord_y AS coord_north, mtdna, wa_results.genotype_id AS genotype_id  FROM wa_results, dead_wolves WHERE wa_results.wa_code != ''  AND wa_results.wa_code = dead_wolves.wa_code  AND quality_genotype in ('yes', 'Yes')

ORDER BY wa_code
""")

    wa_scats = cursor.fetchall()
    loci_values = {}
    for row in wa_scats:
        loci_values[row["wa_code"]] = {}
        for locus in loci_list:
            cursor.execute("SELECT * FROM wa_locus WHERE wa_code = %s AND locus = %s ORDER BY timestamp DESC LIMIT 1 ", [row["wa_code"], locus])
            row2 = cursor.fetchone()
            if row2 is None:
                value1 = "-"
                value2 = "-"
            else:
                if row2["value1"] is not None:
                    value1 = row2["value1"]
                else:
                    value1 = "-"
                if row2["value2"] is not None:
                    value2 = row2["value2"]
                else:
                    value2 = "-"

            if loci_list[locus] == 2:
                loci_values[row["wa_code"]][locus] = [value1, value2]
            else:
                loci_values[row["wa_code"]][locus] = [value1, ""]


    return render_template("wa_genetic_samples_list.html",
                           title=Markup(f"<h2>List of {len(wa_scats)} WA codes</h2>"),
                           loci_list=loci_list,
                           wa_scats=wa_scats,
                           loci_values=loci_values)





@app.route("/wa_analysis/<distance>/<cluster_id>")
@fn.check_login
def wa_analysis(distance: int, cluster_id: int):

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
                    "WHERE quality_genotype in ('yes', 'Yes') "
                    )
                   )

    wa_list = []
    for row in cursor.fetchall():
        if row["cluster_id"] == int(cluster_id):
            wa_list.append(row["wa_code"])
    wa_list_str = "','".join(wa_list)


    cursor.execute(("SELECT wa_code, sample_id, date, municipality, coord_east, coord_north, mtdna, genotype_id, sex_id "
                    "FROM wa_scat_tissue "
                    f"WHERE wa_code in ('{wa_list_str}') "
                    "ORDER BY wa_code ASC"))


    wa_scats = cursor.fetchall()
    loci_values = {}
    for row in wa_scats:
        loci_values[row["wa_code"]] = {}
        for locus in loci_list:
            cursor.execute("SELECT value1, value2, extract(epoch from timestamp)::integer AS timestamp FROM wa_locus WHERE wa_code = %s AND locus = %s ORDER BY timestamp DESC LIMIT 1 ", [row["wa_code"], locus])
            row2 = cursor.fetchone()
            if row2 is None:
                value1 = "-"
                value2 = "-"
                timestamp = "-"
            else:
                if row2["value1"] is not None:
                    value1 = row2["value1"]
                    timestamp = row2["timestamp"]
                else:
                    value1 = "-"

                if row2["value2"] is not None:
                    value2 = row2["value2"]
                    timestamp = row2["timestamp"]
                else:
                    value2 = "-"

            if loci_list[locus] == 2:
                loci_values[row["wa_code"]][locus] = {"values": [value1, value2], "timestamp": timestamp}
            else:
                loci_values[row["wa_code"]][locus] = {"values": [value1, ""], "timestamp": timestamp}


    return render_template("wa_analysis.html",
                            title=Markup(f"<h2>Matches (cluster id: {cluster_id})</h2>"),
                            loci_list=loci_list,
                            wa_scats=wa_scats,
                            loci_values=loci_values)





@app.route("/wa_analysis_group/<distance>/<cluster_id>")
@fn.check_login
def wa_analysis_group(distance: int, cluster_id: int):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # loci list
    cursor.execute("SELECT name, n_alleles FROM loci ORDER BY position ASC")
    loci_list = {}
    for row in cursor.fetchall():
        loci_list[row["name"]] = row["n_alleles"]

    # DBScan
    '''
    cursor.execute(("SELECT wa_code, scat_id, municipality, "
                    "ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat, "
                    f"ST_ClusterDBSCAN(geometry_utm, eps:={distance}, minpoints:=1) over() AS cluster_id "
                    "FROM wa_scat "
                    "WHERE quality_genotype in ('yes', 'Yes') "
                    )
                   )
    '''
    cursor.execute(("SELECT wa_code, "
                    f"ST_ClusterDBSCAN(geometry_utm, eps:={distance}, minpoints:=1) over() AS cluster_id "
                    "FROM wa_scat_tissue WHERE quality_genotype in ('yes', 'Yes')"
                    )
    )


    wa_list = []
    for row in cursor.fetchall():
        if row["cluster_id"] == int(cluster_id):
            wa_list.append(row["wa_code"])
    wa_list_str = "','".join(wa_list)

    # fetch grouped genotypes
    cursor.execute(("SELECT genotype_id "
                    "FROM wa_scat_tissue "
                    f"WHERE wa_code in ('{wa_list_str}') "
                    "GROUP BY genotype_id "
                    "ORDER BY genotype_id ASC"))


    genotype_id = cursor.fetchall()

    loci_values = {}
    sex_list = {}
    for row in genotype_id:

        # sex
        cursor.execute("SELECT sex_id FROM wa_scat_tissue WHERE wa_code in (select wa_code from wa_results where genotype_id = %s)",
                        [row['genotype_id']])
        sex = cursor.fetchall()
        sex_list[row['genotype_id']] = []
        for row3 in sex:
            sex_list[row['genotype_id']].append(row3["sex_id"])

        loci_values[row["genotype_id"]] = {}
        for locus in loci_list:

            cursor.execute(("SELECT value1, value2, extract(epoch from timestamp)::integer AS timestamp "
                            "FROM wa_locus "
                            "WHERE wa_code = (select wa_code from wa_results where genotype_id = %s LIMIT 1) "
                            "AND locus = %s "
                            "ORDER BY timestamp DESC LIMIT 1 "
                            ),
                            [row['genotype_id'], locus]
            )

            row2 = cursor.fetchone()
            if row2 is None:
                value1 = "-"
                value2 = "-"
                timestamp = "-"
            else:
                if row2["value1"] is not None:
                    value1 = row2["value1"]
                    timestamp = row2["timestamp"]
                else:
                    value1 = "-"

                if row2["value2"] is not None:
                    value2 = row2["value2"]
                    timestamp = row2["timestamp"]
                else:
                    value2 = "-"

            if loci_list[locus] == 2:
                loci_values[row["genotype_id"]][locus] = {"values": [value1, value2], "timestamp": timestamp}
            else:
                loci_values[row["genotype_id"]][locus] = {"values": [value1, ""], "timestamp": timestamp}



    return render_template("wa_analysis_group.html",
                            title=Markup(f"<h2>Matches (cluster id: {cluster_id})</h2>"),
                            loci_list=loci_list,
                            genotype_id=genotype_id,
                            sex_list=sex_list,
                            #wa_scats=wa_scats,
                            loci_values=loci_values)





@app.route("/view_genetic_data/<wa_code>")
@fn.check_login
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
@fn.check_login
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
@fn.check_login
def view_genetic_data_history(wa_code, locus):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT *, to_char(timestamp, 'YYYY-MM-DD HH24:MI:SS') AS formated_timestamp FROM wa_locus WHERE wa_code = %s AND locus = %s ORDER by timestamp DESC", [wa_code, locus])
    results = cursor.fetchall()

    return render_template("view_genetic_data_history.html",
                            results = results,
                            wa_code=wa_code,
                            locus=locus)
