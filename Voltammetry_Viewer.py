import marimo

__generated_with = "0.23.15"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import os
    import numpy as np
    import pandas as pd
    import altair as alt

    return alt, mo, os, pd


@app.cell
def _(mo):
    mo.md("""
    # CV / LSV Overlay Viewer
    Upload one or more Gamry `.dta` files. For each file pick which curve
    (e.g. `CURVE`, `CURVE1`, `CURVE2` …) to show, choose axes, and overlay
    with a legend. Optionally normalize current by area → current density.
    """)
    return


@app.cell
def _(Path, csv, pd):
    def parse_dta_file(filepath, columns=("T", "Vf", "Im"), metadata_keys=("SCANRATE",)):
        """
        Parse a single Gamry .DTA file.

        Returns a DataFrame containing the union of rows from every TABLE block
        that includes all of `columns`, with each requested metadata key added
        as a constant-value column, plus a 'Curve' column noting which TABLE
        block the row came from and a 'SourceFile' column.
        """
        filepath = Path(filepath)
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
 
        reader_rows = list(csv.reader(lines, delimiter="\t"))
 
        metadata = {}
        tables = []  # list of (table_name, DataFrame)
 
        i = 0
        n = len(reader_rows)
        while i < n:
            row = reader_rows[i]
            if not row or row[0] == "":
                i += 1
                continue
 
            key = row[0]
            rtype = row[1] if len(row) > 1 else ""
 
            if rtype == "TABLE":
                table_name = key
                try:
                    nrows = int(row[2])
                except (IndexError, ValueError):
                    nrows = None
 
                # Next row: column names (row[0] is blank, row[1] is usually 'Pt')
                i += 1
                if i >= n:
                    break
                header_names = reader_rows[i][1:]
 
                # Row after that: units (skip, but consume it)
                i += 1
                units_row = reader_rows[i][1:] if i < n else []
 
                # Data rows follow until we've consumed nrows, or hit a blank/non-numeric first cell
                data_rows = []
                i += 1
                while i < n:
                    r = reader_rows[i]
                    if not r or r[0] == "":
                        break
                    # Data rows start with an integer point index
                    try:
                        int(r[0])
                    except ValueError:
                        break
                    data_rows.append(r[1:len(header_names) + 1])
                    i += 1
                    if nrows is not None and len(data_rows) >= nrows:
                        break
 
                # Pad/truncate rows to header length, build DataFrame
                width = len(header_names)
                cleaned = [
                    (r + [""] * (width - len(r)))[:width] if len(r) < width else r[:width]
                    for r in data_rows
                ]
                df = pd.DataFrame(cleaned, columns=header_names)
                for c in df.columns:
                    df[c] = df[c].map(_try_float)
 
                if all(col in df.columns for col in columns):
                    df.insert(0, "Curve", table_name)
                    tables.append((table_name, df))
 
                continue  # i already advanced past this table
 
            else:
                # Ordinary metadata line: KEY  TYPE  VALUE  [extra...]  Description
                if key in metadata_keys and len(row) > 2:
                    metadata[key] = _try_float(row[2])
                i += 1
 
        if not tables:
            raise ValueError(
                f"No TABLE block containing columns {columns} found in {filepath}"
            )
 
        combined = pd.concat([t[1] for t in tables], ignore_index=True)
 
        # Attach metadata as constant columns
        for mkey in metadata_keys:
            combined[mkey] = metadata.get(mkey)
 
        combined["SourceFile"] = filepath.name
 
        # Reorder: Curve, T, Vf, Im, <other metadata>, SourceFile, then anything else
        ordered_cols = ["Curve"] + list(columns) + list(metadata_keys) + ["SourceFile"]
        remaining = [c for c in combined.columns if c not in ordered_cols]
        combined = combined[ordered_cols + remaining]
 
        return combined

    return


