"""
WolfDB web service
(c) Olivier Friard

flask blueprint for paths management
"""

import flask
from flask import render_template, redirect, request, flash, session, make_response
from markupsafe import Markup
from sqlalchemy import text
from config import config
import json
import pathlib as pl
import os
import sys
import uuid
from . import paths_import
from .path_form import Path
import functions as fn
from . import paths_export

# import paths_completeness
import datetime as dt

app = flask.Blueprint("paths", __name__, template_folder="templates")

params = config()
app.debug = params["debug"]


def error_info(exc_info: tuple) -> tuple:
    """
    return details about error
    usage: error_info(sys.exc_info())

    Args:
        sys.exc_info() (tuple):

    Returns:
        tuple: error type, error file name, error line number
    """

    exc_type, exc_obj, exc_tb = exc_info
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]

    error_type, error_file_name, error_lineno = exc_obj, fname, exc_tb.tb_lineno

    return f"Error {error_type} in {error_file_name} at line #{error_lineno}"


@app.route("/paths")
@fn.check_login
def paths():
    """
    paths home page
    """

    return render_template("paths.html", header_title="Paths")


@app.route("/view_path/<path_id>")
@fn.check_login
def view_path(path_id):
    """
    Display path data, samples and map
    """

    with fn.conn_alchemy().connect() as con:
        path = con.execute(text("SELECT * FROM paths WHERE path_id = :path_id"), {"path_id": path_id}).mappings().fetchone()
        if path is None:
            return render_template("view_path.html", header_title=f"{path_id} not found", path={"path_id": ""}, path_id=path_id)

        # relative transect
        transect_id = path["transect_id"]
        transect = (
            con.execute(
                text(
                    "SELECT *, ST_AsGeoJSON(st_transform(multilines, 4326)) AS transect_geojson, "
                    "ROUND(ST_Length(multilines)) AS transect_length "
                    "FROM transects "
                    "WHERE transect_id = :transect_id"
                ),
                {"transect_id": transect_id},
            )
            .mappings()
            .fetchone()
        )
        if transect is not None:
            transect_geojson = json.loads(transect["transect_geojson"])

            transect_feature = {
                "type": "Feature",
                "geometry": dict(transect_geojson),
                "properties": {"popupContent": transect_id},
                "id": 1,
            }
            transect_features = [transect_feature]
            center = f"{transect_geojson['coordinates'][0][1]}, {transect_geojson['coordinates'][0][0]}"

        else:
            transect_features = []
            center = ""

        # scats
        scats = (
            con.execute(
                text(
                    "SELECT scat_id, wa_code, ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat, "
                    "ROUND(st_x(st_transform(geometry_utm, 4326))::numeric, 6) as longitude, "
                    "ROUND(st_y(st_transform(geometry_utm, 4326))::numeric, 6) as latitude "
                    "FROM scats WHERE path_id = :path_id"
                ),
                {"path_id": path_id},
            )
            .mappings()
            .all()
        )

        scat_features: list = []
        for scat in scats:
            scat_geojson = json.loads(scat["scat_lonlat"])
            scat_feature = {
                "geometry": dict(scat_geojson),
                "type": "Feature",
                "properties": {
                    "popupContent": f"""Scat ID: <a href="/view_scat/{scat['scat_id']}" target="_blank">{scat['scat_id']}</a>"""
                },
                "id": scat["scat_id"],
            }

            scat_features.append(scat_feature)
            center = f"{scat['latitude']}, {scat['longitude']}"

        # n tracks
        n_tracks = (
            con.execute(text("SELECT COUNT(*) AS n_tracks FROM snow_tracks WHERE transect_id = :transect_id"), {"transect_id": path_id})
            .mappings()
            .fetchone()["n_tracks"]
        )

    return render_template(
        "view_path.html",
        header_title=f"path ID: {path_id}",
        samples=scats,
        n_samples=len(scats),
        path=path,
        n_tracks=n_tracks,
        path_id=path_id,
        map=Markup(
            fn.leaflet_geojson(
                {
                    "scats": scat_features,
                    "scats_color": params["scat_color"],
                    "transects": transect_features,
                    "transects_color": params["transect_color"],
                    "center": center,
                }
            )
        ),
    )


