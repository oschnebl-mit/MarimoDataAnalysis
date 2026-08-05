import marimo

__generated_with = "0.23.15"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import os
    import io
    import pandas as pd
    import altair as alt

    return alt, mo, os, pd


@app.cell
def _(mo):
    mo.md("""
    # Gamry `.dta` Time-Domain Viewer
    Upload a Gamry `.dta` file (e.g. chronoamperometry). The parser is generic:
    it reads all `TABLE` blocks, skips the `OCVCURVE`, and plots the main `CURVE`.
    """)
    return


@app.cell
def _(pd):
    def _to_numeric(series):
        """Convert a column to numeric; if it's entirely non-numeric
        (e.g. the Gamry 'Over' column of '...........'), keep it as-is."""
        conv = pd.to_numeric(series, errors="coerce")
        if conv.notna().sum() == 0:
            return series
        return conv

    def parse_gamry_dta(text):
        """Parse a Gamry .dta file.

        Returns
        -------
        header : dict  -> {KEY: [remaining tab-separated fields]}
        tables : dict  -> {TABLE_NAME: {"data": DataFrame,
                                        "units": {col: unit},
                                        "n": npts}}
        """
        lines = text.splitlines()
        header, tables = {}, {}
        n = len(lines)
        i = 0
        while i < n:
            fields = lines[i].split("\t")

            # A table starts with:  NAME <tab> TABLE <tab> <npts>
            if len(fields) >= 3 and fields[1] == "TABLE":
                name = fields[0]
                try:
                    npts = int(fields[2])
                except ValueError:
                    npts = None

                labels = lines[i + 1].split("\t")[1:]   # skip leading empty field
                units = lines[i + 2].split("\t")[1:]

                rows, j, count = [], i + 3, 0
                while j < n:
                    row = lines[j].split("\t")
                    # data rows: leading empty field, then an integer Pt index
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
                    cols = labels[:ncol]
                    df = pd.DataFrame(rows, columns=cols)
                    for c in df.columns:
                        df[c] = _to_numeric(df[c])
                    tables[name] = {
                        "data": df,
                        "units": dict(zip(labels, units)),
                        "n": npts,
                    }
                i = j
            else:
                if fields and fields[0]:
                    header[fields[0]] = fields[1:]
                i += 1
        return header, tables

    return (parse_gamry_dta,)


@app.cell
def _(mo):
    file_upload = mo.ui.file(
        filetypes=[".dta", ".DTA", ".txt"],
        label="Upload Gamry .dta file",
    )
    file_upload
    return (file_upload,)


@app.cell
def _(file_upload, mo, parse_gamry_dta):
    mo.stop(not file_upload.value, mo.md("⬆️ **Upload a `.dta` file to begin.**"))

    _raw = file_upload.value[0].contents
    text = _raw.decode("latin-1") if isinstance(_raw, bytes) else _raw
    header, tables = parse_gamry_dta(text)

    technique = header.get("TAG", ["?"])[0]
    mo.md(
        f"**Technique (TAG):** `{technique}`  \n"
        f"**Tables found:** {', '.join(tables) or 'none'}"
    )
    return (tables,)


@app.cell
def _(mo, tables):
    # Choose which table to plot (default to CURVE, never OCVCURVE)
    _names = list(tables)
    _default = "CURVE" if "CURVE" in _names else (
        next((n for n in _names if n != "OCVCURVE"), _names[0])
    )
    table_select = mo.ui.dropdown(
        options=_names, value=_default, label="Data table"
    )
    table_select
    return (table_select,)


@app.cell
def _(mo, table_select, tables):
    df = tables[table_select.value]["data"]
    units = tables[table_select.value]["units"]

    # Only offer numeric columns for plotting
    numeric_cols = [c for c in df.columns if df[c].dtype.kind in "fi"]

    def _pick(preferred, fallback_idx):
        for p in preferred:
            if p in numeric_cols:
                return p
        return numeric_cols[min(fallback_idx, len(numeric_cols) - 1)]

    x_axis = mo.ui.dropdown(
        options=numeric_cols, value=_pick(["T"], 1), label="X axis (time)"
    )
    y_left = mo.ui.dropdown(
        options=numeric_cols, value=_pick(["Vf"], 2), label="Left Y (voltage)"
    )
    y_right = mo.ui.dropdown(
        options=numeric_cols, value=_pick(["Im"], 3), label="Right Y (current)"
    )

    mo.hstack([x_axis, y_left, y_right])
    return df, units, x_axis, y_left, y_right


