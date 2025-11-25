"""
WolfDB web service
(c) Olivier Friard

flask blueprint for transects management
"""

import flask
from flask import render_template, redirect, request, flash, make_response, session
from markupsafe import Markup
from sqlalchemy import text
from config import config
import json
import calendar
import datetime as dt

from .transect_form import Transect
import functions as fn
from . import transects_export

app = flask.Blueprint("transects", __name__, template_folder="templates")

params = config()
app.debug = params["debug"]


@app.route("/view_transect/<transect_id>")
@fn.check_login
def view_transect(transect_id):
    """
    Display transect data
    """

    scats_color = params["scat_color"]
    transects_color = params["transect_color"]
    tracks_color = params["track_color"]

    with fn.conn_alchemy().connect() as con:
        transect = (
            con.execute(
                text(
                    "SELECT *, "
                    "ST_AsGeoJSON(st_transform(multilines, 4326)) AS transect_geojson, "
                    "ROUND(ST_Length(multilines)) AS transect_length "
                    "FROM transects "
                    "WHERE transect_id = :transect_id"
                ),
                {"transect_id": transect_id},
            )
            .mappings()
            .fetchone()
        )

        if transect is None:
            flash(fn.alert_danger(f"<b>Transect {transect_id} not found</b>"))
            return redirect("/transects_list")

        transect_features = []
        min_lat, max_lat = 90, -90
        min_lon, max_lon = 90, -90

        if transect["transect_geojson"] is not None:
            transect_geojson = json.loads(transect["transect_geojson"])

            for line in transect_geojson["coordinates"]:
                latitudes = [lat for _, lat in line]
                longitudes = [lon for lon, _ in line]
                min_lat, max_lat = min(latitudes), max(latitudes)
                min_lon, max_lon = min(longitudes), max(longitudes)

            transect_feature = {
                "type": "Feature",
                "properties": {
                    # "style": {"stroke": transects_color, "stroke-width": 2, "stroke-opacity": 1},
                    "popupContent": f"Transect ID: {transect_id}",
                },
                "geometry": dict(transect_geojson),
                "id": 1,
            }
            transect_features = [transect_feature]

        # path
        results_paths = (
            con.execute(
                text(
                    "SELECT *,"
                    "(SELECT count(*) FROM scats WHERE scats.path_id = paths.path_id) AS n_scats "
                    "FROM paths "
                    "WHERE transect_id = :transect_id "
                    "AND (date between :start_date AND :end_date OR date IS NULL) "
                    "ORDER BY date ASC"
                ),
                {
                    "transect_id": transect_id,
                    "start_date": session["start_date"],
                    "end_date": session["end_date"],
                },
            )
            .mappings()
            .all()
        )

        # scats

        # number of scats
        scats = (
            con.execute(
                text(
                    (
                        "SELECT *, ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat FROM scats_list_mat "
                        "WHERE path_id LIKE :path_id "
                        " AND (date between :start_date AND :end_date OR date IS NULL) "
                    )
                ),
                {
                    "path_id": f"{transect_id}|%",
                    "start_date": session["start_date"],
                    "end_date": session["end_date"],
                },
            )
            .mappings()
            .all()
        )

        n_scats = len(scats)

        scat_features: list = []
        for row in scats:
            scat_geojson = json.loads(row["scat_lonlat"])

            lon, lat = scat_geojson["coordinates"]

            min_lat = min(min_lat, lat)
            max_lat = max(max_lat, lat)
            min_lon = min(min_lon, lon)
            max_lon = max(max_lon, lon)

            scat_feature = {
                "geometry": dict(scat_geojson),
                "type": "Feature",
                "properties": {
                    # "style": {"color": color, "fillColor": color },
                    "popupContent": (
                        f"""Scat ID: <a href="/view_scat/{row["scat_id"]}" target="_blank">{row["scat_id"]}</a><br>"""
                        f"""WA code: <a href="/view_wa/{row["wa_code"]}" target="_blank">{row["wa_code"]}</a><br>"""
                        f"""Genotype ID: {row["genotype_id2"]}"""
                    ),
                },
                "id": row["scat_id"],
            }
            scat_features.append(scat_feature)

        # tracks
        tracks = (
            con.execute(
                text(
                    "SELECT *, "
                    "ST_AsGeoJSON(st_transform(multilines, 4326)) AS track_geojson "
                    "FROM snow_tracks WHERE (transect_id = :transect_id OR transect_id LIKE :transect_id2) ORDER BY date DESC"
                ),
                {"transect_id": transect_id, "transect_id2": f"%{transect_id};%"},
            )
            .mappings()
            .all()
        )

        track_features: list = []
        for row in tracks:
            if row["track_geojson"] is not None:
                track_geojson = json.loads(row["track_geojson"])

                for line in track_geojson["coordinates"]:
                    latitudes = [lat for _, lat in line]
                    longitudes = [lon for lon, _ in line]

                    min_lat = min(min_lat, min(latitudes))
                    max_lat = max(max_lat, max(latitudes))

                    min_lon = min(min_lon, min(longitudes))
                    max_lon = max(max_lon, max(longitudes))

                track_feature = {
                    "geometry": dict(track_geojson),
                    "type": "Feature",
                    "properties": {
                        "popupContent": (
                            f"""Track ID: <a href="/view_snowtrack/{row["snowtrack_id"]}" target="_blank">{row["snowtrack_id"]}</a><br>"""
                        ),
                    },
                    "id": row["snowtrack_id"],
                }
                track_features.append(track_feature)

    return render_template(
        "view_transect.html",
        header_title=f"Transect {transect_id}",
        transect=transect,
        paths=results_paths,
        snowtracks=tracks,
        transect_id=transect_id,
        n_scats=n_scats,
        map=Markup(
            fn.leaflet_geojson(
                {
                    "scats": scat_features,
                    "scats_color": scats_color,
                    "transects": transect_features,
                    "transects_color": transects_color,
                    "tracks": track_features,
                    "tracks_color": tracks_color,
                    "fit": [[min_lat, min_lon], [max_lat, max_lon]],
                }
            )
        ),
        # scat_color=params["scat_color"],
        # dead_wolf_color=params["dead_wolf_color"],
        transect_color=params["transect_color"],
        # track_color=params["track_color"],
    )


