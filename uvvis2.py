import marimo

__generated_with = "0.23.15"
app = marimo.App(width="medium")


@app.cell
def _():
    import re
    from pathlib import Path

    import altair as alt
    import marimo as mo
    import numpy as np
    import pandas as pd

    HC = 1239.841984  # eV·nm  ->  E[eV] = HC / λ[nm]
    return HC, Path, alt, mo, np, pd, re


@app.cell
def _(mo):
    mo.md(r"""
    # UV-Vis overlay: %T / %R / %A

    1. Point the browser at your data folder and select one or more CSVs
       (columns `nm` + `%T` or `%R`, extra header/metadata lines are OK).
    2. Files that share a **sample label** are paired to give
       $$\%A = 100 - \%T - \%R$$ (interpolated onto the %T wavelength grid).
    3. Plot in wavelength; the top axis shows the equivalent photon energy
       $$E(\mathrm{eV}) = 1239.84 / \lambda(\mathrm{nm})$$.
    """)
    return


@app.cell
def _(Path, mo):
    root = mo.ui.text(
        value=str(Path.cwd()),
        label="Root folder",
        full_width=True,
    )
    root
    return (root,)


@app.cell
def _(Path, mo, root):
    _root = Path(root.value).expanduser()
    browser = mo.ui.file_browser(
        initial_path=_root if _root.is_dir() else Path.cwd(),
        filetypes=[".csv", ".CSV", ".txt", ".TXT", ".dat"],
        multiple=True,
        restrict_navigation=False,
        label="Select spectra (click several)",
    )
    browser
    return (browser,)


@app.cell
def _(Path, pd, re):
    # ------------------------- parsing helpers -------------------------
    _NUM = re.compile(r"^\s*[-+]?[.\d]")

    _STOPWORDS = {
        "t", "r", "a", "pct", "percent", "trans", "transmission", "transmittance",
        "refl", "reflection", "reflectance", "abs", "absorbance", "uv", "vis",
        "uvvis", "scan", "data", "raw", "csv", "spec", "spectrum",
    }

    def classify_column(name):
        """Map a column header to 'nm', '%T', '%R', 'Abs(file)' or None."""
        c = re.sub(r"[\s_]+", "", str(name)).lower()
        if any(k in c for k in ("nm", "wavelength", "wavelen", "lambda")):
            return "nm"
        if "%t" in c or "t%" in c or "trans" in c or c == "t":
            return "%T"
        if "%r" in c or "r%" in c or "refl" in c or c == "r":
            return "%R"
        if "abs" in c or c in ("a", "od"):
            return "Abs(file)"
        return None

    def quantity_from_filename(stem):
        s = "_" + re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_") + "_"
        if any(k in s for k in ("_t_", "_trans_", "transmission", "transmittance")):
            return "%T"
        if any(k in s for k in ("_r_", "_refl_", "reflection", "reflectance")):
            return "%R"
        return None

    def sample_from_filename(stem):
        toks = [
            t for t in re.split(r"[^A-Za-z0-9]+", stem)
            if t and t.lower() not in _STOPWORDS
        ]
        return " ".join(toks) if toks else stem

    def find_header(lines):
        """Return (skiprows, has_header) for instrument files with preambles."""
        first_num = None
        for i, line in enumerate(lines[:400]):
            if _NUM.match(line) and re.search(r"\d\s*[,;\t]\s*[-+.\d]", line):
                first_num = i
                break
        limit = first_num if first_num is not None else min(len(lines), 400)
        for i in range(limit):
            low = lines[i].lower()
            if any(k in low for k in ("nm", "wavelength", "%t", "%r")):
                return i, True
        if first_num is None:
            return 0, True
        return first_num, False

    def read_spectrum(path):
        """Return (long dataframe, error message or None)."""
        p = Path(path)
        try:
            lines = p.read_text(errors="replace").splitlines()
        except Exception as exc:  # noqa: BLE001
            return pd.DataFrame(), f"{p.name}: unreadable ({exc})"

        skip, has_header = find_header(lines)
        try:
            df = pd.read_csv(
                p,
                sep=None,
                engine="python",
                skiprows=skip,
                header=0 if has_header else None,
                on_bad_lines="skip",
                encoding_errors="replace",
            )
        except Exception as exc:  # noqa: BLE001
            return pd.DataFrame(), f"{p.name}: parse failed ({exc})"

        if df.shape[1] < 2:
            return pd.DataFrame(), f"{p.name}: fewer than 2 columns"

        kinds = {c: classify_column(c) for c in df.columns}
        if "nm" not in kinds.values():
            kinds[df.columns[0]] = "nm"
        xcol = next(c for c, k in kinds.items() if k == "nm")

        x = pd.to_numeric(df[xcol], errors="coerce")
        guess = quantity_from_filename(p.stem) or "%T"

        frames, used = [], []
        for c in df.columns:
            if c == xcol:
                continue
            kind = kinds[c] or guess
            if kind in used:
                kind = f"{kind} [{c}]"
            used.append(kind)
            y = pd.to_numeric(df[c], errors="coerce")
            m = x.notna() & y.notna()
            if m.sum() < 2:
                continue
            frames.append(
                pd.DataFrame(
                    {
                        "path": str(p),
                        "file": p.name,
                        "quantity": kind,
                        "nm": x[m].to_numpy(dtype=float),
                        "value": y[m].to_numpy(dtype=float),
                    }
                )
            )
        if not frames:
            return pd.DataFrame(), f"{p.name}: no numeric data columns"
        return pd.concat(frames, ignore_index=True), None

    return read_spectrum, sample_from_filename


@app.cell
def _(Path, browser, mo, pd, read_spectrum, sample_from_filename):
    _frames, _problems = [], []
    for _i in range(len(browser.value)):
        _p = Path(browser.path(_i))
        _df, _err = read_spectrum(_p)
        if _err:
            _problems.append(_err)
        if not _df.empty:
            _df["sample_auto"] = sample_from_filename(_p.stem)
            _frames.append(_df)

    raw = (
        pd.concat(_frames, ignore_index=True)
        if _frames
        else pd.DataFrame(
            columns=["path", "file", "quantity", "nm", "value", "sample_auto"]
        )
    )

    mo.md("\n".join(f"- ⚠️ {m}" for m in _problems)) if _problems else None
    return (raw,)


@app.cell
def _(Path, mo, raw):
    mo.stop(
        raw.empty,
        mo.md("### 👆 Select one or more CSV files to begin").callout(kind="info"),
    )

    _pairs = raw[["path", "sample_auto"]].drop_duplicates()
    labels = mo.ui.dictionary(
        {
            r.path: mo.ui.text(
                value=r.sample_auto, label=Path(r.path).name, full_width=True
            )
            for r in _pairs.itertuples()
        }
    )
    auto_percent = mo.ui.switch(value=True, label="Rescale 0–1 data to %")

    mo.accordion(
        {
            f"Sample labels ({len(labels)} files) — give %T and %R of the same "
            "sample identical labels to unlock %A": mo.vstack(
                [labels, auto_percent]
            )
        }
    )
    return auto_percent, labels