@app.route("/paths_list")
@fn.check_login
def paths_list():
    """
    get list of paths
    """
    with fn.conn_alchemy().connect() as con:
        results = (
            con.execute(
                text(
                    "SELECT *, "
                    # "(SELECT province FROM transects WHERE transects.transect_id = paths.transect_id LIMIT 1) AS province, "
                    "(SELECT region FROM transects WHERE transects.transect_id = paths.transect_id LIMIT 1) AS region, "
                    "(SELECT COUNT(*) FROM scats WHERE path_id = paths.path_id) AS n_samples, "
                    "(SELECT COUNT(*) FROM snow_tracks WHERE transect_id = paths.transect_id AND date = paths.date) AS n_tracks "
                    "FROM paths "
                    "WHERE (date BETWEEN :start_date AND :end_date OR date IS NULL) "
                    "ORDER BY region ASC, "
                    # "province ASC, "
                    "path_id, date DESC "
                ),
                {
                    "start_date": session["start_date"],
                    "end_date": session["end_date"],
                },
            )
            .mappings()
            .all()
        )

    return render_template(
        "paths_list.html",
        header_title="List of paths",
        n_paths=len(results),
        results=results,
    )


@app.route("/export_paths")
@fn.check_login
def export_paths():
    """
    export tracks in XLSX file
    """

    with fn.conn_alchemy().connect() as con:
        file_content = paths_export.export_paths(
            con.execute(
                text(
                    "SELECT *, "
                    "(SELECT province FROM transects WHERE transects.transect_id = paths.transect_id LIMIT 1) AS province, "
                    "(SELECT region FROM transects WHERE transects.transect_id = paths.transect_id LIMIT 1) AS region, "
                    "(SELECT COUNT(*) FROM scats WHERE path_id = paths.path_id) AS n_samples, "
                    "(SELECT COUNT(*) FROM snow_tracks WHERE transect_id = paths.transect_id AND date = paths.date) AS n_tracks "
                    "FROM paths "
                    "WHERE date BETWEEN :start_date AND :end_date "
                    "ORDER BY region ASC, "
                    "province ASC, "
                    "path_id, date DESC "
                ),
                {
                    "start_date": session["start_date"],
                    "end_date": session["end_date"],
                },
            )
            .mappings()
            .all()
        )

    response = make_response(file_content, 200)
    response.headers["Content-type"] = "application/application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    response.headers["Content-disposition"] = f"attachment; filename=paths_{dt.datetime.now():%Y-%m-%d_%H%M%S}.xlsx"

    return response


@app.route("/new_path", methods=("GET", "POST"))
@fn.check_login
def new_path():
    def not_valid(msg):
        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(fn.alert_danger(f"<b>{msg}</b>"))

        return render_template(
            "new_path.html",
            header_title="Insert a new path",
            title="New path",
            action="/new_path",
            form=form,
            default_values=default_values,
        )

    if request.method == "GET":
        form = Path()

        # get id of all transects
        form.transect_id.choices = [("", "")] + [(x, x) for x in fn.all_transect_id()]

        return render_template(
            "new_path.html",
            header_title="Insert a new path",
            title="New path",
            action="/new_path",
            form=form,
            default_values={},
        )

    if request.method == "POST":
        form = Path(request.form)

        # get id of all transects
        form.transect_id.choices = [("", "")] + [(x, x) for x in fn.all_transect_id()]

        if form.validate():
            with fn.conn_alchemy().connect() as con:
                # path_id
                path_id = f'{request.form["transect_id"]}|{request.form["date"][2:].replace("-", "")}'

                # check if path_id already exists

                if (
                    con.execute(text("SELECT path_id FROM paths WHERE path_id = :path_id"), {"path_id": path_id}).mappings().fetchone()
                    is not None
                ):
                    return not_valid(f"The path ID {path_id} already exists")

                # check if 0 < completeness <= 100
                if not (0 < int(request.form["completeness"]) <= 100):
                    return not_valid("Completeness must be an integer like 0 < completeness <= 100")

                sql = text(
                    "INSERT INTO paths (path_id, transect_id, date, sampling_season, completeness, "
                    "observer, institution, notes, created, category) "
                    "VALUES (:path_id, :transect_id, :date, :sampling_season, :completeness, "
                    ":observer, :institution, :notes, NOW(), :category)"
                )
                con.execute(
                    sql,
                    {
                        "path_id": path_id,
                        "transect_id": request.form["transect_id"],
                        "date": request.form["date"],
                        "sampling_season": fn.sampling_season(request.form["date"]),
                        "completeness": request.form["completeness"] if request.form["completeness"] else None,
                        "observer": request.form["observer"],
                        "institution": request.form["institution"],
                        "notes": request.form["notes"],
                        "category": request.form["category"],
                    },
                )

            return redirect("/paths_list")

        else:
            return not_valid("Some values are not set or are wrong. Please check and submit again")