@app.route("/transects_list")
@fn.check_login
def transects_list():
    # get all transects
    with fn.conn_alchemy().connect() as con:
        transects = (
            con.execute(text("SELECT * FROM transects ORDER BY transect_id"))
            .mappings()
            .all()
        )

        return render_template(
            "transects_list.html",
            header_title="List of transects",
            n_transects=len(transects),
            results=transects,
        )


@app.route("/export_transects")
@fn.check_login
def export_transects():
    """
    export all transects in XLSX
    """

    with fn.conn_alchemy().connect() as con:
        file_content = transects_export.export_transects(
            con.execute(text("SELECT * FROM transects ORDER BY transect_id"))
            .mappings()
            .all()
        )

        response = make_response(file_content, 200)
        response.headers["Content-type"] = (
            "application/application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response.headers["Content-disposition"] = (
            f"attachment; filename=transects_{dt.datetime.now():%Y-%m-%d_%H%M%S}.xlsx"
        )

        return response


@app.route("/new_transect", methods=("GET", "POST"))
@fn.check_login
def new_transect():
    """
    Insert a new transect
    """

    def not_valid(msg):
        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(fn.alert_danger(f"<b>{msg}</b>"))

        return render_template(
            "new_transect.html",
            header_title="Insert a new transect",
            title="New transect",
            action="/new_transect",
            form=form,
            default_values=default_values,
        )

    if request.method == "GET":
        form = Transect()
        return render_template(
            "new_transect.html",
            header_title="Insert a new transect",
            title="New transect",
            action="/new_transect",
            form=form,
            default_values={},
        )

    if request.method == "POST":
        form = Transect(request.form)

        if form.validate():
            with fn.conn_alchemy().connect() as con:
                # check if transect_id already exists
                rows = (
                    con.execute(
                        text(
                            "SELECT transect_id FROM transects WHERE UPPER(transect_id) = UPPER(:transect_id)"
                        ),
                        {"transect_id": request.form["transect_id"]},
                    )
                    .mappings()
                    .all()
                )
                if len(rows):
                    return not_valid(
                        f"The transect ID {request.form['transect_id']} already exists"
                    )

                # check province code
                row = (
                    con.execute(
                        text(
                            "SELECT * FROM geo_info WHERE province_code = :province_code"
                        ),
                        {"province_code": request.form["province_code"].upper()},
                    )
                    .mappings()
                    .fetchone()
                )
                if row is None:
                    return not_valid("Check the province code")
                transect_province_name = row["province_name"]
                transect_region = row["region"]

                data = {
                    "transect_id": request.form["transect_id"].upper().strip(),
                    "sector": request.form["sector"].strip(),
                    "location": request.form["location"].strip(),
                    "municipality": request.form["municipality"].strip(),
                    "province_code": request.form["province_code"].upper(),
                    "province": transect_province_name,
                    "region": transect_region,
                }

                if request.form["multilines"]:
                    sql = text(
                        "INSERT INTO transects (transect_id, sector, location, municipality, province_code, province, region, multilines) "
                        "VALUES (:transect_id, :sector, :location, :municipality, :province_code, :province, :region, ST_GeomFromText(:multilines , 32632))"
                    )
                    data["multilines"] = request.form["multilines"].strip()
                else:
                    sql = text(
                        "INSERT INTO transects (transect_id, sector, location, municipality, province, region) "
                        "VALUES (:transect_id, :sector, :location, :municipality, :province, :region)"
                    )

                try:
                    con.execute(
                        sql,
                        data,
                    )

                except Exception:
                    return not_valid("Check the MultiLineString field")

                return redirect("/transects_list")
        else:
            return not_valid("Transect form NOT validated")


