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
    # UV-Vis: %T / %R / %A and Tauc analysis

    1. Point the browser at your data folder and select CSVs
       (columns `nm` + `%T` or `%R`; extra header/metadata lines are OK).
    2. Files sharing a **sample label** are paired to give
       $$\%A = 100 - \%T - \%R$$
    3. Three plots below: one sample's %T/%R/%A, %A overlaid across all
       samples, and a Tauc $(\alpha h\nu)^\gamma$ analysis across all samples.
    """)
    return


@app.cell
def _(Path, mo):
    root = mo.ui.text(value=str(Path.cwd()), label="Root folder", full_width=True)
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
def _(HC, alt, np, pd):
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

    def sample_optics(tidy_df, samples):
        """Interpolate each sample's %T and %R onto one common λ grid.

        Returns (wide df: sample, nm, eV, pctT, pctR, pctA; status df).
        """

        def series_for(group, quantity):
            sub = (
                group[group["quantity"] == quantity]
                .drop_duplicates(subset="nm")
                .sort_values("nm")
            )
            return sub["nm"].to_numpy(float), sub["value"].to_numpy(float)

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

    def add_alpha(df, source, thickness_nm):
        """Attach α (cm⁻¹) or Kubelka–Munk F(R), using one shared thickness."""
        out = df.copy()
        t_cm = thickness_nm * 1e-7
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

    return add_alpha, conjugate_axis, fit_linear, sample_optics


@app.cell
def _(mo, tidy):
    mo.md("## Plot 1 — single sample: %T / %R / %A")
    _samples = sorted(tidy["sample"].unique())
    sample1 = mo.ui.dropdown(options=_samples, value=_samples[0], label="Sample")
    nm_range1 = mo.ui.range_slider(
        start=float(tidy["nm"].min()), stop=float(tidy["nm"].max()), step=1,
        value=[float(tidy["nm"].min()), float(tidy["nm"].max())],
        label="λ window (nm)", show_value=True, full_width=True,
    )
    smooth1 = mo.ui.slider(start=1, stop=51, step=2, value=1, label="Smoothing (pts)", show_value=True)
    ev_axis1 = mo.ui.switch(value=True, label="Top axis in eV")

    mo.vstack([sample1, nm_range1, mo.hstack([smooth1, ev_axis1], justify="start", gap=1)])
    return ev_axis1, nm_range1, sample1, smooth1


@app.cell
def _(alt, conjugate_axis, ev_axis1, mo, nm_range1, sample1, smooth1, tidy):
    _lo, _hi = float(nm_range1.value[0]), float(nm_range1.value[1])
    _df = tidy[
        (tidy["sample"] == sample1.value)
        & tidy["quantity"].isin(["%T", "%R", "%A (100−T−R)"])
        & tidy["nm"].between(_lo, _hi)
    ].copy()
    mo.stop(
        _df.empty,
        mo.md("No %T/%R/%A data for this sample/window.").callout(kind="warn"),
    )

    if smooth1.value > 1:
        _df["value"] = _df.groupby("quantity", sort=False)["value"].transform(
            lambda s: s.rolling(smooth1.value, center=True, min_periods=1).mean()
        )

    _x = alt.X("nm:Q", title="Wavelength (nm)", scale=alt.Scale(domain=[_lo, _hi], nice=False))
    _y = alt.Y("value:Q", title="Signal (%)", scale=alt.Scale(zero=False, nice=True))
    _color = alt.Color("quantity:N", title="Quantity", scale=alt.Scale(scheme="category10"))
    _tip = [
        alt.Tooltip("quantity:N", title="Quantity"),
        alt.Tooltip("nm:Q", title="λ (nm)", format=".1f"),
        alt.Tooltip("eV:Q", title="E (eV)", format=".3f"),
        alt.Tooltip("value:Q", title="Value (%)", format=".3f"),
    ]
    _layers = [
        alt.Chart(_df).mark_line(strokeWidth=1.9, clip=True).encode(x=_x, y=_y, color=_color),
        alt.Chart(_df).mark_circle(size=70, opacity=0).encode(x=_x, y=_y, color=_color, tooltip=_tip),
    ]
    if ev_axis1.value:
        _sec = conjugate_axis([_lo, _hi], primary="nm")
        if _sec is not None:
            _layers.append(_sec)

    mo.ui.altair_chart(
        alt.layer(*_layers).resolve_scale(x="shared", y="shared").properties(
            height=420, width="container", title=f"{sample1.value} — %T / %R / %A"
        ),
        chart_selection=False, legend_selection=True,
    )
    return


@app.cell
def _(mo, tidy):
    mo.md("## Plot 2 & 3 — all-sample comparisons")
    _all = sorted(tidy["sample"].unique())
    sample_pick = mo.ui.multiselect(
        options=_all, value=_all, label=f"Samples to overlay ({len(_all)} found)"
    )
    sample_pick
    return (sample_pick,)


@app.cell
def _(mo, sample_optics, sample_pick, tidy):
    sample_order = sorted(sample_pick.value)
    mo.stop(
        not sample_order,
        mo.md("### Pick at least one sample above.").callout(kind="info"),
    )

    optics, optics_status = sample_optics(tidy, sample_order)
    mo.stop(
        optics.empty,
        mo.md("No sample had usable %T/%R data.").callout(kind="warn"),
    )

    mo.accordion({"Per-sample data status": mo.ui.table(optics_status, selection=None)})
    return optics, sample_order


@app.cell
def _(mo):
    absA_x = mo.ui.radio(
        options={"wavelength (nm)": "nm", "energy (eV)": "eV"},
        value="wavelength (nm)", label="x axis", inline=True,
    )
    absA_smooth = mo.ui.slider(
        start=1, stop=51, step=2, value=1, label="Smoothing (pts)", show_value=True
    )
    mo.hstack([absA_x, absA_smooth], justify="start", gap=1)
    return absA_smooth, absA_x


@app.cell
def _(absA_smooth, absA_x, alt, conjugate_axis, mo, optics, sample_order):
    _df = optics.dropna(subset=["pctA"]).copy()
    mo.stop(
        _df.empty,
        mo.md(
            "**No %A available.** %A needs both %T *and* %R for a sample — "
            "check the sample labels so the two files share a label."
        ).callout(kind="warn"),
    )

    if absA_smooth.value > 1:
        _df["pctA"] = _df.groupby("sample", sort=False)["pctA"].transform(
            lambda s: s.rolling(absA_smooth.value, center=True, min_periods=1).mean()
        )

    _xf = absA_x.value
    _dom = (
        [float(_df["nm"].min()), float(_df["nm"].max())]
        if _xf == "nm"
        else [float(_df["eV"].min()), float(_df["eV"].max())]
    )
    _x = alt.X(
        f"{_xf}:Q",
        title="Wavelength (nm)" if _xf == "nm" else "Photon energy (eV)",
        scale=alt.Scale(domain=_dom, nice=False),
    )
    _y = alt.Y("pctA:Q", title="Absorptance %A = 100 − %T − %R", scale=alt.Scale(zero=False, nice=True))
    _color = alt.Color(
        "sample:N", title="Sample",
        scale=alt.Scale(domain=sample_order, scheme="tableau10"), sort=sample_order,
    )
    _tip = [
        alt.Tooltip("sample:N"),
        alt.Tooltip("nm:Q", title="λ (nm)", format=".1f"),
        alt.Tooltip("eV:Q", title="E (eV)", format=".3f"),
        alt.Tooltip("pctA:Q", title="%A", format=".2f"),
    ]
    _layers = [
        alt.Chart(_df).mark_line(strokeWidth=1.9, clip=True).encode(x=_x, y=_y, color=_color),
        alt.Chart(_df).mark_circle(size=70, opacity=0).encode(x=_x, y=_y, color=_color, tooltip=_tip),
    ]
    _sec = conjugate_axis(_dom, primary=_xf)
    if _sec is not None:
        _layers.append(_sec)

    mo.ui.altair_chart(
        alt.layer(*_layers).resolve_scale(x="shared", y="shared").properties(
            height=420, width="container", title="%A overlay — all samples"
        ),
        chart_selection=False, legend_selection=True,
    )
    return


@app.cell
def _(mo):
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
    thickness_global = mo.ui.number(start=0.1, stop=1e7, step=10, value=500.0, label="Thickness t (nm)")
    show_fit = mo.ui.switch(value=True, label="Show fits + E_g")

    mo.hstack([alpha_source, gamma_global, thickness_global, show_fit], justify="start", gap=1, wrap=True)
    return alpha_source, gamma_global, show_fit, thickness_global


@app.cell
def _(mo, optics, sample_order):
    _e0 = round(float(optics["eV"].min()), 2)
    _e1 = round(float(optics["eV"].max()), 2)
    _span = _e1 - _e0

    ev_window = mo.ui.range_slider(
        start=_e0, stop=_e1, step=0.01, value=[_e0, _e1],
        label="Energy window (eV)", show_value=True, full_width=True,
    )
    fit_windows = mo.ui.dictionary(
        {
            _s: mo.ui.range_slider(
                start=_e0, stop=_e1, step=0.01,
                value=[round(_e0 + 0.55 * _span, 2), round(_e0 + 0.80 * _span, 2)],
                label=_s, show_value=True, full_width=True,
            )
            for _s in sample_order
        }
    )
    mo.vstack([
        ev_window,
        mo.accordion(
            {"Per-sample linear-fit windows for E_g (eV)": mo.vstack(list(fit_windows.values()))}
        ),
    ])
    return ev_window, fit_windows


@app.cell
def _(
    HC,
    add_alpha,
    alpha_source,
    alt,
    conjugate_axis,
    ev_window,
    fit_linear,
    fit_windows,
    gamma_global,
    mo,
    np,
    optics,
    pd,
    sample_order,
    show_fit,
    thickness_global,
):
    _src, _gamma, _t = alpha_source.value, float(gamma_global.value), float(thickness_global.value)
    _km = _src == "km"

    _d = add_alpha(optics, _src, _t)
    _d = _d[_d["eV"].between(*ev_window.value)].copy()
    _d["y"] = np.where(_d["alpha"] > 0, (_d["alpha"] * _d["eV"]) ** _gamma, np.nan)
    _d = _d.replace([np.inf, -np.inf], np.nan)
    _d = _d[np.isfinite(_d["y"]) & np.isfinite(_d["eV"])].copy()
    mo.stop(
        _d.empty,
        mo.md("No finite values for this α source / energy window.").callout(kind="warn"),
    )

    _xdom = [float(ev_window.value[0]), float(ev_window.value[1])]
    _y0, _y1 = float(_d["y"].min()), float(_d["y"].max())
    _pad = 0.05 * (_y1 - _y0) if _y1 > _y0 else 1.0
    _ydom = [min(0.0, _y0), _y1 + _pad]

    _gt = {2.0: "2", 0.5: "1/2", 2 / 3: "2/3", 1 / 3: "1/3"}
    _gamma_txt = _gt.get(_gamma, f"{_gamma:.3g}")
    _ylab = (
        f"(F(R)·hν)^{_gamma_txt} (a.u.)" if _km
        else f"(αhν)^{_gamma_txt}  [(cm⁻¹·eV)^{_gamma_txt}]"
    )

    _x = alt.X("eV:Q", title="Photon energy (eV)", scale=alt.Scale(domain=_xdom, nice=False, clamp=True))
    _y = alt.Y("y:Q", title=_ylab, scale=alt.Scale(domain=_ydom, nice=False, clamp=True))
    _color = alt.Color(
        "sample:N", title="Sample", sort=sample_order,
        scale=alt.Scale(domain=sample_order, scheme="tableau10"),
    )

    # per-sample linear fit of the onset -> E_g, drawn as dashed segment + rule
    _fit_rows, _seg, _rules, _bands = [], [], [], []

    if show_fit.value:
        for _s in sample_order:
            _sub = _d[_d["sample"] == _s]
            if _sub.empty:
                continue
            _slider = fit_windows.value.get(_s)
            if _slider is None:
                continue
            _lo, _hi = float(_slider[0]), float(_slider[1])
            _bands.append({"sample": _s, "eV": _lo, "eV2": _hi, "y": _ydom[0], "y2": _ydom[1]})
            _w = _sub[_sub["eV"].between(_lo, _hi)].sort_values("eV")
            _res = fit_linear(_w["eV"].to_numpy(float), _w["y"].to_numpy(float))
            _row = {"sample": _s, "fit window (eV)": f"{_lo:.2f}–{_hi:.2f}", "n pts": int(len(_w))}
            if _res is None:
                _fit_rows.append({
                    **_row, "E_g (eV)": np.nan, "λ_g (nm)": np.nan, "R²": np.nan,
                    "note": "no valid positive-slope fit — move/widen the window",
                })
                continue

            _eg = _res["E_g"]
            _fit_rows.append({
                **_row,
                "E_g (eV)": round(_eg, 3),
                "λ_g (nm)": round(HC / _eg, 1) if _eg > 0 else np.nan,
                "R²": round(_res["r2"], 4) if np.isfinite(_res["r2"]) else np.nan,
                "note": "",
            })
            for _xx in (float(np.clip(_eg, *_xdom)), float(np.clip(_res["x_max"], *_xdom))):
                _yy = _res["slope"] * _xx + _res["intercept"]
                if np.isfinite(_yy):
                    _seg.append({"sample": _s, "eV": _xx, "y": float(_yy)})
            if _xdom[0] <= _eg <= _xdom[1]:
                _rules.append({"sample": _s, "eV": _eg, "E_g": _eg})

    _layers = []
    if _bands:
        _layers.append(
            alt.Chart(pd.DataFrame(_bands)).mark_rect(opacity=0.09, color="#4c78a8", stroke=None)
            .encode(x=_x, x2="eV2:Q", y=_y, y2="y2:Q")
        )

    _layers.append(alt.Chart(_d).mark_line(strokeWidth=1.9, clip=True).encode(x=_x, y=_y, color=_color))
    _layers.append(
        alt.Chart(_d).mark_circle(size=70, opacity=0).encode(
            x=_x, y=_y, color=_color,
            tooltip=[
                alt.Tooltip("sample:N"),
                alt.Tooltip("eV:Q", title="E (eV)", format=".3f"),
                alt.Tooltip("nm:Q", title="λ (nm)", format=".1f"),
                alt.Tooltip("alpha:Q", title="α / F(R)", format=".4g"),
                alt.Tooltip("y:Q", title="y", format=".4g"),
            ],
        )
    )

    _seg_df = pd.DataFrame(_seg)
    if len(_seg_df):
        _layers.append(
            alt.Chart(_seg_df).mark_line(strokeDash=[6, 4], strokeWidth=1.5, clip=True)
            .encode(x=_x, y=_y, color=_color, detail="sample:N")
        )

    _rule_df = pd.DataFrame(_rules)
    if len(_rule_df):
        _layers.append(
            alt.Chart(_rule_df).mark_rule(strokeDash=[2, 3], opacity=0.85, clip=True)
            .encode(
                x=_x, y=alt.datum(_ydom[0]), y2=alt.datum(_ydom[1]), color=_color,
                tooltip=[alt.Tooltip("sample:N"), alt.Tooltip("E_g:Q", title="E_g (eV)", format=".3f")],
            )
        )

    _sec = conjugate_axis(_xdom, primary="eV")
    if _sec is not None:
        _layers.append(_sec)

    tauc_chart = mo.ui.altair_chart(
        alt.layer(*_layers).resolve_scale(x="shared", y="shared").properties(
            height=440, width="container", title="Tauc plot — sample comparison",
        ),
        chart_selection=False, legend_selection=True,
    )
    tauc_fits = pd.DataFrame(
        _fit_rows, columns=["sample", "E_g (eV)", "λ_g (nm)", "R²", "fit window (eV)", "n pts", "note"]
    )

    mo.vstack([
        tauc_chart,
        mo.ui.table(tauc_fits, selection=None) if len(tauc_fits) else mo.md(
            "_Place the fit window on the linear onset to extract E_g._"
        ),
    ])
    return


if __name__ == "__main__":
    app.run()