@app.cell
def _(HC, auto_percent, labels, np, pd, raw):
    _df = raw.copy()
    _df["sample"] = _df["path"].map(
        lambda p: (labels.value.get(p) or "").strip() or None
    )
    _df["sample"] = _df["sample"].fillna(_df["sample_auto"])

    # fraction -> percent
    if auto_percent.value:
        _idx = [
            g.index.to_numpy()
            for _, g in _df.groupby(["sample", "quantity"], sort=False)
            if g["value"].abs().max() <= 1.5
        ]
        if _idx:
            _sel = np.concatenate(_idx)
            _df.loc[_sel, "value"] = _df.loc[_sel, "value"] * 100.0

    # ---- derived %A = 100 - %T - %R, R interpolated onto the T grid ----
    _derived = []
    for _s, _g in _df.groupby("sample", sort=False):
        _t = _g[_g["quantity"] == "%T"].sort_values("nm")
        _r = _g[_g["quantity"] == "%R"].sort_values("nm")
        if _t.empty or _r.empty:
            continue
        _lo = max(_t["nm"].min(), _r["nm"].min())
        _hi = min(_t["nm"].max(), _r["nm"].max())
        _grid = _t.loc[_t["nm"].between(_lo, _hi), "nm"].to_numpy()
        if _grid.size < 2:
            continue
        _tv = np.interp(_grid, _t["nm"].to_numpy(), _t["value"].to_numpy())
        _rv = np.interp(_grid, _r["nm"].to_numpy(), _r["value"].to_numpy())
        _derived.append(
            pd.DataFrame(
                {
                    "path": "derived",
                    "file": "derived",
                    "quantity": "%A (100−T−R)",
                    "nm": _grid,
                    "value": 100.0 - _tv - _rv,
                    "sample_auto": _s,
                    "sample": _s,
                }
            )
        )

    tidy = pd.concat([_df, *_derived], ignore_index=True) if _derived else _df
    tidy["eV"] = HC / tidy["nm"]
    tidy = (
        tidy[["sample", "quantity", "nm", "eV", "value", "file"]]
        .sort_values(["sample", "quantity", "nm"])
        .reset_index(drop=True)
    )
    return (tidy,)


@app.cell
def _():
    # ev_mode = mo.ui.dropdown(
    #     options={
    #         "%A vs energy": "A",
    #         "Absorption coefficient α vs energy": "alpha",
    #         "Tauc plot (αhν)^γ vs energy": "tauc",
    #     },
    #     value="Tauc plot (αhν)^γ vs energy",
    #     label="Plot",
    # )
    # alpha_source = mo.ui.dropdown(
    #     options={
    #         "α = ln[(100−%R)/%T] / t   (R-corrected Beer–Lambert)": "trt",
    #         "α = −ln(%T/100) / t   (no R correction)": "t",
    #         "α = −ln(1 − %A/100) / t   (from 100−T−R)": "abs",
    #         "Kubelka–Munk F(R) = (1−R)²/2R   (diffuse %R, no t)": "km",
    #     },
    #     value="α = ln[(100−%R)/%T] / t   (R-corrected Beer–Lambert)",
    #     label="α from",
    # )
    # thickness = mo.ui.number(
    #     start=0.1, stop=1e7, step=10, value=500.0, label="Thickness t (nm)"
    # )
    # gamma_sel = mo.ui.radio(
    #     options={
    #         "direct allowed, γ = 2": 2.0,
    #         "indirect allowed, γ = 1/2": 0.5,
    #         "direct forbidden, γ = 2/3": 2.0 / 3.0,
    #         "indirect forbidden, γ = 1/3": 1.0 / 3.0,
    #     },
    #     value="direct allowed, γ = 2",
    #     label="Transition type",
    # )
    # norm_y = mo.ui.switch(value=False, label="Normalize each curve to max = 1")

    # _e0 = round(float(tidy["eV"].min()), 2)
    # _e1 = round(float(tidy["eV"].max()), 2)
    # _span = _e1 - _e0
    # ev_window = mo.ui.range_slider(
    #     start=_e0, stop=_e1, step=0.01, value=[_e0, _e1],
    #     label="Energy window (eV)", show_value=True, full_width=True,
    # )
    # fit_range = mo.ui.range_slider(
    #     start=_e0, stop=_e1, step=0.01,
    #     value=[round(_e0 + 0.55 * _span, 2), round(_e0 + 0.80 * _span, 2)],
    #     label="Linear-fit window for E_g (eV)", show_value=True, full_width=True,
    # )
    # show_fit = mo.ui.switch(value=True, label="Show fit + E_g intercept")

    # mo.vstack(
    #     [
    #         mo.hstack(
    #             [
    #                 mo.vstack([ev_mode, alpha_source]),
    #                 mo.vstack([gamma_sel]),
    #                 mo.vstack([thickness, norm_y, show_fit]),
    #             ],
    #             widths=[2, 1, 1], gap=1,
    #         ),
    #         ev_window,
    #         fit_range,
    #     ]
    # )
    return


@app.cell
def _(mo, tidy):
    _qs = sorted(tidy["quantity"].unique())
    _default = [q for q in _qs if not q.startswith("Abs")] or _qs
    quantity_sel = mo.ui.multiselect(
        options=_qs, value=_default, label="Traces to plot"
    )

    _lo, _hi = float(tidy["nm"].min()), float(tidy["nm"].max())
    nm_range = mo.ui.range_slider(
        start=_lo, stop=_hi, step=1, value=[_lo, _hi],
        label="λ window (nm)", show_value=True, full_width=True,
    )
    smooth_win = mo.ui.slider(
        start=1, stop=51, step=2, value=1, label="Smoothing (pts)", show_value=True
    )
    stride = mo.ui.slider(
        start=1, stop=20, value=1, label="Plot every Nth point", show_value=True
    )
    y_auto = mo.ui.switch(value=True, label="Auto y-range")
    y_range = mo.ui.range_slider(
        start=-50, stop=150, step=1, value=[0, 100], label="y range (%)", show_value=True
    )
    ev_axis = mo.ui.switch(value=True, label="Top axis in eV")

    mo.hstack(
        [
            mo.vstack([quantity_sel, nm_range]),
            mo.vstack([smooth_win, stride]),
            mo.vstack([y_auto, y_range, ev_axis]),
        ],
        widths=[2, 1, 1],
        gap=1,
    )
    return ev_axis, nm_range, quantity_sel, smooth_win, stride, y_auto, y_range


