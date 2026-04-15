"""
export scats in XLSX format
"""

from io import BytesIO
from tempfile import NamedTemporaryFile

import pandas as pd
from openpyxl import Workbook


def export_scats(scats):
    wb = Workbook()

    ws1 = wb.active
    ws1.title = "Scats"

    header: list = [
        "Scat ID",
        "Date",
        "Sampling season",
        "Sampling type",
        "path ID",
        "Snowtrack ID",
        "WA code",
        "Genotype ID",
        "location",
        "municipality",
        "province",
        "region",
        "Deposition",
        "Matrix",
        "Collected scat",
        "Scalp category",
        "Genetic sample",
        "Coordinate east",
        "Coordinate north",
        "Zone",
        "Operator",
        "Institution",
        "Notes",
    ]

    ws1.append(header)

    for row in scats:
        out = []
        out.append(row["scat_id"])
        out.append(row["date"])
        out.append(row["sampling_season"])
        out.append(row["sampling_type"])
        out.append(row["path_id"] if row["path_id"] is not None else "")
        out.append(row["snowtrack_id"] if row["snowtrack_id"] is not None else "")
        out.append(row["wa_code"] if row["wa_code"] is not None else "")
        out.append(row["genotype_id2"])
        out.append(row["location"] if row["location"] is not None else "")
        out.append(row["municipality"] if row["municipality"] is not None else "")
        out.append(row["province"] if row["province"] is not None else "")
        out.append(row["region"] if row["region"] is not None else "")
        out.append(row["deposition"])
        out.append(row["matrix"])
        out.append(row["collected_scat"])
        out.append(row["scalp_category"])

        """
        scalp_cat = row["scalp_category"]
        if row["mtdna"] is not None and "WOLF" in row["mtdna"].upper():
            scalp_cat += " (from mtDNA: C1)"
        out.append(scalp_cat)
        """

        out.append(row["genetic_sample"])
        out.append(row["coord_east"])
        out.append(row["coord_north"])
        out.append(row["coord_zone"])
        out.append(row["observer"])
        out.append(row["institution"])
        out.append(row["notes"])

        ws1.append(out)

    with NamedTemporaryFile() as tmp:
        wb.save(tmp.name)
        tmp.seek(0)
        stream = tmp.read()

        return stream


def export_scats_pandas(scats, file_format="xlsx"):
    file_format = file_format.lower()

    columns = [
        ("scat_id", "Scat ID"),
        ("date", "Date"),
        ("sampling_season", "Sampling season"),
        ("sampling_type", "Sampling type"),
        ("path_id", "path ID"),
        ("snowtrack_id", "Snowtrack ID"),
        ("wa_code", "WA code"),
        ("genotype_id2", "Genotype ID"),
        ("location", "location"),
        ("municipality", "municipality"),
        ("province", "province"),
        ("region", "region"),
        ("deposition", "Deposition"),
        ("matrix", "Matrix"),
        ("collected_scat", "Collected scat"),
        ("scalp_category", "Scalp category"),
        ("genetic_sample", "Genetic sample"),
        ("coord_east", "Coordinate east"),
        ("coord_north", "Coordinate north"),
        ("coord_zone", "Zone"),
        ("observer", "Operator"),
        ("institution", "Institution"),
        ("notes", "Notes"),
    ]

    rows = []
    for row in scats:
        rows.append(
            {
                label: ("" if row.get(key) is None else row.get(key))
                for key, label in columns
            }
        )

    df = pd.DataFrame(rows, columns=[label for _, label in columns])

    output = BytesIO()

    if file_format == "xlsx":
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Scats")

    elif file_format == "tsv":
        df.to_csv(output, index=False, sep="\t", encoding="utf-8")

    elif file_format == "ods":
        with pd.ExcelWriter(output, engine="odf") as writer:
            df.to_excel(writer, index=False, sheet_name="Scats")

    else:
        raise ValueError("Unsupported format. Use 'xlsx', 'tsv', or 'ods'.")

    output.seek(0)
    return output.read()