@app.cell
def _(pd):
    def _to_numeric(series):
        conv = pd.to_numeric(series, errors="coerce")
        return series if conv.notna().sum() == 0 else conv

    def parse_gamry_dta(text):
        """Generic Gamry .dta parser -> (header dict, {table: {data, units, n}})."""
        lines = text.splitlines()
        header, tables = {}, {}
        n = len(lines)
        i = 0
        while i < n:
            fields = lines[i].split("\t")
            if len(fields) >= 2 and fields[1] == "TABLE":
                name = fields[0]
                try:
                    npts = int(fields[-1])
                except ValueError:
                    npts = None
                labels = lines[i + 1].split("\t")[1:]
                units = lines[i + 2].split("\t")[1:]
                rows, j, count = [], i + 3, 0
                while j < n:
                    row = lines[j].split("\t")
                    if len(row) < 2 or row[0] != "":
                        break
                    try:
                        int(row[1])
                    except ValueError:
                        break
                    rows.append(row[1:])
                    count += 1
                    j += 1
                    if npts is not None and count >= npts:
                        break
                if rows:
                    ncol = len(rows[0])
                    df = pd.DataFrame(rows, columns=labels[:ncol])
                    for c in df.columns:
                        df[c] = _to_numeric(df[c])
                    tables[name] = {"data": df,
                                    "units": dict(zip(labels, units)),
                                    "n": npts}
                i = j
            else:
                if fields and fields[0]:
                    header[fields[0]] = fields[1:]
                i += 1
        return header, tables

    return (parse_gamry_dta,)


@app.cell
def _(mo):
    files = mo.ui.file(filetypes=[".dta", ".DTA", ".txt"],
                       multiple=True, label="Upload one or more .dta files")
    files
    return (files,)


@app.cell
def _(files, mo, parse_gamry_dta):
    mo.stop(not files.value, mo.md("⬆️ **Upload at least one `.dta` file.**"))

    parsed = {}          # {filename: {"header":..., "tables":..., "area":float}}
    for _f in files.value:
        _raw = _f.contents
        _txt = _raw.decode("latin-1") if isinstance(_raw, bytes) else _raw
        _hdr, _tabs = parse_gamry_dta(_txt)
        try:
            _area = float(_hdr.get("AREA", ["", "1.0"])[1])
        except (ValueError, IndexError):
            _area = 1.0
        parsed[_f.name] = {"header": _hdr, "tables": _tabs, "area": _area}

    mo.md(f"**Loaded {len(parsed)} file(s):** "
          + ", ".join(f"`{n}`" for n in parsed))
    return (parsed,)


@app.cell
def _():
    # parsed["20260824_BmPTf2N_S3MS_200K_550Torr_p4V_RCV3.DTA"]["header"]["SCANRATE"][1]
    return


@app.cell
def _(parsed):
    # Determine common numeric columns across all files (for axis dropdowns)
    def _numeric_cols(tabs):
        cols = set()
        for t in tabs.values():
            df = t["data"]
            cols |= {c for c in df.columns if df[c].dtype.kind in "fi"}
        return cols

    common = None
    for info in parsed.values():
        nc = _numeric_cols(info["tables"])
        common = nc if common is None else (common & nc)
    common = sorted(common or [])
    return (common,)


@app.cell
def _(common):
    common
    return


@app.cell
def _(common, mo):
    def _pick(prefs, idx):
        for p in prefs:
            if p in common:
                return p
        return common[min(idx, len(common) - 1)] if common else None

    x_axis = mo.ui.dropdown(options=common, value=_pick(["Vf"], 0),
                            label="X axis")
    y_axis = mo.ui.dropdown(options=common, value=_pick(["Im"], 1),
                            label="Y axis")
    normalize = mo.ui.switch(value=False, label="Normalize Y by area (→ density)")
    mo.hstack([x_axis, y_axis, normalize])
    return normalize, x_axis, y_axis


@app.cell
def _(mo, parsed):
    # For each file, pick which curve/cycle to display (skip OCVCURVE by default)
    curve_selectors = {}
    for _name, _info in parsed.items():
        _tabs = list(_info["tables"])
        _default = next((t for t in _tabs if t != "OCVCURVE"),
                        _tabs[0] if _tabs else None)
        curve_selectors[_name] = mo.ui.dropdown(
            options=_tabs, value=_default, label=_name)

    mo.vstack([mo.md("### Choose curve (cycle) per file")]
              + list(curve_selectors.values()))
    return (curve_selectors,)


@app.cell
def _(mo, parsed):
    # Optional custom legend label per file (defaults to filename)
    label_inputs = {}
    for _name in parsed:
        label_inputs[_name] = mo.ui.text(value=_name, label=_name,
                                         full_width=True)
    mo.vstack([mo.md("### Legend labels (optional)")]
              + list(label_inputs.values()))
    return (label_inputs,)


