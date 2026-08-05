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

    return alt, mo, np, os, pd


@app.cell
def _(mo):
    mo.md("""
    # Gamry Tafel Analysis
    Upload a potentiodynamic-polarization `.dta`. Pick the anodic & cathodic
    linear windows with the sliders; the notebook fits each branch and reports
    Tafel slopes, E_corr, i_corr, and exchange current density j₀.
    """)
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
            if len(fields) >= 3 and fields[1] == "TABLE":
                name = fields[0]
                try:
                    npts = int(fields[2])
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
    file_upload = mo.ui.file(filetypes=[".dta", ".DTA", ".txt"],
                             label="Upload Gamry polarization .dta")
    file_upload
    return (file_upload,)


@app.cell
def _(file_upload, mo, parse_gamry_dta):
    mo.stop(not file_upload.value, mo.md("⬆️ **Upload a `.dta` file to begin.**"))
    _raw = file_upload.value[0].contents
    text = _raw.decode("latin-1") if isinstance(_raw, bytes) else _raw
    header, tables = parse_gamry_dta(text)
    technique = header.get("TAG", ["?"])[0]

    # Area from header if present (QUANT: [type, value, label])
    try:
        area_hdr = float(header.get("AREA", ["", "1.0"])[1])
    except (ValueError, IndexError):
        area_hdr = 1.0

    mo.md(f"**Technique (TAG):** `{technique}`  \n"
          f"**Tables:** {', '.join(tables) or 'none'}  \n"
          f"**Header area:** {area_hdr} cm²")
    return area_hdr, tables


@app.cell
def _(area_hdr, mo, tables):
    _names = list(tables)
    _default = "CURVE" if "CURVE" in _names else (
        next((n for n in _names if n != "OCVCURVE"), _names[0]))
    table_select = mo.ui.dropdown(options=_names, value=_default,
                                  label="Data table")
    area = mo.ui.number(value=area_hdr, start=1e-6, stop=1e6, step=0.01,
                        label="Electrode area (cm²)")
    mo.hstack([table_select, area])
    return area, table_select


@app.cell
def _(mo, table_select, tables):
    df0 = tables[table_select.value]["data"]
    units = tables[table_select.value]["units"]
    ncols = [c for c in df0.columns if df0[c].dtype.kind in "fi"]

    def _pick(prefs, idx):
        for p in prefs:
            if p in ncols:
                return p
        return ncols[min(idx, len(ncols) - 1)]

    e_col = mo.ui.dropdown(options=ncols, value=_pick(["Vf"], 2),
                           label="Potential column")
    i_col = mo.ui.dropdown(options=ncols, value=_pick(["Im"], 3),
                           label="Current column")
    mo.hstack([e_col, i_col])
    return df0, e_col, i_col


@app.cell
def _(mo):
    ir_source = mo.ui.radio(
        options=["None", "Manual value", "From EIS file"],
        value="None", label="iR correction source")
    ir_source
    return (ir_source,)


@app.cell
def _(ir_source, mo):
    ru_manual = mo.ui.number(value=0.0, start=0.0, stop=1e6, step=0.1,
                             label="Rᵤ (ohm)")
    eis_upload = mo.ui.file(filetypes=[".dta", ".DTA", ".txt"],
                            label="Upload Gamry EIS .dta")
    if ir_source.value == "Manual value":
        _widget = ru_manual
    elif ir_source.value == "From EIS file":
        _widget = eis_upload
    else:
        _widget = mo.md("*No iR correction applied.*")
    _widget
    return eis_upload, ru_manual