@app.route("/edit_transect/<transect_id>", methods=("GET", "POST"))
@fn.check_login
def edit_transect(transect_id):
    def not_valid(msg):
        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(fn.alert_danger(f"<b>{msg}</b>"))

        return render_template(
            "new_transect.html",
            title="Edit transect",
            action=f"/edit_transect/{transect_id}",
            form=form,
            default_values=default_values,
        )

    if request.method == "GET":
        with fn.conn_alchemy().connect() as con:
            default_values = (
                con.execute(
                    text(
                        "SELECT transect_id, "
                        "CASE WHEN sector IS NULL THEN '' ELSE sector END, "
                        "location, municipality, province_code, "
                        "ST_AsText(multilines) AS multilines "
                        "FROM transects "
                        "WHERE transect_id = :transect_id"
                    ),
                    {"transect_id": transect_id},
                )
                .mappings()
                .fetchone()
            )

            """default_values["sector"] = "" if default_values["sector"] is None else default_values["sector"]"""

            form = Transect()

            form.multilines.data = default_values["multilines"]

            return render_template(
                "new_transect.html",
                header_title=f"Edit transect {transect_id}",
                title="Edit transect",
                action=f"/edit_transect/{transect_id}",
                form=form,
                default_values=default_values,
            )

    if request.method == "POST":
        form = Transect(request.form)
        if form.validate():
            with fn.conn_alchemy().connect() as con:
                # check if transect_id already exists
                if request.form["transect_id"] != transect_id:
                    if len(
                        con.execute(
                            text(
                                "SELECT transect_id FROM transects WHERE UPPER(transect_id) = UPPER(:transect_id)"
                            ),
                            {"transect_id": request.form["transect_id"]},
                        )
                        .mappings()
                        .all()
                    ):
                        return not_valid(
                            f"The transect ID {request.form['transect_id']} already exists"
                        )

                # extract province name and region
                row = (
                    con.execute(
                        text(
                            "SELECT * FROM geo_info WHERE province_code = :province_code"
                        ),
                        {"province_code": request.form["province_code"].upper()},
                    )
                    .mappings()
                    .fetchone()
                )
                if row is None:
                    return not_valid("Check the province code")
                transect_province_name = row["province_name"]
                transect_region = row["region"]

                """
                if request.form["province_code"].upper() in province_codes:
                    transect_province_name = province_codes[request.form["province_code"].upper()]["nome"]
                    transect_region = province_codes[request.form["province_code"].upper()]["regione"]
                else:
                    transect_province_name = request.form["province"].strip().upper()
                    transect_region = fn.province_name2region(request.form["province"])
                """

                sql = text(
                    "UPDATE transects SET transect_id = :_new_transect_id, sector = :sector, location = :location, "
                    " municipality = :municipality, province_code = :province_code, region = :region "
                    "WHERE transect_id = :transect_id"
                )

                con.execute(
                    sql,
                    {
                        "_new_transect_id": request.form["transect_id"].strip(),
                        "sector": request.form["sector"]
                        if request.form["sector"]
                        else None,
                        "location": request.form["location"].strip(),
                        "municipality": request.form["municipality"].strip(),
                        "province": transect_province_name,
                        "province_code": request.form["province_code"].upper(),
                        "region": transect_region,
                        "transect_id": transect_id,
                    },
                )

                if request.form["multilines"].strip():
                    try:
                        sql = text(
                            "UPDATE transects SET multilines = ST_GeomFromText(:multilines , 32632) WHERE transect_id = :transect_id"
                        )
                        con.execute(
                            sql,
                            {
                                "multilines": request.form["multilines"].strip(),
                                "transect_id": transect_id,
                            },
                        )

                    except Exception:
                        return not_valid("Check the MultiLineString field")

                return redirect(f"/view_transect/{transect_id}")
        else:
            return not_valid("Transect form NOT validated")