@app.cell
def _(
    HC,
    alt,
    ev_axis,
    mo,
    nm_range,
    pd,
    quantity_sel,
    smooth_win,
    stride,
    tidy,
    y_auto,
    y_range,
):
    _lo, _hi = float(nm_range.value[0]), float(nm_range.value[1])
    plot_df = tidy[
        tidy["quantity"].isin(quantity_sel.value) & tidy["nm"].between(_lo, _hi)
    ].copy()

    if smooth_win.value > 1 and not plot_df.empty:
        plot_df["value"] = (
            plot_df.groupby(["sample", "quantity"], sort=False)["value"]
            .transform(
                lambda s: s.rolling(smooth_win.value, center=True, min_periods=1).mean()
            )
        )

    if stride.value > 1 and not plot_df.empty:
        _k = plot_df.groupby(["sample", "quantity"], sort=False).cumcount()
        plot_df = plot_df[_k % stride.value == 0]

    mo.stop(
        plot_df.empty,
        mo.md("No data in the current selection / window.").callout(kind="warn"),
    )

    _x = alt.X(
        "nm:Q",
        title="Wavelength (nm)",
        scale=alt.Scale(domain=[_lo, _hi], nice=False),
    )
    _yscale = (
        alt.Scale(zero=False, nice=True)
        if y_auto.value
        else alt.Scale(domain=[float(y_range.value[0]), float(y_range.value[1])], clamp=True)
    )
    _y = alt.Y("value:Q", title="Signal (%)", scale=_yscale)
    _color = alt.Color("sample:N", title="Sample", scale=alt.Scale(scheme="tableau10"))
    _dash = alt.StrokeDash("quantity:N", title="Quantity")
    _tooltip = [
        alt.Tooltip("sample:N", title="Sample"),
        alt.Tooltip("quantity:N", title="Quantity"),
        alt.Tooltip("nm:Q", title="λ (nm)", format=".1f"),
        alt.Tooltip("eV:Q", title="E (eV)", format=".3f"),
        alt.Tooltip("value:Q", title="Value (%)", format=".3f"),
    ]

    _brush = alt.selection_interval(encodings=["x"])

    _lines = (
        alt.Chart(plot_df)
        .mark_line(strokeWidth=1.8, clip=True)
        .encode(x=_x, y=_y, color=_color, strokeDash=_dash)
        .add_params(_brush)
    )
    # invisible markers -> per-point tooltips without extra selections
    _hover = (
        alt.Chart(plot_df)
        .mark_circle(size=70, opacity=0)
        .encode(x=_x, y=_y, color=_color, tooltip=_tooltip)
    )

    _layers = [_lines, _hover]

    if ev_axis.value:
        _cands = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.4, 1.6, 1.8,
                  2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]
        _evs = [e for e in _cands if _lo <= HC / e <= _hi]
        while len(_evs) > 10:
            _evs = _evs[::2]
        if _evs:
            _pos = [HC / e for e in _evs]
            _layers.append(
                alt.Chart(pd.DataFrame({"nm": _pos}))
                .mark_rule(opacity=0)
                .encode(
                    x=alt.X(
                        "nm:Q",
                        scale=alt.Scale(domain=[_lo, _hi], nice=False),
                        axis=alt.Axis(
                            orient="top",
                            values=_pos,
                            labelExpr=f"format({HC}/datum.value, '.2f')",
                            title="Photon energy (eV)",
                            grid=False,
                        ),
                    )
                )
            )

    _spec = (
        alt.layer(*_layers)
        .resolve_scale(x="shared", y="shared")
        .properties(height=440, width="container")
    )

    chart = mo.ui.altair_chart(_spec, chart_selection=False, legend_selection=False)
    chart
    return (plot_df,)


@app.cell(hide_code=True)
def _():
    # probe = mo.ui.number(
    #     start=float(nm_range.value[0]),
    #     stop=float(nm_range.value[1]),
    #     step=0.5,
    #     value=float(np.median(plot_df["nm"])),
    #     label="Read all traces at λ (nm)",
    # )
    # probe
    return


@app.cell
def _(HC, np, plot_df, probe):
    _rows = []
    for (_s, _q), _g in plot_df.groupby(["sample", "quantity"], sort=True):
        _g = _g.sort_values("nm")
        _rows.append(
            {
                "sample": _s,
                "quantity": _q,
                f"value @ {probe.value:g} nm": float(
                    np.interp(probe.value, _g["nm"], _g["value"])
                ),
                "min %": float(_g["value"].min()),
                "max %": float(_g["value"].max()),
                "λ of max (nm)": float(_g.loc[_g["value"].idxmax(), "nm"]),
                "λ range (nm)": f"{_g['nm'].min():.0f}–{_g['nm'].max():.0f}",
                "E @ probe (eV)": HC / probe.value,
            }
        )
    # mo.ui.table(pd.DataFrame(_rows).round(3), selection=None)
    return


@app.cell
def _():
    # _wide = plot_df.pivot_table(
    #     index="nm", columns=["sample", "quantity"], values="value"
    # )
    # _wide.columns = [f"{s} {q}" for s, q in _wide.columns]
    # mo.hstack(
    #     [
    #         mo.download(
    #             data=plot_df.to_csv(index=False).encode(),
    #             filename="overlay_long.csv",
    #             mimetype="text/csv",
    #             label="⬇ tidy (long) CSV",
    #         ),
    #         mo.download(
    #             data=_wide.reset_index().to_csv(index=False).encode(),
    #             filename="overlay_wide.csv",
    #             mimetype="text/csv",
    #             label="⬇ wide CSV (one column per trace)",
    #         ),
    #     ],
    #     justify="start",
    #     gap=1,
    # )
    return


