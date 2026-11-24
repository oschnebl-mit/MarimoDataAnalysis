import marimo

__generated_with = "0.25.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import os
    import numpy as np
    import pandas as pd
    import altair as alt

    return alt, mo, np, os, pd


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # CV / LSV Overlay Viewer
    Upload one or more Gamry `.dta` files. For each file pick which curve
    (e.g. `CURVE`, `CURVE1`, `CURVE2` …) to show, choose axes, and overlay
    with a legend. Optionally normalize current by area → current density.
    """)
    return


@app.cell
def _():
    data_path = r'/Users/ods/MIT Dropbox/Olivia Schneble/jaramillogroupshared/Data'
    # data_path = r'\Users\oschn\Dropbox (MIT)\jaramillogroupshared\Data'
    return (data_path,)


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
def _(StringIO, os, pd):
    def read_gamry_dta_alt(path):
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        # Find where the data block begins
        start = None
        for i, line in enumerate(lines):
            if line.strip().startswith("ZCURVE"):
                start = i
                break
        if start is None:
            raise ValueError("ZCURVE marker not found")

        # Keep everything after the ZCURVE line
        data_lines = lines[start+1:]

        # Remove unit row(s) and any trailing error/abort lines
        cleaned = []
        for ln in data_lines:
            s = ln.strip()
            if not s:
                continue
            if s.startswith("#"):          # units row
                continue
            if "Measurement aborted" in s:
                continue
            cleaned.append(ln)

        # Read as strings first to avoid dtype mixing
        df = pd.read_csv(
            StringIO("".join(cleaned)),
            sep="\t",
            header=0,          # first remaining line is the column header
            dtype=str,
            engine="python"
        )

        # Optional: convert numeric columns
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df['Measurement'] = os.path.basename(path)
        return df
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
def _(data_path, mo):

    browser = mo.ui.file_browser(initial_path=data_path,multiple=True)

    browser
    return (browser,)


@app.cell
def _(browser, files, mo, parse_gamry_dta):
    from pathlib import Path

    def _iter_sources():
        """Yield (name, raw_contents) from both the uploader and the file browser."""
        # 1) Uploaded files: contents are already in memory
        for f in (files.value or []):
            yield f.name, f.contents

        # 2) File-browser selections: read from disk
        for info in (browser.value or []):
            p = Path(info.path)
            if info.is_directory:
                # If a folder is selected, load every .DTA file inside it
                for child in sorted(p.glob("*.[dD][tT][aA]")):
                    yield child.name, child.read_bytes()
            else:
                yield info.name, p.read_bytes()


    parsed = {}          # {filename: {"header":..., "tables":..., "area":float}}
    for _name, _raw in _iter_sources():
        _txt = _raw.decode("latin-1") if isinstance(_raw, bytes) else _raw
        _hdr, _tabs = parse_gamry_dta(_txt)
        try:
            _area = float(_hdr.get("AREA", ["", "1.0"])[1])
        except (ValueError, IndexError):
            _area = 1.0
        if _name in parsed:                      # same filename from both sources / folders
            _name = f"{_name} ({len(parsed)})"
        parsed[_name] = {"header": _hdr, "tables": _tabs, "area": _area}

    mo.md(f"**Loaded {len(parsed)} file(s):** "
          + (", ".join(f"`{n}`" for n in parsed) if parsed else "_none selected_"))
    return Path, parsed


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
    normalize = mo.ui.switch(value=False, label="Normalize I by sqrt(Scanrate)")
    iRcorrect = mo.ui.switch(value=False, label="Apply iR correction")
    mo.hstack([x_axis, y_axis, normalize, iRcorrect])
    return iRcorrect, normalize, x_axis, y_axis


@app.cell
def _(alt, mo, normalize, plotdf, x_axis, y_axis):
    mo.stop(plotdf.empty, mo.md("*Nothing to plot yet.*"))

    _ylab = (f"{y_axis.value} / sqrt(scanrate)" if normalize.value else y_axis.value)
    _zoom = alt.selection_interval(bind="scales")

    chart_pts = alt.Chart(plotdf).mark_circle(fillOpacity=0.5,strokeOpacity=0.1).encode(
        x=alt.X("x:Q", title=x_axis.value, scale=alt.Scale(zero=False, nice=False)),
        y=alt.Y("y:Q", title=_ylab, scale=alt.Scale(zero=False)),
        detail = 'series:N',
        color = 'date:N',
        # size = alt.Size('date:N', title = 'Expt. Date'),
        # color=alt.Color("scanrate:Q", title="Scan Rate (mV/s)"),
        order=alt.Order("order:Q"),          # draw in sweep order (CV loops close)
        tooltip=["series:N", "curve:N", "x:Q", "y:Q"]
    ).add_params(_zoom).properties(width=680, height=440)

    chart_line = alt.Chart(plotdf).mark_line(strokeOpacity=0.5).encode(
        x=alt.X("x:Q", title=x_axis.value, scale=alt.Scale(zero=False, nice=False)),
        y=alt.Y("y:Q", title=_ylab, scale=alt.Scale(zero=False)),
        detail = 'series:N',
        color = 'date:N',
        order = alt.Order("order:Q")
    )
    plot = mo.ui.altair_chart((chart_line+chart_pts), chart_selection=False,
                              legend_selection=True)
    plot.interactive()
    return


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
def _():
    # Optional custom legend label per file (defaults to filename)
    # label_inputs = {}
    # for _name in parsed:
    #     label_inputs[_name] = mo.ui.text(value=_name, label=_name,
    #                                      full_width=True)
    # mo.vstack([mo.md("### Legend labels (optional)")]
    #           + list(label_inputs.values()))
    return


@app.cell
def _(mo, parsed):
    Ru_inputs = {}
    for _name in parsed:
        Ru_inputs[_name] = mo.ui.number(value = 0,label=_name,full_width=True)

    mo.vstack([mo.md("## Add Ru value for iR compensation")]+list(Ru_inputs.values()))
    return (Ru_inputs,)


@app.cell
def _(
    Ru_inputs,
    curve_selectors,
    iRcorrect,
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
        # _sub["series"] = label_inputs[_name].value or _name
        _sub["series"] = _name
        _sub["curve"] = _curve
        _sub["order"] = range(len(_sub))   # preserve sweep order for line drawing
        _sub["scanrate"] = float(_info['header']['SCANRATE'][1])
        _sub["date"] = _info['header']['DATE'][1]

        if normalize.value:
            _sub["y"] = _sub["y"] / _info["area"]
            # _sub["y_norm"] = _sub["y"]/np.sqrt(_sub["scanrate"])
        if iRcorrect.value:
            _sub["x"] = _sub["x"] - _sub["y"]*Ru_inputs[_name].value
        frames.append(_sub)

        plotdf = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["x", "y", "series", "curve", "order","scanrate"])
    return (plotdf,)


@app.cell
def _(mo):
    mo.md("""
    ---
    ### Potential at target currents (grouped bar chart)
    Enter target currents (mA) to compare the potential reached on the
    **forward sweep** (earliest matching point, by Pt index) across
    experiments.
    """)
    return


@app.cell
def _(mo):
    target_currents = mo.ui.text(value="0.5, 1, 1.5, 2",
                                 label="Target currents (mA, comma-separated)",
                                 full_width=True)
    current_units = mo.ui.dropdown(options=["A", "mA", "µA"], value="A",
                                   label="Native current units (as recorded)")
    use_abs_current = mo.ui.switch(value=True, label="Match on |current| (ignore sign)")
    mo.hstack([target_currents, current_units, use_abs_current])
    return current_units, target_currents, use_abs_current


@app.cell
def _(current_units, mo, pd, plotdf, target_currents, use_abs_current):
    mo.stop(plotdf.empty, mo.md("*Load data and select curves first.*"))

    def _potential_at_current(df_grp, target):
        """First crossing of `target`, scanning from the lowest Pt (sweep order),
        i.e. the forward sweep rather than the return sweep."""
        _sorted = df_grp.sort_values("order")
        xs = _sorted["x"].tolist()
        ys = _sorted["y"].tolist()
        if use_abs_current.value:
            ys = [abs(v) for v in ys]
        for i in range(len(ys) - 1):
            y0, y1 = ys[i], ys[i + 1]
            if y0 == target:
                return xs[i]
            if (y0 < target) != (y1 < target):
                frac = (target - y0) / (y1 - y0)
                return xs[i] + frac * (xs[i + 1] - xs[i])
        if ys and ys[-1] == target:
            return xs[-1]
        return float("nan")

    _unit_to_mA = {"A": 1000.0, "mA": 1.0, "µA": 0.001}
    _scale = _unit_to_mA[current_units.value]
    try:
        _targets_mA = [float(v) for v in target_currents.value.replace(",", " ").split()]
    except ValueError:
        _targets_mA = []

    _rows = []
    for _series, _grp in plotdf.groupby("series"):
        for _t_mA in _targets_mA:
            _target_native = _t_mA / _scale
            _pot = _potential_at_current(_grp, _target_native)
            _rows.append({"series": _series, "target_mA": _t_mA, "potential": _pot})

    bar_df = pd.DataFrame(_rows, columns=["series", "target_mA", "potential"])
    return (bar_df,)


@app.cell
def _(alt, bar_df, mo, x_axis):
    mo.stop(bar_df.empty, mo.md("*No target currents to plot yet.*"))

    bar_chart_spec = alt.Chart(bar_df).mark_bar().encode(
        x=alt.X("target_mA:O", title="Target current (mA)"),
        xOffset=alt.XOffset("series:N"),
        y=alt.Y("potential:Q", title=x_axis.value, scale=alt.Scale(zero=False)),
        color=alt.Color("series:N", title="Experiment"),
        tooltip=["series:N", "target_mA:Q", "potential:Q"],
    ).properties(width=600, height=400)

    bar_chart = mo.ui.altair_chart(bar_chart_spec)
    bar_chart
    return


@app.cell
def _(mo):
    mo.md("""
    ---
    ### Optional: Electrochemically active surface area (ECSA) from CV
    Estimates ECSA from the scan-rate dependence of the non-faradaic
    double-layer charging current. Load CVs of the **same electrode** at
    several scan rates, pick a potential window with no faradaic current,
    and fit `ΔI/2 = Cdl · (scan rate)`. Given a specific capacitance `Cs`,
    `ECSA = Cdl / Cs`.
    """)
    return


@app.cell
def _(mo):
    ecsa_enabled = mo.ui.switch(value=False, label="Enable ECSA extraction")
    ecsa_enabled
    return (ecsa_enabled,)


@app.cell
def _(ecsa_enabled, mo, parsed):
    mo.stop(not ecsa_enabled.value,
            mo.md("*Toggle on to extract ECSA from the loaded CVs.*"))

    ecsa_files = mo.ui.multiselect(
        options=list(parsed), value=list(parsed),
        label="Files to include (same electrode, different scan rates)")
    ecsa_potential = mo.ui.number(value=0.0, step=0.01,
                                  label="Non-faradaic potential (V)")
    ecsa_window = mo.ui.number(value=0.02, start=0.0, step=0.005,
                               label="± window (V) to average current over")
    ecsa_cs = mo.ui.number(value=40.0, start=1.0, step=1.0,
                           label="Specific capacitance Cs (µF/cm²)")
    mo.vstack([
        ecsa_files,
        mo.hstack([ecsa_potential, ecsa_window, ecsa_cs]),
    ])
    return ecsa_cs, ecsa_files, ecsa_potential, ecsa_window


@app.cell
def _(
    current_units,
    curve_selectors,
    ecsa_files,
    ecsa_potential,
    ecsa_window,
    np,
    parsed,
    pd,
    x_axis,
    y_axis,
):
    _unit_to_A = {"A": 1.0, "mA": 1e-3, "µA": 1e-6}
    _scale_A = _unit_to_A[current_units.value]
    _lo, _hi = ecsa_potential.value - ecsa_window.value, ecsa_potential.value + ecsa_window.value

    _rows = []
    for _name in ecsa_files.value:
        _info = parsed.get(_name)
        if _info is None:
            continue
        _curve = curve_selectors[_name].value
        if _curve is None or _curve not in _info["tables"]:
            continue
        _df = _info["tables"][_curve]["data"]
        if x_axis.value not in _df.columns or y_axis.value not in _df.columns:
            continue

        _sub = pd.DataFrame({
            "x": _df[x_axis.value].astype(float),
            "y": _df[y_axis.value].astype(float),
        })
        # Classify each point by sweep direction (sign of dV) so we can
        # separate the forward- and return-sweep charging currents.
        _dx = _sub["x"].diff()
        _direction = np.sign(_dx.where(_dx != 0)).bfill().ffill()
        _sub["direction"] = _direction

        _near = _sub[(_sub["x"] >= _lo) & (_sub["x"] <= _hi)]
        _i_pos = _near.loc[_near["direction"] > 0, "y"].mean()
        _i_neg = _near.loc[_near["direction"] < 0, "y"].mean()
        if pd.isna(_i_pos) or pd.isna(_i_neg):
            continue

        try:
            _scanrate = float(_info["header"]["SCANRATE"][1])
        except (KeyError, ValueError, IndexError):
            continue

        _cdl_current_A = abs(_i_pos - _i_neg) / 2.0 * _scale_A
        _rows.append({
            "series": _name,
            "scanrate": _scanrate,
            "cdl_current_A": _cdl_current_A,
            "area_cm2": _info["area"],
        })

    ecsa_df = pd.DataFrame(
        _rows, columns=["series", "scanrate", "cdl_current_A", "area_cm2"])
    return (ecsa_df,)


@app.cell
def _(ecsa_cs, ecsa_df, mo, np):
    mo.stop(ecsa_df["scanrate"].nunique() < 2,
            mo.md("*Need at least two different scan rates (with current "
                  "in the chosen potential window) to fit Cdl.*"))

    _slope, _intercept = np.polyfit(ecsa_df["scanrate"], ecsa_df["cdl_current_A"], 1)
    cdl_F = _slope
    geometric_area_cm2 = ecsa_df["area_cm2"].mean()
    ecsa_cm2 = cdl_F / (ecsa_cs.value * 1e-6)
    roughness_factor = ecsa_cm2 / geometric_area_cm2 if geometric_area_cm2 else float("nan")

    mo.md(f"""
    **Cdl** = {cdl_F * 1e6:.3g} µF (slope of ΔI/2 vs. scan rate, intercept {_intercept * 1e6:.3g} µA)

    **ECSA** = Cdl / Cs = {ecsa_cm2:.3g} cm²

    **Roughness factor** = ECSA / geometric area ({geometric_area_cm2:.3g} cm²) = {roughness_factor:.3g}
    """)
    return (cdl_F,)


@app.cell
def _(alt, cdl_F, ecsa_df, mo, np, pd):
    _fit_x = np.linspace(0, ecsa_df["scanrate"].max() * 1.05, 50)
    _fit_y_uA = (cdl_F * _fit_x) * 1e6
    _fit_df = pd.DataFrame({"scanrate": _fit_x, "cdl_current_uA": _fit_y_uA})

    _points_df = ecsa_df.assign(cdl_current_uA=ecsa_df["cdl_current_A"] * 1e6)

    _chart_points = alt.Chart(_points_df).mark_point(filled=True, size=80).encode(
        x=alt.X("scanrate:Q", title="Scan rate (V/s)"),
        y=alt.Y("cdl_current_uA:Q", title="ΔI/2 (µA)"),
        color=alt.Color("series:N", title="File"),
        tooltip=["series:N", "scanrate:Q", "cdl_current_uA:Q"],
    )
    _chart_fit = alt.Chart(_fit_df).mark_line(strokeDash=[4, 4], color="gray").encode(
        x="scanrate:Q", y="cdl_current_uA:Q",
    )

    ecsa_chart = mo.ui.altair_chart((_chart_points + _chart_fit).properties(width=600, height=400))
    ecsa_chart
    return


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