@app.cell
def _(alt, eis_upload, ir_source, mo, parse_gamry_dta, pd, ru_manual):
    Ru = 0.0
    _view = mo.md("")

    if ir_source.value == "Manual value":
        Ru = float(ru_manual.value)
        _view = mo.md(f"**Rᵤ = {Ru:.3f} Ω** (manual)")

    elif ir_source.value == "From EIS file" and eis_upload.value:
        _raw = eis_upload.value[0].contents
        _txt = _raw.decode("latin-1") if isinstance(_raw, bytes) else _raw
        _, _tabs = parse_gamry_dta(_txt)
        # Gamry EIS table is usually ZCURVE
        _name = "ZCURVE" if "ZCURVE" in _tabs else next(iter(_tabs))
        _z = _tabs[_name]["data"]

        def _col(df, prefs):
            for p in prefs:
                if p in df.columns:
                    return p
            return None

        fcol = _col(_z, ["Freq", "Frequency"])
        zr = _col(_z, ["Zreal", "Zre", "Z'"])
        zi = _col(_z, ["Zimag", "Zim", "Z''"])

        if zr and zi:
            zdf = _z[[c for c in [fcol, zr, zi] if c]].copy()
            zdf.columns = (["Freq"] if fcol else []) + ["Zre", "Zim"]
            # Rᵤ = high-frequency real-axis intercept:
            # among the highest-frequency points, take Zre where |Zim| is smallest
            if fcol:
                hf = zdf.sort_values("Freq", ascending=False).head(
                    max(3, len(zdf) // 5))
            else:
                hf = zdf
            Ru = float(hf.loc[hf["Zim"].abs().idxmin(), "Zre"])

            nyq = alt.Chart(zdf).mark_point(filled=True, opacity=0.6).encode(
                x=alt.X("Zre:Q", title="Z′ (Ω)"),
                y=alt.Y("Zim:Q", title="Z″ (Ω)"),
                tooltip=["Freq:Q", "Zre:Q", "Zim:Q"] if fcol else ["Zre:Q", "Zim:Q"],
            )
            marker = alt.Chart(pd.DataFrame({"Zre": [Ru], "Zim": [0.0]})).mark_point(
                size=140, color="red", shape="cross").encode(x="Zre:Q", y="Zim:Q")
            nyq_plot = mo.ui.altair_chart(
                (nyq + marker).properties(width=400, height=300,
                    title="Nyquist — red cross = estimated Rᵤ"),
                chart_selection=False, legend_selection=False)
            _view = mo.vstack([mo.md(
                f"**Rᵤ = {Ru:.3f} Ω** (high-frequency intercept of `{_name}`).  \n"
                f"*Check the cross sits at the left/high-freq intercept; "
                f"if not, override with the manual option.*"), nyq_plot])
        else:
            _view = mo.md("Could not find Zreal/Zimag columns in EIS file.")
    _view
    return (Ru,)


@app.cell
def _(Ru, area, df0, e_col, i_col, np, pd):
    # Build the Tafel dataframe: current density and log10|j|
    # Ru = ru_manual.value
    E_raw = df0[e_col.value].to_numpy(dtype=float)
    I = df0[i_col.value].to_numpy(dtype=float)
    E = E_raw - I * Ru                       # <-- iR correction: E_corr = E - I·Rᵤ
    j = I / area.value
    with np.errstate(divide="ignore"):
        logj = np.log10(np.abs(j))
    tdf = pd.DataFrame({"E": E, "E_raw": E_raw, "j": j,
                        "absj": np.abs(j), "logj": logj})
    tdf = tdf[np.isfinite(tdf["logj"])].reset_index(drop=True)

    return (tdf,)


@app.cell
def _(alt, mo, tdf):
    _zoom = alt.selection_interval(bind="scales")
    raw_chart = alt.Chart(tdf).mark_line(point=alt.OverlayMarkDef(
        size=15, filled=True, opacity=0.6)).encode(
        x=alt.X("E:Q", title="E (V vs. Ref.)", scale=alt.Scale(zero=False)),
        y=alt.Y("j:Q", title="j (A/cm²)", scale=alt.Scale(zero=False)),
        # color by sign so cathodic (–) vs anodic (+) current is obvious
        color=alt.condition("datum.j < 0",
                            alt.value("#1f77b4"),   # cathodic, blue
                            alt.value("#d62728")),   # anodic, red
        tooltip=["E:Q", "j:Q", "logj:Q"],
    ).add_params(_zoom).properties(width=650, height=350,
                                   title="Raw: current density vs applied potential")
    raw_plot = mo.ui.altair_chart(raw_chart, chart_selection=False,
                                  legend_selection=False)
    mo.vstack([mo.md("### Raw data (pick your branches from here)"), raw_plot])
    return


@app.cell
def _(mo, tdf):
    emin, emax = float(tdf["E"].min()), float(tdf["E"].max())
    _step = (emax - emin) / 200 or 1e-4
    # Sensible starting guesses: cathodic = lower half, anodic = upper half
    _mid = (emin + emax) / 2
    cath_range = mo.ui.range_slider(
        start=emin, stop=emax, step=_step,
        value=[emin, _mid - _step], label="Cathodic branch E-window (V)",
        full_width=True, show_value=True)
    anod_range = mo.ui.range_slider(
        start=emin, stop=emax, step=_step,
        value=[_mid + _step, emax], label="Anodic branch E-window (V)",
        full_width=True, show_value=True)
    mo.vstack([cath_range, anod_range])
    return anod_range, cath_range


@app.cell
def _(anod_range, cath_range, np, tdf):
    def fit_branch(lo, hi):
        m = (tdf["E"] >= lo) & (tdf["E"] <= hi)
        sub = tdf[m]
        if len(sub) < 2:
            return None
        # Fit E = slope * logj + intercept  -> slope in V/decade
        slope, intercept = np.polyfit(sub["logj"], sub["E"], 1)
        return {"slope": slope, "intercept": intercept,
                "n": len(sub), "logj": sub["logj"].to_numpy(),
                "E": sub["E"].to_numpy()}

    cfit = fit_branch(*cath_range.value)
    afit = fit_branch(*anod_range.value)

    corr = None
    if cfit and afit and cfit["slope"] != afit["slope"]:
        # Intersection of the two Tafel lines
        logj_corr = (afit["intercept"] - cfit["intercept"]) / \
                    (cfit["slope"] - afit["slope"])
        e_corr = cfit["slope"] * logj_corr + cfit["intercept"]
        i_corr = 10 ** logj_corr
        corr = {"logj": logj_corr, "E": e_corr, "icorr": i_corr}
    return afit, cfit, corr


@app.cell
def _(afit, cfit, corr, mo):
    def _mv(s):  # V/decade -> mV/decade
        return None if s is None else s * 1000.0

    rows = []
    if cfit:
        rows.append(f"| Cathodic | {_mv(cfit['slope']):.1f} mV/dec | {cfit['n']} pts |")
    if afit:
        rows.append(f"| Anodic | {_mv(afit['slope']):.1f} mV/dec | {afit['n']} pts |")
    table = ("| Branch | Tafel slope | Fit points |\n|---|---|---|\n"
             + "\n".join(rows)) if rows else "*Adjust the windows to fit.*"

    if corr:
        summary = (f"\n\n**E_corr = {corr['E']*1000:.1f} mV**  \n"
                   f"**i_corr = {corr['icorr']:.3e} A/cm²**  \n"
                   f"(exchange current density j₀ ≈ i_corr for a symmetric system)")
    else:
        summary = ""
    mo.md("### Fit results\n" + table + summary)
    return


@app.cell
def _(afit, alt, cfit, corr, mo, np, pd, tdf):
    zoom = alt.selection_interval(bind="scales")

    pts = alt.Chart(tdf).mark_point(size=25, filled=True,
                                    opacity=0.5, color="#555").encode(
        x=alt.X("logj:Q", title="log₁₀ |j|  (j in A/cm²)"),
        y=alt.Y("E:Q", title="E (V vs. Ref.)", scale=alt.Scale(zero=False)),
        tooltip=["E:Q", "absj:Q", "logj:Q"],
    ).add_params(zoom)

    layers = [pts]

    def branch_line(fit, color):
        if not fit:
            return None
        xs = np.array([fit["logj"].min(), fit["logj"].max()])
        ys = fit["slope"] * xs + fit["intercept"]
        d = pd.DataFrame({"logj": xs, "E": ys})
        return alt.Chart(d).mark_line(color=color, strokeWidth=2).encode(
            x="logj:Q", y="E:Q")

    cl = branch_line(cfit, "#1f77b4")
    al = branch_line(afit, "#d62728")
    if cl is not None:
        layers.append(cl)
    if al is not None:
        layers.append(al)

    if corr:
        cd = pd.DataFrame({"logj": [corr["logj"]], "E": [corr["E"]]})
        layers.append(alt.Chart(cd).mark_point(
            size=140, color="black", shape="cross").encode(
            x="logj:Q", y="E:Q",
            tooltip=[alt.Tooltip("E:Q", title="E_corr"),
                     alt.Tooltip("logj:Q", title="log10 i_corr")]))

    chart = alt.layer(*layers).properties(width=650, height=420)
    plot = mo.ui.altair_chart(chart, chart_selection=False, legend_selection=False)
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
    filename = mo.ui.text(value="tafel_plot.png", label="Filename",
                          full_width=True)
    ppi = mo.ui.number(value=300, start=72, stop=1200, step=1, label="ppi")
    save_button = mo.ui.run_button(label="💾 Save PNG to disk")
    mo.vstack([filename, ppi, save_button])
    return filename, ppi, save_button


@app.cell
def _(chart, mo, ppi):
    import vl_convert as vlc
    scale = ppi.value / 72.0
    png_bytes = vlc.vegalite_to_png(chart.to_json(), scale=scale)
    download = mo.download(data=png_bytes, filename="tafel_plot.png",
                           mimetype="image/png",
                           label=f"⬇️ Download PNG ({ppi.value} ppi)")
    mo.md(f"PNG rendered ({len(png_bytes)//1024} KB).\n\n{download}")
    return (png_bytes,)


@app.cell
def _(filename, mo, os, png_bytes, ppi, save_button):
    mo.stop(not save_button.value,
            mo.md("*Adjust the fit, then click **Save PNG to disk**.*"))
    fname = filename.value.strip() or "tafel_plot.png"
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


@app.cell
def _(mo):
    window = mo.ui.slider(start=3, stop=51, step=2, value=9,
                          label="Sliding-window size (points)", show_value=True)
    window
    return (window,)


@app.cell
def _(alt, mo, np, pd, tdf, window):
    # Local Tafel slope dE/d(log|j|) via a sliding linear fit, per branch,
    # to avoid mixing anodic/cathodic points across the zero-crossing.
    def _local_slopes(sub):
        sub = sub.sort_values("logj").reset_index(drop=True)
        w = window.value
        if len(sub) < w:
            return pd.DataFrame(columns=["logj", "slope_mV"])
        half = w // 2
        out = []
        for k in range(half, len(sub) - half):
            seg = sub.iloc[k - half:k + half + 1]
            s, _ = np.polyfit(seg["logj"], seg["E"], 1)
            out.append((sub["logj"].iloc[k], s * 1000.0))  # mV/decade
        return pd.DataFrame(out, columns=["logj", "slope_mV"])

    cath = _local_slopes(tdf[tdf["j"] < 0])
    anod = _local_slopes(tdf[tdf["j"] > 0])
    cath["branch"] = "cathodic"
    anod["branch"] = "anodic"
    diff = pd.concat([cath, anod], ignore_index=True)

    _zoom = alt.selection_interval(bind="scales")
    dchart = alt.Chart(diff).mark_line(point=True).encode(
        x=alt.X("logj:Q", title="log₁₀ |j|  (j in A/cm²)"),
        y=alt.Y("slope_mV:Q", title="Local Tafel slope (mV/dec)",
                scale=alt.Scale(zero=False)),
        color=alt.Color("branch:N", scale=alt.Scale(
            domain=["cathodic", "anodic"], range=["#1f77b4", "#d62728"])),
        tooltip=["branch:N", "logj:Q", "slope_mV:Q"],
    ).add_params(_zoom).properties(
        width=650, height=350,
        title="Differential Tafel plot — look for a flat plateau")
    diff_plot = mo.ui.altair_chart(dchart, chart_selection=False,
                                   legend_selection=False)
    mo.vstack([mo.md(
        "### Differential Tafel slope (plateau finder)\n"
        "A **flat region** = genuine Tafel behavior. Read the plateau's "
        "log|j| range, then set the branch sliders to bracket it."), diff_plot])
    return


if __name__ == "__main__":
    app.run()