@app.route("/del_transect/<transect_id>")
@fn.check_login
def del_transect(transect_id):
    with fn.conn_alchemy().connect() as con:
        # check if path based on transect exist
        result = (
            con.execute(
                text(
                    "SELECT COUNT(*) AS n_paths FROM paths WHERE transect_id = :transect_id"
                ),
                {"transect_id": transect_id},
            )
            .mappings()
            .all()
        )
        if result["n_paths"] > 0:
            return "Some paths are based on this transect. Please remove them before"

        con.execute(
            "DELETE FROM transects WHERE transect_id = :transect_id",
            {"transect_id": transect_id},
        )
        return redirect("/transects_list")


@app.route("/plot_transects")
@fn.check_login
def plot_transects():
    """
    Plot all transects
    """

    with fn.conn_alchemy().connect() as con:
        transects_features: list = []
        tot_min_lat, tot_min_lon = 90, 90
        tot_max_lat, tot_max_lon = -90, -90
        count_transects: int = 0

        for row in (
            con.execute(
                text(
                    "SELECT transect_id, ST_AsGeoJSON(st_transform(multilines, 4326)) AS transect_lonlat FROM transects"
                )
            )
            .mappings()
            .all()
        ):
            if row["transect_lonlat"] is not None:
                transect_geojson = json.loads(row["transect_lonlat"])

                for line in transect_geojson["coordinates"]:
                    # bounding box
                    latitudes = [lat for _, lat in line]
                    longitudes = [lon for lon, _ in line]
                    tot_min_lat = min([tot_min_lat, min(latitudes)])
                    tot_max_lat = max([tot_max_lat, max(latitudes)])
                    tot_min_lon = min([tot_min_lon, min(longitudes)])
                    tot_max_lon = max([tot_max_lon, max(longitudes)])

                transect_feature = {
                    "geometry": dict(transect_geojson),
                    "type": "Feature",
                    "properties": {
                        "popupContent": f"""Transect ID: <a href="/view_transect/{row["transect_id"]}" target="_blank">{row["transect_id"]}</a>"""
                    },
                    "id": row["transect_id"],
                }

                transects_features.append(dict(transect_feature))
                count_transects += 1

            else:
                print(f"{row['transect_id']} WITHOUT coordinates")

    return render_template(
        "plot_transects.html",
        header_title="Plot of transects",
        map=Markup(
            fn.leaflet_geojson(
                {
                    "transects": transects_features,
                    "transects_color": params["transect_color"],
                    "fit": [[tot_min_lat, tot_min_lon], [tot_max_lat, tot_max_lon]],
                }
            )
        ),
        transect_color=params["transect_color"],
        count_transects=count_transects,
    )