@app.cell(hide_code=True)
def _():
    # def sample_optics(tidy_df, samples):
    #     """Interpolate each sample's %T and %R onto one common λ grid.

    #     Returns (wide dataframe: sample, nm, eV, pctT, pctR, pctA; status dataframe).
    #     """
    #     _frames, _status = [], []
    #     for _s in samples:
    #         _g = tidy_df[tidy_df["sample"] == _s]

    #         def _grab(q, _g=_g):
    #             _sub = (
    #                 _g[_g["quantity"] == q]
    #                 .drop_duplicates(subset="nm")
    #                 .sort_values("nm")
    #             )
    #             return _sub["nm"].to_numpy(float), _sub["value"].to_numpy(float)

    #         _nmT, _T = _grab("%T")
    #         _nmR, _R = _grab("%R")
    #         _hasT, _hasR = _nmT.size >= 2, _nmR.size >= 2

    #         _row = {"sample": _s, "has %T": _hasT, "has %R": _hasR}
    #         if not (_hasT or _hasR):
    #             _status.append({**_row, "note": "no usable %T/%R"})
    #             continue

    #         if _hasT and _hasR:
    #             _lo = max(_nmT.min(), _nmR.min())
    #             _hi = min(_nmT.max(), _nmR.max())
    #             _base = _nmT if _nmT.size >= _nmR.size else _nmR
    #             _grid = _base[(_base >= _lo) & (_base <= _hi)]
    #             _note = "%T + %R → %A and α available"
    #         elif _hasT:
    #             _grid, _note = _nmT, "%T only → α from T, no %A"
    #         else:
    #             _grid, _note = _nmR, "%R only → Kubelka–Munk only"

    #         if _grid.size < 5:
    #             _status.append({**_row, "note": "λ overlap too small"})
    #             continue

    #         _Ti = np.interp(_grid, _nmT, _T) if _hasT else np.full(_grid.size, np.nan)
    #         _Ri = np.interp(_grid, _nmR, _R) if _hasR else np.full(_grid.size, np.nan)

    #         _frames.append(
    #             pd.DataFrame(
    #                 {
    #                     "sample": _s,
    #                     "nm": _grid,
    #                     "eV": HC / _grid,
    #                     "pctT": _Ti,
    #                     "pctR": _Ri,
    #                     "pctA": 100.0 - _Ti - _Ri,
    #                 }
    #             )
    #         )
    #         _status.append(
    #             {
    #                 **_row,
    #                 "n pts": int(_grid.size),
    #                 "λ range (nm)": f"{_grid.min():.0f}–{_grid.max():.0f}",
    #                 "E range (eV)": f"{HC/_grid.max():.2f}–{HC/_grid.min():.2f}",
    #                 "note": _note,
    #             }
    #         )

    #     _cols = ["sample", "nm", "eV", "pctT", "pctR", "pctA"]
    #     _out = (
    #         pd.concat(_frames, ignore_index=True)
    #         if _frames
    #         else pd.DataFrame(columns=_cols)
    #     )
    #     return _out, pd.DataFrame(_status)

    # def add_alpha(df, source, t_map_nm):
    #     """Attach α (cm⁻¹) or Kubelka–Munk F(R) column per row, per-sample thickness."""
    #     _d = df.copy()
    #     _t_cm = _d["sample"].map(t_map_nm).astype(float).to_numpy() * 1e-7
    #     _T, _R, _A = (
    #         _d["pctT"].to_numpy(float),
    #         _d["pctR"].to_numpy(float),
    #         _d["pctA"].to_numpy(float),
    #     )
    #     with np.errstate(divide="ignore", invalid="ignore"):
    #         if source == "trt":       # reflection-corrected Beer–Lambert
    #             _num = np.where(100.0 - _R > 0, 100.0 - _R, np.nan)
    #             _den = np.where(_T > 0, _T, np.nan)
    #             _a = np.log(_num / _den) / _t_cm
    #         elif source == "t":       # no R correction
    #             _a = -np.log(np.where(_T > 0, _T / 100.0, np.nan)) / _t_cm
    #         elif source == "abs":     # from absorptance 100−T−R
    #             _thru = 1.0 - _A / 100.0
    #             _a = -np.log(np.where(_thru > 0, _thru, np.nan)) / _t_cm
    #         else:                     # Kubelka–Munk, thickness-free, a.u.
    #             _Rf = np.where((_R > 0) & (_R < 100), _R / 100.0, np.nan)
    #             _a = (1.0 - _Rf) ** 2 / (2.0 * _Rf)
    #     _d["alpha"] = np.asarray(_a, float)
    #     return _d.replace([np.inf, -np.inf], np.nan)

    # def conjugate_axis(domain, primary="nm", max_ticks=9):
    #     """Transparent layer adding a top axis in the conjugate unit (nm <-> eV)."""
    #     _lo, _hi = float(domain[0]), float(domain[1])
    #     if primary == "nm":
    #         _cands = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0,
    #                   2.25, 2.5, 2.75, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]
    #         _title, _fmt = "Photon energy (eV)", ".2f"
    #     else:
    #         _cands = [200, 250, 300, 350, 400, 450, 500, 600, 700, 800, 900,
    #                   1000, 1200, 1500, 2000, 2500, 3000]
    #         _title, _fmt = "Wavelength (nm)", ".0f"
    #     _pos = [HC / c for c in _cands if _lo <= HC / c <= _hi]
    #     while len(_pos) > max_ticks:
    #         _pos = _pos[::2]
    #     if not _pos:
    #         return None
    #     return (
    #         alt.Chart(pd.DataFrame({primary: _pos}))
    #         .mark_rule(opacity=0)
    #         .encode(
    #             x=alt.X(
    #                 f"{primary}:Q",
    #                 scale=alt.Scale(domain=[_lo, _hi], nice=False),
    #                 axis=alt.Axis(
    #                     orient="top",
    #                     values=_pos,
    #                     labelExpr=f"format({HC}/datum.value, '{_fmt}')",
    #                     title=_title,
    #                     grid=False,
    #                 ),
    #             )
    #         )
    #     )

    # def smooth_by(df, group_cols, col, win):
    #     if win <= 1:
    #         return df
    #     _d = df.copy()
    #     _d[col] = _d.groupby(group_cols, sort=False)[col].transform(
    #         lambda s: s.rolling(win, center=True, min_periods=1).mean()
    #     )
    #     return _d
    return