@app.cell
def _(
    curve_selectors,
    label_inputs,
    mo,
    normalize,
    parsed,
    pd,
    x_axis,
    y_axis,
):
    mo.stop(not (x_axis.value and y_axis.value),
            mo.md("*Select X and Y axes.*"))

    frames = []
    for _name, _info in parsed.items():
        _curve = curve_selectors[_name].value
        if _curve is None or _curve not in _info["tables"]:
            continue
        _df = _info["tables"][_curve]["data"].copy()
        if x_axis.value not in _df.columns or y_axis.value not in _df.columns:
            continue
        _sub = pd.DataFrame({
            "x": _df[x_axis.value].astype(float),
            "y": _df[y_axis.value].astype(float),
        })
        if normalize.value:
            _sub["y"] = _sub["y"] / _info["area"]
        _sub["series"] = label_inputs[_name].value or _name
        _sub["curve"] = _curve
        _sub["order"] = range(len(_sub))   # preserve sweep order for line drawing
        _sub["scanrate"] = float(_info['header']['SCANRATE'][1])
        _sub["date"] = _sub["series"].str.extract(r"(20260\d*)_")
        frames.append(_sub)

    plotdf = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["x", "y", "series", "curve", "order", "scanrate", "date"])
    return (plotdf,)


@app.cell
def _(alt, mo, normalize, plotdf, x_axis, y_axis):
    mo.stop(plotdf.empty, mo.md("*Nothing to plot yet.*"))

    _ylab = (f"{y_axis.value} / area" if normalize.value else y_axis.value)
    _zoom = alt.selection_interval(bind="scales")

    chart = alt.Chart(plotdf).mark_line().encode(
        x=alt.X("x:Q", title=x_axis.value, scale=alt.Scale(zero=False, nice=False)),
        y=alt.Y("y:Q", title=_ylab, scale=alt.Scale(zero=False)),
        color=alt.Color("scanrate:Q", title="scanrate",
                        legend=alt.Legend(orient="right")),
        detail = "series:N",
        size = "date:N",
        order=alt.Order("order:Q"),          # draw in sweep order (CV loops close)
        tooltip=["series:N", "curve:N", "x:Q", "y:Q"],
    ).add_params(_zoom).properties(width=680, height=440)


    plot = mo.ui.altair_chart(chart, chart_selection=False,
                              legend_selection=True)
    plot
    return (chart,)


@app.cell
def _(mo):
    mo.md("""
    ---
    ### Save high-resolution PNG (300 ppi)
    """)
    return


@app.cell
def _(mo):
    filename = mo.ui.text(value="overlay.png", label="Filename", full_width=True)
    ppi = mo.ui.number(value=300, start=72, stop=1200, step=1, label="ppi")
    save_button = mo.ui.run_button(label="💾 Save PNG to disk")
    mo.vstack([filename, ppi, save_button])
    return filename, ppi, save_button


@app.cell
def _(chart, mo, ppi):
    import vl_convert as vlc
    scale = ppi.value / 72.0
    png_bytes = vlc.vegalite_to_png(chart.to_json(), scale=scale)
    download = mo.download(data=png_bytes, filename="overlay.png",
                           mimetype="image/png",
                           label=f"⬇️ Download PNG ({ppi.value} ppi)")
    mo.md(f"PNG rendered ({len(png_bytes)//1024} KB).\n\n{download}")
    return (png_bytes,)


@app.cell
def _(filename, mo, os, png_bytes, ppi, save_button):
    mo.stop(not save_button.value,
            mo.md("*Adjust the overlay, then click **💾 Save PNG to disk**.*"))
    fname = filename.value.strip() or "overlay.png"
    if not fname.lower().endswith(".png"):
        fname += ".png"
    path = os.path.abspath(fname)
    try:
        with open(path, "wb") as f:
            f.write(png_bytes)
        result = mo.md(f"✅ Saved **{ppi.value} ppi** PNG → `{path}`")
    except Exception as e:
        result = mo.md(f"❌ Save failed: `{e}`")
    result
    return


if __name__ == "__main__":
    app.run()