@app.cell
def _():
    # def _lbl(col):
    #     u = units.get(col, "")
    #     return f"{col} ({u})" if u else col

    # xcol, lcol, rcol = x_axis.value, y_left.value, y_right.value

    # base = alt.Chart(df).encode(
    #     x=alt.X(f"{xcol}:Q", title=_lbl(xcol),
    #             scale=alt.Scale(zero=False, nice=False))
    # )

    # line_left = base.mark_line(color="#1f77b4").encode(
    #     y=alt.Y(f"{lcol}:Q", title=_lbl(lcol),
    #             axis=alt.Axis(titleColor="#1f77b4"),
    #             scale=alt.Scale(zero=False)),
    #     tooltip=[alt.Tooltip(f"{xcol}:Q"), alt.Tooltip(f"{lcol}:Q")],
    # )

    # line_right = base.mark_line(color="#d62728").encode(
    #     y=alt.Y(f"{rcol}:Q", title=_lbl(rcol),
    #             axis=alt.Axis(titleColor="#d62728"),
    #             scale=alt.Scale(zero=False)),
    #     tooltip=[alt.Tooltip(f"{xcol}:Q"), alt.Tooltip(f"{rcol}:Q")],
    # )

    # chart = (
    #     alt.layer(line_left, line_right)
    #     .resolve_scale(y="independent")
    #     .properties(width=650, height=380)
    # )

    # plot = mo.ui.altair_chart(chart)
    # plot
    return


@app.cell
def _(alt, df, mo, units, x_axis, y_left, y_right):
    def _lbl(col):
        u = units.get(col, "")
        return f"{col} ({u})" if u else col

    xcol, lcol, rcol = x_axis.value, y_left.value, y_right.value

    # zoom/pan on both axes + an x-interval brush for selecting points
    zoom = alt.selection_interval(bind="scales")
    brush = alt.selection_interval(encodings=["x"])

    base = alt.Chart(df).encode(
        x=alt.X(f"{xcol}:Q", title=_lbl(xcol),
                scale=alt.Scale(zero=False, nice=False))
    )

    line_left = base.mark_line(color="#1f77b4").encode(
        y=alt.Y(f"{lcol}:Q", title=_lbl(lcol),
                axis=alt.Axis(titleColor="#1f77b4"),
                scale=alt.Scale(zero=False)),
        tooltip=[alt.Tooltip(f"{xcol}:Q"), alt.Tooltip(f"{lcol}:Q")],
    )

    line_right = base.mark_line(color="#d62728").encode(
        y=alt.Y(f"{rcol}:Q", title=_lbl(rcol),
                axis=alt.Axis(titleColor="#d62728"),
                scale=alt.Scale(zero=False)),
        tooltip=[alt.Tooltip(f"{xcol}:Q"), alt.Tooltip(f"{rcol}:Q")],
    )

    chart = (
        alt.layer(line_left, line_right)
        .resolve_scale(y="independent")
        .add_params(zoom, brush)
        .properties(width=650, height=380)
    )

    plot = mo.ui.altair_chart(chart)
    plot
    return chart, plot


@app.cell
def _(mo, plot):
    # Shows whatever you brush/select on the chart — handy for reading off values
    mo.md("### Selected points") if len(plot.value) else mo.md(
        "*Brush/drag on the plot to select points.*"
    )
    return


@app.cell
def _():
    # plot.value
    return


@app.cell
def _(mo):
    mo.md("""
    ---
    ### Save high-resolution PNG (300 ppi)
    """)
    return


@app.cell
def _(chart, mo, ppi):
    # Render the PNG bytes once (used for both disk-save and download).
    import vl_convert as vlc

    scale = ppi.value / 72.0  # vl-convert scale factor -> 300 ppi ≈ 4.17x
    png_bytes = vlc.vegalite_to_png(chart.to_json(), scale=scale)

    download = mo.download(
        data=png_bytes,
        filename="gamry_plot.png",
        mimetype="image/png",
        label=f"⬇️ Download PNG ({ppi.value} ppi)",
    )
    mo.md(f"PNG rendered ({len(png_bytes)//1024} KB). Use the button below to "
          f"download, or the disk-save above.\n\n{download}")
    return (png_bytes,)


@app.cell
def _(mo):
    filename = mo.ui.text(value="gamry_plot.png", label="Filename", full_width=True)
    ppi = mo.ui.number(value=300, start=72, stop=1200, step=1, label="ppi")
    save_button = mo.ui.run_button(label="Save PNG")
    mo.vstack([filename, ppi, save_button])
    return filename, ppi, save_button


@app.cell
def _(filename, mo, os, png_bytes, ppi, save_button):
    # Decoupled: only writes when you click. Errors are shown, not swallowed.
    mo.stop(
        not save_button.value,
        mo.md("*Adjust the plot, then click **Save PNG to disk** when ready.*"),
    )

    fname = filename.value.strip() or "gamry_plot.png"
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
def _():
    return


if __name__ == "__main__":
    app.run()