@app.cell(hide_code=True)
def _(HC, alt, np, pd):
    def _unused_placeholder():  # (delete; only here to show nothing else changed)
        pass

    def series_for(group, quantity):
        """Sorted, de-duplicated (nm, value) arrays for one quantity."""
        sub = (
            group[group["quantity"] == quantity]
            .drop_duplicates(subset="nm")
            .sort_values("nm")
        )
        return sub["nm"].to_numpy(float), sub["value"].to_numpy(float)

    def sample_optics(tidy_df, samples):
        """Interpolate each sample's %T and %R onto one common λ grid.

        Returns (wide df: sample, nm, eV, pctT, pctR, pctA; status df).
        """
        frames, status = [], []

        for name in samples:
            group = tidy_df[tidy_df["sample"] == name]
            nm_t, val_t = series_for(group, "%T")
            nm_r, val_r = series_for(group, "%R")
            has_t, has_r = nm_t.size >= 2, nm_r.size >= 2
            row = {"sample": name, "has %T": has_t, "has %R": has_r}

            if not (has_t or has_r):
                status.append({**row, "note": "no usable %T/%R"})
                continue

            if has_t and has_r:
                lo = max(nm_t.min(), nm_r.min())
                hi = min(nm_t.max(), nm_r.max())
                base = nm_t if nm_t.size >= nm_r.size else nm_r
                grid = base[(base >= lo) & (base <= hi)]
                note = "%T + %R → %A and α available"
            elif has_t:
                grid, note = nm_t, "%T only → α from T, no %A"
            else:
                grid, note = nm_r, "%R only → Kubelka–Munk only"

            if grid.size < 5:
                status.append({**row, "note": "λ overlap too small"})
                continue

            t_i = np.interp(grid, nm_t, val_t) if has_t else np.full(grid.size, np.nan)
            r_i = np.interp(grid, nm_r, val_r) if has_r else np.full(grid.size, np.nan)

            frames.append(
                pd.DataFrame(
                    {
                        "sample": name,
                        "nm": grid,
                        "eV": HC / grid,
                        "pctT": t_i,
                        "pctR": r_i,
                        "pctA": 100.0 - t_i - r_i,
                    }
                )
            )
            status.append(
                {
                    **row,
                    "n pts": int(grid.size),
                    "λ range (nm)": f"{grid.min():.0f}–{grid.max():.0f}",
                    "E range (eV)": f"{HC / grid.max():.2f}–{HC / grid.min():.2f}",
                    "note": note,
                }
            )

        cols = ["sample", "nm", "eV", "pctT", "pctR", "pctA"]
        wide = (
            pd.concat(frames, ignore_index=True)
            if frames
            else pd.DataFrame(columns=cols)
        )
        return wide, pd.DataFrame(status)

    def add_alpha(df, source, thickness_nm_map):
        """Attach α (cm⁻¹) or Kubelka–Munk F(R), using each sample's own thickness."""
        out = df.copy()
        t_cm = out["sample"].map(thickness_nm_map).astype(float).to_numpy() * 1e-7
        pct_t = out["pctT"].to_numpy(float)
        pct_r = out["pctR"].to_numpy(float)
        pct_a = out["pctA"].to_numpy(float)

        with np.errstate(divide="ignore", invalid="ignore"):
            if source == "trt":                       # reflection-corrected
                num = np.where(100.0 - pct_r > 0, 100.0 - pct_r, np.nan)
                den = np.where(pct_t > 0, pct_t, np.nan)
                alpha = np.log(num / den) / t_cm
            elif source == "t":                       # no R correction
                alpha = -np.log(np.where(pct_t > 0, pct_t / 100.0, np.nan)) / t_cm
            elif source == "abs":                     # from 100 − T − R
                through = 1.0 - pct_a / 100.0
                alpha = -np.log(np.where(through > 0, through, np.nan)) / t_cm
            else:                                     # Kubelka–Munk (a.u.)
                r_frac = np.where((pct_r > 0) & (pct_r < 100), pct_r / 100.0, np.nan)
                alpha = (1.0 - r_frac) ** 2 / (2.0 * r_frac)

        out["alpha"] = np.asarray(alpha, float)
        return out.replace([np.inf, -np.inf], np.nan)

    def conjugate_axis(domain, primary="nm", max_ticks=9):
        """Transparent layer adding a top axis in the conjugate unit (nm ↔ eV)."""
        lo, hi = float(domain[0]), float(domain[1])
        if primary == "nm":
            candidates = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.4, 1.6, 1.8,
                          2.0, 2.25, 2.5, 2.75, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]
            title, fmt = "Photon energy (eV)", ".2f"
        else:
            candidates = [200, 250, 300, 350, 400, 450, 500, 600, 700, 800, 900,
                          1000, 1200, 1500, 2000, 2500, 3000]
            title, fmt = "Wavelength (nm)", ".0f"

        positions = [HC / c for c in candidates if lo <= HC / c <= hi]
        while len(positions) > max_ticks:
            positions = positions[::2]
        if not positions:
            return None

        return (
            alt.Chart(pd.DataFrame({primary: positions}))
            .mark_rule(opacity=0)
            .encode(
                x=alt.X(
                    f"{primary}:Q",
                    scale=alt.Scale(domain=[lo, hi], nice=False),
                    axis=alt.Axis(
                        orient="top",
                        values=positions,
                        labelExpr=f"format({HC}/datum.value, '{fmt}')",
                        title=title,
                        grid=False,
                    ),
                )
            )
        )

    def smooth_by(df, group_cols, col, win):
        if win <= 1:
            return df
        out = df.copy()
        out[col] = out.groupby(group_cols, sort=False)[col].transform(
            lambda s: s.rolling(win, center=True, min_periods=1).mean()
        )
        return out

    return add_alpha, conjugate_axis, sample_optics, smooth_by


@app.cell
def _(mo, tidy):
    _all = sorted(tidy["sample"].unique())
    sample_pick = mo.ui.multiselect(
        options=_all, value=_all, label=f"Samples to overlay ({len(_all)} found)"
    )
    order_by = mo.ui.dropdown(
        options={"alphabetical": "name", "selection order": "given"},
        value="alphabetical",
        label="Legend order",
    )

    _nm0, _nm1 = float(tidy["nm"].min()), float(tidy["nm"].max())
    baseline_on = mo.ui.switch(
        value=False, label="Subtract sub-gap %A baseline (scatter/offset correction)"
    )
    baseline_win = mo.ui.range_slider(
        start=_nm0, stop=_nm1, step=1,
        value=[max(_nm0, _nm1 - 150), _nm1],
        label="Baseline λ window (nm) — pick a transparent region",
        show_value=True, full_width=True,
    )

    mo.vstack(
        [
            mo.hstack([sample_pick, order_by], widths=[3, 1], gap=1),
            mo.hstack([baseline_on], justify="start"),
            baseline_win,
        ]
    )
    return baseline_on, baseline_win, order_by, sample_pick


@app.cell
def _(
    baseline_on,
    baseline_win,
    mo,
    np,
    order_by,
    sample_optics,
    sample_pick,
    tidy,
):
    _samples = list(sample_pick.value)
    if order_by.value == "name":
        _samples = sorted(_samples)

    mo.stop(
        not _samples,
        mo.md("### Pick at least one sample above.").callout(kind="info"),
    )

    optics, optics_status = sample_optics(tidy, _samples)
    mo.stop(
        optics.empty,
        mo.md("No sample had usable %T/%R data.").callout(kind="warn"),
    )

    baseline_table = None
    if baseline_on.value:
        _lo, _hi = baseline_win.value
        _rows = []
        for _s, _g in optics.groupby("sample", sort=False):
            _m = _g["nm"].between(_lo, _hi) & _g["pctA"].notna()
            _b = float(np.nanmedian(_g.loc[_m, "pctA"])) if _m.any() else 0.0
            optics.loc[optics["sample"] == _s, "pctA"] -= _b
            _rows.append({"sample": _s, "baseline %A subtracted": round(_b, 3)})
        baseline_table = _rows

    sample_order = _samples

    mo.accordion(
        {
            "Per-sample data status"
            + (" · baseline applied" if baseline_on.value else ""): mo.vstack(
                [
                    mo.ui.table(optics_status, selection=None),
                    mo.ui.table(baseline_table, selection=None)
                    if baseline_table
                    else mo.md(""),
                ]
            )
        }
    )
    return optics, sample_order


@app.cell
def _(mo, optics):
    absA_x = mo.ui.radio(
        options={"wavelength (nm)": "nm", "energy (eV)": "eV"},
        value="wavelength (nm)", label="x axis", inline=True,
    )
    absA_smooth = mo.ui.slider(
        start=1, stop=51, step=2, value=1, label="Smoothing (pts)", show_value=True
    )
    absA_offset = mo.ui.slider(
        start=0, stop=50, step=1, value=0,
        label="Stack offset (% per curve)", show_value=True,
    )
    absA_norm = mo.ui.switch(value=False, label="Normalize each %A to its max")
    _n0, _n1 = float(optics["nm"].min()), float(optics["nm"].max())
    absA_win = mo.ui.range_slider(
        start=_n0, stop=_n1, step=1, value=[_n0, _n1],
        label="λ window (nm)", show_value=True, full_width=True,
    )
    mo.vstack(
        [
            mo.hstack(
                [absA_x, absA_smooth, absA_offset, absA_norm],
                justify="start", gap=1, wrap=True,
            ),
            absA_win,
        ]
    )
    return absA_norm, absA_offset, absA_smooth, absA_win, absA_x