@app.route("/edit_path/<path_id>", methods=("GET", "POST"))
@fn.check_login
def edit_path(path_id):
    with fn.conn_alchemy().connect() as con:
        if request.method == "GET":
            default_values = con.execute(text("SELECT * FROM paths WHERE path_id = :path_id"), {"path_id": path_id}).mappings().fetchone()

            if default_values["category"] is None:
                default_values["category"] = ""

            form = Path(
                transect_id=default_values["transect_id"],
                completeness=default_values["completeness"],
                category=default_values["category"],
            )
            # get id of all transects
            form.transect_id.choices = [("", "")] + [(x, x) for x in fn.all_transect_id()]
            form.notes.data = default_values["notes"]

            return render_template(
                "new_path.html",
                header_title=f"Edit path {path_id}",
                title="Edit path",
                action=f"/edit_path/{path_id}",
                form=form,
                default_values=default_values,
            )

        if request.method == "POST":
            form = Path(request.form)

            # get id of all transects
            form.transect_id.choices = [("", "")] + [(x, x) for x in fn.all_transect_id()]

            if form.validate():
                # path_id
                new_path_id = f'{request.form["transect_id"]}|{request.form["date"][2:].replace("-", "")}'

                # check if path_id already exists
                if new_path_id != path_id:
                    rows = (
                        con.execute(text("SELECT path_id FROM paths WHERE path_id = :path_id"), {"path_id": new_path_id}).mappings().all()
                    )

                    if rows is not None and len(rows):
                        default_values = {}
                        for k in request.form:
                            default_values[k] = request.form[k]

                        flash(
                            Markup(
                                f'<div class="alert alert-danger" role="alert"><b>The path ID <b>{new_path_id}</b> already exists!</b></div>'
                            )
                        )
                        return render_template(
                            "new_path.html",
                            header_title=f"Edit path {path_id}",
                            title="Edit path",
                            action=f"/edit_path/{path_id}",
                            form=form,
                            default_values=default_values,
                        )

                sql = text(
                    "UPDATE paths SET "
                    "path_id = :new_path_id,"
                    "transect_id = :transect_id, "
                    "date = :date, "
                    "sampling_season = :sampling_season, "
                    "completeness = :completeness, "
                    "observer = :observer, "
                    "institution = :institution, "
                    "category = :category, "
                    "notes = :notes "
                    "WHERE path_id = :path_id"
                )

                con.execute(
                    sql,
                    {
                        "new_path_id": new_path_id,
                        "transect_id": request.form["transect_id"],
                        "date": request.form["date"],
                        "sampling_season": fn.sampling_season(request.form["date"]),
                        "completeness": request.form["completeness"] if request.form["completeness"] else None,
                        "observer": request.form["observer"],
                        "institution": request.form["institution"],
                        "category": request.form["category"],
                        "notes": request.form["notes"],
                        "path_id": path_id,
                    },
                )

                return redirect(f"/view_path/{new_path_id}")
            else:
                # default values
                default_values: dict = {}
                for k in request.form:
                    default_values[k] = request.form[k]

                flash(
                    Markup(
                        '<div class="alert alert-danger" role="alert"><b>Some values are not set or are wrong. Please check and submit again</b></div>'
                    )
                )
                return render_template(
                    "new_path.html",
                    header_title=f"Edit path {path_id}",
                    title="Edit path",
                    action=f"/edit_path/{path_id}",
                    form=form,
                    default_values=default_values,
                )


@app.route("/del_path/<path_id>")
@fn.check_login
def del_path(path_id):
    """
    delete a path
    """

    with fn.conn_alchemy().connect() as con:
        con.execute(text("DELETE FROM paths WHERE path_id = :path_id"), {"path_id": path_id})
    return redirect("/paths_list")