@app.route("/transects_analysis")
@fn.check_login
def transects_analysis():
    with fn.conn_alchemy().connect() as con:
        # check if path based on transect exist
        transects = (
            con.execute(
                text("SELECT * FROM transects ORDER BY region, province, transect_id")
            )
            .mappings()
            .all()
        )

        out = """<style>    table{    border-width: 0 0 1px 1px;    border-style: solid;} td{    border-width: 1px 1px 0 0;    border-style: solid;    margin: 0;    }</style>    """

        season = [5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3, 4]

        out += "<table>"
        out += "<tr><th>Region</th><th>Province</th><th>transect ID</th>"
        for month in season:
            out += f"<th>{calendar.month_abbr[month]}</th>"
        out += "</tr>"

        for row in transects:
            transect_id = row["transect_id"]

            # print(f"{transect_id=}")

            transect_month = {}
            dates_list = {}
            completeness_list = {}

            for row_path in (
                con.execute(
                    text("SELECT * FROM paths WHERE transect_id = :transect_id"),
                    {"transect_id": transect_id},
                )
                .mappings()
                .all()
            ):
                # add date of path
                path_date = str(row_path["date"])
                path_month = int(path_date.split("-")[1])
                if path_month not in dates_list:
                    dates_list[path_month] = []
                dates_list[path_month].append(path_date)

                # add completeness
                path_completeness = str(row_path["completeness"])
                path_month = int(path_date.split("-")[1])
                if path_month not in completeness_list:
                    completeness_list[path_month] = []
                completeness_list[path_month].append(path_completeness)

                for row_scat in (
                    con.execute(
                        text("SELECT * FROM scats WHERE path_id = :path_id "),
                        {"path_id": row_path["path_id"]},
                    )
                    .mappings()
                    .all()
                ):
                    month = int(str(row_scat["date"]).split("-")[1])

                    if month not in transect_month:
                        transect_month[month] = {"samples": 0}

                    transect_month[month]["samples"] += 1

            out += f"<tr><td>{row['region']}</td><td>{row['province']}</td><td>{transect_id}</td>"

            for month in season:
                flag_path = False
                # date
                if month in dates_list:
                    out += f"<td>{', '.join(dates_list[month])}<br>"
                    flag_path = True
                else:
                    out += "<td>"

                if month in completeness_list:
                    out += f"{', '.join(completeness_list[month])}<br>"

                if month in transect_month:
                    out += f"{transect_month[month]['samples']}<br>"
                else:
                    if flag_path:
                        out += "0<br>"
                    else:
                        out += "<br>"

                out += "</td>"
            out += "</tr>"

        out += "</table>"
        return out


@app.route("/transects_n_samples_by_month/<year_init>/<year_end>")
@fn.check_login
def transects_n_samples_by_month(year_init, year_end):
    with fn.conn_alchemy().connect() as con:
        # check if path based on transect exist
        transects = (
            con.execute(text("SELECT * FROM transects ORDER BY transect_id"))
            .mappings()
            .all()
        )

        sampling_years = range(int(year_init), int(year_end) + 1)
        season_months: list = [5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3, 4]

        out: list = []

        # header
        row = ["path_id"]
        for year in sampling_years:
            for month in season_months:
                row.append(f"{year}-{month:02}")
        out.append(row)

        for transect in transects:
            transect_id = transect["transect_id"]
            row = [transect_id]

            for year in sampling_years:
                for month in season_months:
                    paths = (
                        con.execute(
                            text(
                                "SELECT path_id FROM paths "
                                "WHERE transect_id = :transect_id "
                                "AND EXTRACT(YEAR FROM date) = :year"
                                "AND EXTRACT(MONTH FROM date) = :month"
                            ),
                            {"transect_id": transect_id, "year": year, "month": month},
                        )
                        .mappings()
                        .all()
                    )
                    if len(paths):
                        scats = (
                            con.execute(
                                text(
                                    (
                                        "SELECT count(*) AS n_scats FROM scats "
                                        "WHERE path_id IN (SELECT path_id FROM paths WHERE transect_id = :transect_id AND EXTRACT(YEAR FROM date) = :year AND EXTRACT(MONTH FROM date) = :month)"
                                    )
                                ),
                                {
                                    "transect_id": transect_id,
                                    "year": year,
                                    "month": month,
                                },
                            )
                            .mappings()
                            .fetchone()
                        )
                        row.append(str(scats["n_scats"]))
                    else:
                        row.append("NA")
            out.append(row)

        out_str = "\n".join([z for z in ["\t".join(x) for x in out]])

        response = make_response(out_str, 200)
        response.headers["Content-type"] = "'text/tab-separated-values"
        response.headers["Content-disposition"] = (
            f"attachment; filename=transects_n-samples_{dt.datetime.now():%Y-%m-%d_%H%M%S}.tsv"
        )

        return response