@app.cell
def _(
    HC,
    absA_norm,
    absA_offset,
    absA_smooth,
    absA_win,
    absA_x,
    alt,
    conjugate_axis,
    mo,
    optics,
    sample_order,
    smooth_by,
):
    _df = optics[optics["nm"].between(*absA_win.value)].dropna(subset=["pctA"]).copy()
    mo.stop(
        _df.empty,
        mo.md(
            "**No %A available.** %A needs both %T *and* %R for a sample — "
            "check the sample labels so the two files share a label."
        ).callout(kind="warn"),
    )

    _df = smooth_by(_df, ["sample"], "pctA", absA_smooth.value)

    if absA_norm.value:
        _df["pctA"] = _df.groupby("sample", sort=False)["pctA"].transform(
            lambda s: s / s.max() if s.max() > 0 else s
        )
    if absA_offset.value:
        _idx = {s: i for i, s in enumerate(sample_order)}
        _df["pctA"] = _df["pctA"] + _df["sample"].map(_idx) * absA_offset.value

    _xf = absA_x.value
    _dom = (
        list(absA_win.value)
        if _xf == "nm"
        else [HC / absA_win.value[1], HC / absA_win.value[0]]
    )
    _x = alt.X(
        f"{_xf}:Q",
        title="Wavelength (nm)" if _xf == "nm" else "Photon energy (eV)",
        scale=alt.Scale(domain=_dom, nice=False),
    )
    _y = alt.Y(
        "pctA:Q",
        title="Absorptance %A = 100 − %T − %R"
        + (" (normalized)" if absA_norm.value else "")
        + (" + offset" if absA_offset.value else ""),
        scale=alt.Scale(zero=False, nice=True),
    )
    _color = alt.Color(
        "sample:N", title="Sample",
        scale=alt.Scale(domain=sample_order, scheme="tableau10"),
        sort=sample_order,
    )
    _tip = [
        alt.Tooltip("sample:N"),
        alt.Tooltip("nm:Q", title="λ (nm)", format=".1f"),
        alt.Tooltip("eV:Q", title="E (eV)", format=".3f"),
        alt.Tooltip("pctA:Q", title="%A", format=".2f"),
        alt.Tooltip("pctT:Q", title="%T", format=".2f"),
        alt.Tooltip("pctR:Q", title="%R", format=".2f"),
    ]

    _layers = [
        alt.Chart(_df).mark_line(strokeWidth=1.9, clip=True).encode(
            x=_x, y=_y, color=_color
        ),
        alt.Chart(_df).mark_circle(size=70, opacity=0).encode(
            x=_x, y=_y, color=_color, tooltip=_tip
        ),
    ]
    _sec = conjugate_axis(_dom, primary=_xf)
    if _sec is not None:
        _layers.append(_sec)

    absA_chart = mo.ui.altair_chart(
        alt.layer(*_layers).resolve_scale(x="shared", y="shared")
        .properties(height=400, width="container", title="%A overlay — all samples"),
        chart_selection=False, legend_selection=True,
    )
    absA_chart

    return


@app.cell
def _(mo, sample_order):
    ev_mode = mo.ui.dropdown(
        options={
            "Tauc plot (αhν)^γ vs energy": "tauc",
            "Absorption coefficient α vs energy": "alpha",
            "%A vs energy": "A",
        },
        value="Tauc plot (αhν)^γ vs energy", label="Plot",
    )
    alpha_source = mo.ui.dropdown(
        options={
            "α = ln[(100−%R)/%T]/t   (R-corrected)": "trt",
            "α = −ln(%T/100)/t": "t",
            "α = −ln(1 − %A/100)/t": "abs",
            "Kubelka–Munk F(R) = (1−R)²/2R": "km",
        },
        value="α = ln[(100−%R)/%T]/t   (R-corrected)", label="α from",
    )
    gamma_global = mo.ui.radio(
        options={
            "direct allowed, γ = 2": 2.0,
            "indirect allowed, γ = 1/2": 0.5,
            "direct forbidden, γ = 2/3": 2.0 / 3.0,
            "indirect forbidden, γ = 1/3": 1.0 / 3.0,
        },
        value="direct allowed, γ = 2", label="Transition type",
    )
    gamma_per_sample = mo.ui.switch(value=False, label="Per-sample γ")
    gamma_dict = mo.ui.dictionary(
        {
            s: mo.ui.dropdown(
                options={"γ = 2 (direct)": 2.0, "γ = 1/2 (indirect)": 0.5,
                         "γ = 2/3": 2.0 / 3.0, "γ = 1/3": 1.0 / 3.0},
                value="γ = 2 (direct)", label=s,
            )
            for s in sample_order
        }
    )
    thickness_dict = mo.ui.dictionary(
        {
            s: mo.ui.number(start=0.1, stop=1e7, step=10, value=500.0, label=f"{s}  t (nm)")
            for s in sample_order
        }
    )
    tauc_norm = mo.ui.switch(
        value=False, label="Normalize each Tauc curve (compare shapes / unknown t)"
    )

    mo.vstack(
        [
            mo.hstack([ev_mode, alpha_source], widths=[1, 2], gap=1),
            mo.hstack([gamma_global, mo.vstack([gamma_per_sample, tauc_norm])], gap=1),
            mo.accordion(
                {
                    "Per-sample thickness": thickness_dict,
                    "Per-sample γ (used only when 'Per-sample γ' is on)": gamma_dict,
                }
            ),
        ]
    )
    return (
        alpha_source,
        ev_mode,
        gamma_dict,
        gamma_global,
        gamma_per_sample,
        tauc_norm,
        thickness_dict,
    )


@app.cell
def _(mo, optics, sample_order):
    _e0 = round(float(optics["eV"].min()), 2)
    _e1 = round(float(optics["eV"].max()), 2)
    _sp = _e1 - _e0

    ev_window = mo.ui.range_slider(
        start=_e0, stop=_e1, step=0.01, value=[_e0, _e1],
        label="Energy window (eV)", show_value=True, full_width=True,
    )
    fit_shared = mo.ui.range_slider(
        start=_e0, stop=_e1, step=0.01,
        value=[round(_e0 + 0.55 * _sp, 2), round(_e0 + 0.80 * _sp, 2)],
        label="Shared linear-fit window (eV)", show_value=True, full_width=True,
    )
    fit_per_sample = mo.ui.switch(value=False, label="Independent fit window per sample")
    fit_dict = mo.ui.dictionary(
        {
            s: mo.ui.range_slider(
                start=_e0, stop=_e1, step=0.01,
                value=[round(_e0 + 0.55 * _sp, 2), round(_e0 + 0.80 * _sp, 2)],
                label=s, show_value=True, full_width=True,
            )
            for s in sample_order
        }
    )
    show_fit = mo.ui.switch(value=True, label="Show fits + E_g")


    return ev_window, fit_dict, fit_per_sample, fit_shared, show_fit