@app.route(
    "/load_paths_xlsx",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def load_paths_xlsx():
    """
    import paths from a XLSX file

    """
    if request.method == "GET":
        return render_template("load_paths_xlsx.html", header_title="Import paths from XLSX/ODS")

    if request.method == "POST":
        new_file = request.files["new_file"]

        # check file extension
        if pl.Path(new_file.filename).suffix.upper() not in params["excel_allowed_extensions"]:
            flash(fn.alert_danger("The uploaded file does not have an allowed extension (must be <b>.xlsx</b> or <b>.ods</b>)"))
            return redirect("/load_paths_xlsx")

        try:
            filename = str(uuid.uuid4()) + str(pl.Path(new_file.filename).suffix.upper())
            new_file.save(pl.Path(params["upload_folder"]) / pl.Path(filename))
        except Exception:
            flash(fn.alert_danger("Error with the uploaded file"))
            return redirect("/load_paths_xlsx")

        r, msg, paths_data = paths_import.extract_data_from_paths_xlsx(filename)
        if r:
            flash(Markup(f"File name: <b>{new_file.filename}</b>") + Markup("<hr><br>") + msg)
            return redirect("/load_paths_xlsx")

        # check if path_id already in DB
        with fn.conn_alchemy().connect() as con:
            paths_list = "','".join([paths_data[idx]["path_id"] for idx in paths_data])
            sql = text(f"SELECT path_id FROM paths WHERE path_id IN ('{paths_list}')")
            paths_to_update = [row["path_id"] for row in con.execute(sql).mappings().all()]

            return render_template(
                "confirm_load_paths_xlsx.html",
                n_paths=len(paths_data),
                n_paths_to_update=paths_to_update,
                all_data=paths_data,
                filename=filename,
            )


@app.route("/confirm_load_paths_xlsx/<filename>/<mode>")
@fn.check_login
def confirm_load_paths_xlsx(filename, mode):
    if mode not in ["new", "all"]:
        flash(fn.alert_danger("Error: mode not allowed"))
        return redirect("/load_paths_xlsx")

    r, msg, all_data = paths_import.extract_data_from_paths_xlsx(filename)
    if r:
        flash(Markup(f"File name: <b>{filename}</b>") + Markup("<hr><br>") + msg)
        return redirect("/load_paths_xlsx")

    # check if path_id already in DB
    with fn.conn_alchemy().connect() as con:
        paths_list = "','".join([all_data[idx]["path_id"] for idx in all_data])
        sql = text(f"SELECT path_id FROM paths WHERE path_id IN ('{paths_list}')")
        paths_to_update = [row["path_id"] for row in con.execute(sql).mappings().all()]

        sql = text(
            "UPDATE paths SET "
            "path_id = :path_id, "
            "transect_id = :transect_id,"
            "date = :date,"
            "sampling_season = :sampling_season,"
            "completeness = :completeness,"
            "observer = :operator, "
            "institution = :institution, "
            "notes = :notes "
            "WHERE path_id = :path_id;"
            "INSERT INTO paths ("
            "path_id,"
            "transect_id,"
            "date,"
            "sampling_season,"
            "completeness,"
            "observer,"
            "institution,"
            "notes "
            ") "
            "SELECT "
            ":path_id,"
            ":transect_id,"
            ":date,"
            ":sampling_season,"
            ":completeness, "
            ":operator,"
            ":institution,"
            ":notes "
            "WHERE NOT EXISTS (SELECT 1 FROM paths WHERE path_id = :path_id)"
        )
        count_added = 0
        count_updated = 0
        for idx in all_data:
            data = dict(all_data[idx])

            if mode == "new" and (data["path_id"] in paths_to_update):
                continue
            if data["path_id"] in paths_to_update:
                count_updated += 1
            else:
                count_added += 1

            # print(f"{data=}")

            try:
                con.execute(
                    sql,
                    {
                        "path_id": data["path_id"],
                        "transect_id": data["transect_id"],
                        "date": data["date"],
                        "sampling_season": fn.sampling_season(data["date"]),
                        "completeness": data["completeness"] if data["completeness"] else None,
                        "operator": data["operator"].strip(),
                        "institution": data["institution"].strip(),
                        "notes": data["notes"].strip(),
                    },
                )
            except Exception:
                return "An error occured during the import of paths. Contact the administrator.<br>" + error_info(sys.exc_info())

    msg = f"XLSX/ODS file successfully loaded. {count_added} paths added, {count_updated} paths updated."
    flash(fn.alert_success(msg))

    return redirect("/paths")