@app.cell
def _(ev_window, fit_dict, fit_per_sample, fit_shared, mo, show_fit):
    mo.vstack(
        [
            ev_window,
            mo.hstack([show_fit, fit_per_sample], justify="start", gap=1),
            fit_dict if fit_per_sample.value else fit_shared,
        ]
    )
    return


@app.cell
def _(mo):
    fit_layers = mo.ui.multiselect(
        options=["fit window shading", "fit lines", "E_g markers", "nm top axis"],
        value=["fit window shading", "fit lines", "E_g markers", "nm top axis"],
        label="Overlay layers (uncheck to isolate a problem layer)",
    )
    debug_layers = mo.ui.switch(value=False, label="Show layer diagnostics")
    mo.hstack([fit_layers, debug_layers], justify="start", gap=1)
    return debug_layers, fit_layers


@app.cell
def _(
    HC,
    add_alpha,
    alpha_source,
    alt,
    conjugate_axis,
    debug_layers,
    ev_mode,
    ev_window,
    fit_dict,
    fit_layers,
    fit_per_sample,
    fit_shared,
    gamma_dict,
    gamma_global,
    gamma_per_sample,
    mo,
    np,
    optics,
    pd,
    sample_order,
    show_fit,
    tauc_norm,
    thickness_dict,
):
    # ---------- plain-named helper (no leading underscores inside a def) ----------
    def fit_linear(x_arr, y_arr):
        """Least-squares line; returns dict with finite-checked slope/intercept/E_g."""
        good = np.isfinite(x_arr) & np.isfinite(y_arr)
        x_arr, y_arr = x_arr[good], y_arr[good]
        if x_arr.size < 5 or np.ptp(x_arr) <= 0 or np.ptp(y_arr) <= 0:
            return None
        slope, intercept = np.polyfit(x_arr, y_arr, 1)
        if not (np.isfinite(slope) and np.isfinite(intercept)) or slope <= 0:
            return None
        e_gap = -intercept / slope
        if not np.isfinite(e_gap):
            return None
        resid = ((y_arr - (slope * x_arr + intercept)) ** 2).sum()
        total = ((y_arr - y_arr.mean()) ** 2).sum()
        r2 = 1.0 - resid / total if total > 0 else np.nan
        return {
            "slope": float(slope),
            "intercept": float(intercept),
            "E_g": float(e_gap),
            "r2": float(r2) if np.isfinite(r2) else np.nan,
            "n": int(x_arr.size),
            "x_max": float(x_arr.max()),
        }

    _mode, _src = ev_mode.value, alpha_source.value
    _km = _src == "km"
    _t_map = {s: float(thickness_dict.value[s]) for s in sample_order}
    _g_map = {
        s: (float(gamma_dict.value[s]) if gamma_per_sample.value
            else float(gamma_global.value))
        for s in sample_order
    }
    _fit_map = {
        s: (list(fit_dict.value[s]) if fit_per_sample.value else list(fit_shared.value))
        for s in sample_order
    }

    # ---------------- build y ----------------
    _d = add_alpha(optics, _src, _t_map)
    _d = _d[_d["eV"].between(*ev_window.value)].copy()
    _d["gamma"] = _d["sample"].map(_g_map)

    if _mode == "A":
        _d["y"] = _d["pctA"]
    elif _mode == "alpha":
        _d["y"] = _d["alpha"]
    else:
        _d["y"] = np.where(
            _d["alpha"] > 0, (_d["alpha"] * _d["eV"]) ** _d["gamma"], np.nan
        )

    _d = _d.replace([np.inf, -np.inf], np.nan)
    _d = _d[np.isfinite(_d["y"]) & np.isfinite(_d["eV"])].copy()
    mo.stop(
        _d.empty,
        mo.md("No finite values for this mode / α source.").callout(kind="warn"),
    )

    if tauc_norm.value and _mode != "A":
        _d["y"] = _d.groupby("sample", sort=False)["y"].transform(
            lambda s: s / s.max() if s.max() > 0 else s
        )
        _d = _d[np.isfinite(_d["y"])]

    # ---------- EXPLICIT domains so no overlay layer can hijack the scales ----------
    _xdom = [float(ev_window.value[0]), float(ev_window.value[1])]
    _y0, _y1 = float(_d["y"].min()), float(_d["y"].max())
    if not np.isfinite(_y0) or not np.isfinite(_y1) or _y1 <= _y0:
        _y0, _y1 = (_y0 - 1.0, _y0 + 1.0) if np.isfinite(_y0) else (0.0, 1.0)
    _pad = 0.05 * (_y1 - _y0)
    _ydom = [_y0 - _pad, _y1 + _pad] if _mode == "A" else [min(0.0, _y0), _y1 + _pad]

    # ---------------- per-sample fits (finite-safe) ----------------
    _fit_rows, _seg, _rules, _bands, _notes = [], [], [], [], []
    _gt = {2.0: "2", 0.5: "1/2", 2 / 3: "2/3", 1 / 3: "1/3"}

    if show_fit.value and _mode != "A":
        for _s in sample_order:
            _sub = _d[_d["sample"] == _s]
            if _sub.empty:
                continue
            _lo, _hi = float(_fit_map[_s][0]), float(_fit_map[_s][1])
            _bands.append(
                {"sample": _s, "eV": _lo, "eV2": _hi, "y": _ydom[0], "y2": _ydom[1]}
            )
            _w = _sub[_sub["eV"].between(_lo, _hi)].sort_values("eV")
            _res = fit_linear(_w["eV"].to_numpy(float), _w["y"].to_numpy(float))
            _base = {
                "sample": _s,
                "γ": _gt.get(_g_map[_s], f"{_g_map[_s]:.3g}"),
                "t (nm)": _t_map[_s],
                "fit window (eV)": f"{_lo:.2f}–{_hi:.2f}",
                "n pts": int(len(_w)),
            }
            if _res is None:
                _fit_rows.append(
                    {**_base, "E_g (eV)": np.nan, "λ_g (nm)": np.nan, "R²": np.nan,
                     "note": "no valid positive-slope fit — move/widen the window"}
                )
                _notes.append(f"{_s}: fit rejected ({len(_w)} pts in window)")
                continue

            _eg = _res["E_g"]
            _fit_rows.append(
                {**_base,
                 "E_g (eV)": round(_eg, 3),
                 "λ_g (nm)": round(HC / _eg, 1) if _eg > 0 else np.nan,
                 "R²": round(_res["r2"], 4) if np.isfinite(_res["r2"]) else np.nan,
                 "note": ""}
            )
            # clamp the drawn segment to the visible x-domain -> no scale blow-up
            _xa = float(np.clip(_eg, _xdom[0], _xdom[1]))
            _xb = float(np.clip(_res["x_max"], _xdom[0], _xdom[1]))
            for _xx in (_xa, _xb):
                _yy = _res["slope"] * _xx + _res["intercept"]
                if np.isfinite(_yy):
                    _seg.append({"sample": _s, "eV": _xx, "y": float(_yy)})
            if _xdom[0] <= _eg <= _xdom[1]:
                _rules.append({"sample": _s, "eV": _eg, "E_g": _eg})

    # ---------------- encodings ----------------
    _x = alt.X("eV:Q", title="Photon energy (eV)",
               scale=alt.Scale(domain=_xdom, nice=False, clamp=True))
    _gset = sorted({_g_map[s] for s in sample_order})
    _gtxt = "γ" if len(_gset) > 1 else _gt.get(_gset[0], f"{_gset[0]:.3g}")
    if _mode == "A":
        _ylab = "Absorptance %A = 100 − %T − %R"
    elif _mode == "alpha":
        _ylab = "F(R) (a.u.)" if _km else "α (cm⁻¹)"
    else:
        _ylab = (f"(F(R)·hν)^{_gtxt} (a.u.)" if _km
                 else f"(αhν)^{_gtxt}  [(cm⁻¹·eV)^{_gtxt}]")
    if tauc_norm.value and _mode != "A":
        _ylab += " — normalized"
    _y = alt.Y("y:Q", title=_ylab,
               scale=alt.Scale(domain=_ydom, nice=False, clamp=True))
    _color = alt.Color("sample:N", title="Sample", sort=sample_order,
                       scale=alt.Scale(domain=sample_order, scheme="tableau10"))

    _layers = []

    # shading FIRST, but same field names (eV/eV2, y/y2) and fully specified
    if _bands and "fit window shading" in fit_layers.value:
        _layers.append(
            alt.Chart(pd.DataFrame(_bands))
            .mark_rect(opacity=0.09, color="#4c78a8", stroke=None)
            .encode(x=_x, x2="eV2:Q", y=_y, y2="y2:Q")
        )

    _layers.append(
        alt.Chart(_d).mark_line(strokeWidth=1.9, clip=True).encode(
            x=_x, y=_y, color=_color
        )
    )
    _layers.append(
        alt.Chart(_d).mark_circle(size=70, opacity=0).encode(
            x=_x, y=_y, color=_color,
            tooltip=[
                alt.Tooltip("sample:N"),
                alt.Tooltip("eV:Q", title="E (eV)", format=".3f"),
                alt.Tooltip("nm:Q", title="λ (nm)", format=".1f"),
                alt.Tooltip("alpha:Q", title="α / F(R)", format=".4g"),
                alt.Tooltip("pctA:Q", title="%A", format=".2f"),
                alt.Tooltip("y:Q", title="y", format=".4g"),
            ],
        )
    )

    _seg_df = pd.DataFrame(_seg)
    if len(_seg_df) and "fit lines" in fit_layers.value:
        _seg_df = _seg_df[np.isfinite(_seg_df["y"]) & np.isfinite(_seg_df["eV"])]
        if len(_seg_df):
            _layers.append(
                alt.Chart(_seg_df)
                .mark_line(strokeDash=[6, 4], strokeWidth=1.5, clip=True)
                .encode(x=_x, y=_y, color=_color, detail="sample:N")
            )

    _rule_df = pd.DataFrame(_rules)
    if len(_rule_df) and "E_g markers" in fit_layers.value:
        _layers.append(
            alt.Chart(_rule_df)
            .mark_rule(strokeDash=[2, 3], opacity=0.85, clip=True)
            .encode(
                x=_x, y=alt.datum(_ydom[0]), y2=alt.datum(_ydom[1]), color=_color,
                tooltip=[alt.Tooltip("sample:N"),
                         alt.Tooltip("E_g:Q", title="E_g (eV)", format=".3f")],
            )
        )

    if "nm top axis" in fit_layers.value:
        _sec = conjugate_axis(_xdom, primary="eV")
        if _sec is not None:
            _layers.append(_sec)

    tauc_chart = mo.ui.altair_chart(
        alt.layer(*_layers).resolve_scale(x="shared", y="shared").properties(
            height=440, width="container",
            title="Tauc / α overlay — sample comparison",
        ),
        chart_selection=False, legend_selection=True,
    )

    tauc_fits = pd.DataFrame(
        _fit_rows,
        columns=["sample", "γ", "t (nm)", "E_g (eV)", "λ_g (nm)", "R²",
                 "fit window (eV)", "n pts", "note"],
    )

    _eg_bar = None
    if len(tauc_fits) and tauc_fits["E_g (eV)"].notna().any():
        _b = tauc_fits.dropna(subset=["E_g (eV)"])
        _eg_bar = (
            alt.Chart(_b).mark_bar().encode(
                y=alt.Y("sample:N", sort=sample_order, title=None),
                x=alt.X("E_g (eV):Q", scale=alt.Scale(zero=True), title="E_g (eV)"),
                color=_color,
                tooltip=["sample", "E_g (eV)", "λ_g (nm)", "R²", "γ"],
            ).properties(height=max(60, 28 * len(_b)), width="container")
        )

    _diag = mo.md("")
    if debug_layers.value:
        _diag = mo.ui.table(
            pd.DataFrame(
                [
                    {"layer": "data", "rows": len(_d),
                     "x min": _d["eV"].min(), "x max": _d["eV"].max(),
                     "y min": _d["y"].min(), "y max": _d["y"].max(),
                     "non-finite": int((~np.isfinite(_d["y"])).sum())},
                    {"layer": "fit segments", "rows": len(_seg_df),
                     "y min": _seg_df["y"].min() if len(_seg_df) else None,
                     "y max": _seg_df["y"].max() if len(_seg_df) else None},
                    {"layer": "E_g rules", "rows": len(_rule_df)},
                    {"layer": "shading", "rows": len(_bands)},
                    {"layer": "x domain", "x min": _xdom[0], "x max": _xdom[1]},
                    {"layer": "y domain", "y min": _ydom[0], "y max": _ydom[1]},
                ]
            ).round(5),
            selection=None,
        )

    mo.vstack(
        [
            tauc_chart,
            mo.md("⚠️ " + " · ".join(_notes)) if _notes else mo.md(""),
            mo.ui.table(tauc_fits, selection=None) if len(tauc_fits) else mo.md(
                "_Place the fit window on the linear onset to extract E_g._"
            ),
            _eg_bar if _eg_bar is not None else mo.md(""),
            _diag,
            mo.download(
                data=_d.to_csv(index=False).encode(),
                filename="tauc_multisample.csv",
                mimetype="text/csv",
                label="⬇ α / Tauc data for all samples (CSV)",
            ),
        ]
    )
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
