import marimo

__generated_with = "0.23.15"
app = marimo.App(width="medium")


@app.cell
def _():
    return


@app.cell
def _():
    import marimo as mo
    from pathlib import Path
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt

    return Path, mo, np, pd, plt


@app.cell
def _(mo):
    mo.md("""
    # GC chromatogram viewer

    Rows look like `signal1,signal2,MM/DD/YYYY,HH:MM:SS`. Header and blank lines are
    skipped automatically. Time is reconstructed from the row index and the sampling
    rate (estimated from the 1-s-resolution timestamps, or entered manually).
    """)
    return


@app.cell
def _(mo):
    folder = mo.ui.text(value="/Users/ods/Downloads/TCD_file/", label="Data folder", full_width=True)
    pattern = mo.ui.text(value="*.ASC", label="File pattern (glob)")
    mo.vstack([folder, pattern])
    return folder, pattern


@app.cell
def _(Path, folder, mo, pattern):
    data_dir = Path(folder.value).expanduser()
    all_files = sorted(data_dir.glob(pattern.value)) if data_dir.is_dir() else []

    file_select = mo.ui.multiselect(
        options={f.name: str(f) for f in all_files},
        value=[f.name for f in all_files],
        label=f"Files ({len(all_files)} found)",
        full_width=True,
    )

    (
        file_select
        if all_files
        else mo.callout(
            mo.md(f"No files matching `{pattern.value}` in `{data_dir.resolve()}`"),
            kind="warn",
        )
    )
    return


@app.cell(hide_code=True)
def _(np, pd):
    def estimate_rate_hz(ts):
        """Samples/second from 1-s-resolution timestamps.

        Counts rows between the first and last whole-second boundary,
        so partial seconds at the start/end don't bias the estimate.
        """
        if len(ts) < 3 or ts.isna().any():
            return None
        step = ts.diff().dt.total_seconds().to_numpy()
        edges = np.flatnonzero(step > 0)
        if len(edges) < 2:
            return None
        span = (ts.iloc[edges[-1]] - ts.iloc[edges[0]]).total_seconds()
        return (edges[-1] - edges[0]) / span if span > 0 else None

    def read_gc_ascii(path):
        rows = []
        n_header = 0
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                parts = [p.strip() for p in line.split(",")]
                try:
                    a, b = float(parts[0]), float(parts[1])
                except (ValueError, IndexError):
                    if not rows:
                        n_header += 1
                    continue
                stamp = " ".join(parts[2:4]) if len(parts) >= 4 else None
                rows.append((a, b, stamp))

        df = pd.DataFrame(rows, columns=["col1", "col2", "timestamp"])
        df["timestamp"] = pd.to_datetime(
            df["timestamp"], format="%m/%d/%Y %H:%M:%S", errors="coerce"
        )
        df.attrs["n_header"] = n_header
        df.attrs["rate_hz"] = estimate_rate_hz(df["timestamp"])
        return df

    return (read_gc_ascii,)


@app.cell
def _(mo):
    browser = mo.ui.file_browser(multiple=True)
    browser
    return (browser,)


@app.cell
def _(browser, read_gc_ascii):
    traces = {}
    load_errors = {}
    # for _p in file_select.value:
    for _p in browser.value:
        _name = _p.path
        try:
            _df = read_gc_ascii(_name)
            if _df.empty:
                load_errors[_name] = "no numeric data rows found"
            else:
                traces[_name] = _df
        except Exception as _e:
            load_errors[_name] = str(_e)
    return load_errors, traces


@app.cell
def _(load_errors, mo, np, pd, traces):
    _rows = []
    for _name, _df in traces.items():
        _n = len(_df)
        _i = np.arange(_n)
        _d = (_df["col2"] - _df["col1"]).to_numpy(float)
        if _n > 1:
            _slope, _icpt = np.polyfit(_i, _d, 1)
            _resid_sd = np.std(_d - (_slope * _i + _icpt))
        else:
            _slope = _resid_sd = np.nan
        _rate = _df.attrs.get("rate_hz")
        _rows.append(
            {
                "file": _name,
                "header lines": _df.attrs.get("n_header"),
                "points": _n,
                "rate (Hz, est.)": round(_rate, 3) if _rate else None,
                "duration (min)": round(_n / _rate / 60, 2) if _rate else None,
                "col1 min": _df["col1"].min(),
                "col1 max": _df["col1"].max(),
                "col2−col1 slope (/sample)": round(_slope, 2),
                "col2−col1 resid SD": round(_resid_sd, 1),
                "start": _df["timestamp"].iloc[0],
            }
        )

    _items = []
    if _rows:
        _items += [
            mo.ui.table(pd.DataFrame(_rows), selection=None),
            mo.md(
                "_If the col2−col1 residual SD is small compared with the col1 range, "
                "column 2 is just column 1 plus a linear ramp and adds no peak information._"
            ),
        ]
    if load_errors:
        _items.append(
            mo.callout(
                mo.md("\n".join(f"- **{k}**: {v}" for k, v in load_errors.items())),
                kind="danger",
            )
        )
    mo.vstack(_items) if _items else mo.md("_No data loaded._")
    return


@app.cell
def _(mo):
    signal = mo.ui.dropdown(
        options={
            "Column 1": "col1",
            "Column 2": "col2",
            "Column 2 − Column 1": "diff",
        },
        value="Column 1",
        label="Signal (y)",
    )
    rate_override = mo.ui.number(
        start=0, stop=1000, step=0.1, value=0,
        label="Sampling rate, Hz (0 = auto)",
    )
    time_unit = mo.ui.radio(options=["s", "min"], value="min", label="Time unit", inline=True)
    invert = mo.ui.checkbox(label="Invert signal")
    normalize = mo.ui.checkbox(label="Normalize each trace (max |y| = 1)")
    interactive = mo.ui.checkbox(value=True, label="Interactive (zoom/pan)")
    offset = mo.ui.slider(
        start=0, stop=1, step=0.01, value=0, label="Vertical offset (fraction of max)"
    )

    mo.vstack(
        [
            mo.hstack([signal, rate_override, time_unit], justify="start"),
            mo.hstack([invert, normalize, interactive], justify="start"),
            offset,
        ]
    )
    return (
        interactive,
        invert,
        normalize,
        offset,
        rate_override,
        signal,
        time_unit,
    )


@app.cell
def _(
    interactive,
    invert,
    mo,
    normalize,
    np,
    offset,
    plt,
    rate_override,
    signal,
    time_unit,
    traces,
):
    def _get_y(df):
        if signal.value == "diff":
            y = (df["col2"] - df["col1"]).to_numpy(float)
        else:
            y = df[signal.value].to_numpy(float)
        return -y if invert.value else y

    _ys = {name: _get_y(df) for name, df in traces.items()}
    _global_max = max((np.nanmax(np.abs(y)) for y in _ys.values()), default=1.0)
    _step = offset.value * (1.0 if normalize.value else _global_max)

    _fig, _ax = plt.subplots(figsize=(10, 5))
    _all_timed = True

    for _k, (_name, _df) in enumerate(traces.items()):
        _rate = rate_override.value or _df.attrs.get("rate_hz")
        if _rate:
            _t = np.arange(len(_df)) / _rate
            if time_unit.value == "min":
                _t = _t / 60
        else:
            _t = np.arange(len(_df))
            _all_timed = False

        _y = _ys[_name]
        if normalize.value:
            _m = np.nanmax(np.abs(_y))
            if _m:
                _y = _y / _m
        _ax.plot(_t, _y + _k * _step, lw=1, label=_name)

    _ax.set_xlabel(f"Time ({time_unit.value})" if _all_timed else "Time / sample index (rate unknown for some files)")
    _ax.set_ylabel(
        signal.selected_key
        + (" (inverted)" if invert.value else "")
        + (" (normalized)" if normalize.value else "")
    )
    if traces:
        if len(traces) <= 10:
            _ax.legend(fontsize="small")
        else:
            _ax.legend(fontsize="x-small", bbox_to_anchor=(1.02, 1), loc="upper left")
    _fig.tight_layout()

    mo.mpl.interactive(_fig) if interactive.value else _fig
    return


@app.cell
def _():
    return


@app.cell
def _(invert, np, rate_override, signal):
    def gc_signal(df):
        """(t in seconds or None if rate unknown, y) using the current plot settings.
        Normalize/offset are display-only and deliberately not applied here."""
        if signal.value == "diff":
            y = (df["col2"] - df["col1"]).to_numpy(float)
        else:
            y = df[signal.value].to_numpy(float)
        if invert.value:
            y = -y
        rate = rate_override.value or df.attrs.get("rate_hz")
        t = np.arange(len(df)) / rate if rate else None
        return t, y

    def integrate_window(t, y, t0, t1, baseline="linear", n_edge=3):
        """Integrate y over [t0, t1] after subtracting a baseline.

        baseline: 'linear' = straight line between the mean of n_edge points
                  at each window edge; 'flat' = constant at the start-edge mean;
                  'zero' = no baseline subtraction.
        """
        trapz = getattr(np, "trapezoid", None) or np.trapz  # numpy 2 / 1
        i0 = int(np.searchsorted(t, t0, side="left"))
        i1 = int(np.searchsorted(t, t1, side="right")) - 1
        if i1 - i0 < 2:
            return None
        tw, yw = t[i0 : i1 + 1], y[i0 : i1 + 1]
        k = int(max(1, min(n_edge, len(tw) // 4)))
        ta, tb = tw[:k].mean(), tw[-k:].mean()
        ya, yb = yw[:k].mean(), yw[-k:].mean()
        if baseline == "linear":
            base = ya + (yb - ya) * (tw - ta) / (tb - ta)
        elif baseline == "flat":
            base = np.full_like(yw, ya)
        else:
            base = np.zeros_like(yw)

        yc = yw - base
        j = int(np.argmax(np.abs(yc)))
        h = yc[j]

        # FWHM from linearly interpolated half-height crossings
        fwhm = np.nan
        if h != 0:
            above = (yc / h) >= 0.5
            l = j
            while l > 0 and above[l - 1]:
                l -= 1
            r = j
            while r < len(yc) - 1 and above[r + 1]:
                r += 1
            if l > 0 and r < len(yc) - 1:
                def cross(a, b):
                    fa, fb = yc[a] / h - 0.5, yc[b] / h - 0.5
                    return tw[a] + (tw[b] - tw[a]) * fa / (fa - fb)
                fwhm = cross(r, r + 1) - cross(l - 1, l)

        return dict(
            t=tw, y=yw, base=base,
            area=float(trapz(yc, tw)),
            height=float(h), apex=float(tw[j]), apex_y=float(yw[j]),
            fwhm=float(fwhm), n=len(tw),
            apex_at_edge=j in (0, len(tw) - 1),
            edge_step=float(yb - ya),
        )

    return gc_signal, integrate_window


@app.cell
def _(mo):
    peak_text = mo.ui.text_area(
        value=(
            "# One peak per line: name, start, end\n"
            "# Times are in the unit chosen under Plot options (s or min).\n"
            "# Example:\n"
            "# H2, 0.40, 0.65\n"
        ),
        label="Peak windows",
        rows=8,
        full_width=True,
    )
    baseline_mode = mo.ui.dropdown(
        options={
            "Linear between window edges": "linear",
            "Flat at window start": "flat",
            "Zero (no baseline)": "zero",
        },
        value="Linear between window edges",
        label="Baseline",
    )
    n_edge = mo.ui.number(start=1, stop=50, step=1, value=3, label="Points averaged at each edge")
    mo.vstack(
        [
            mo.md("## Peak integration"),
            peak_text,
            mo.hstack([baseline_mode, n_edge], justify="start"),
        ]
    )
    return baseline_mode, n_edge, peak_text


@app.cell
def _(peak_text):
    peak_windows = []
    peak_parse_errors = []
    _seen = set()
    for _ln, _raw in enumerate(peak_text.value.splitlines(), 1):
        _line = _raw.split("#")[0].strip()
        if not _line:
            continue
        _parts = [p.strip() for p in _line.split(",")]
        try:
            if len(_parts) != 3 or not _parts[0]:
                raise ValueError
            _name, _a, _b = _parts[0], float(_parts[1]), float(_parts[2])
        except ValueError:
            peak_parse_errors.append(f"line {_ln}: `{_line}` (expected: name, start, end)")
            continue
        if _name in _seen:
            peak_parse_errors.append(f"line {_ln}: duplicate peak name `{_name}`")
            continue
        _seen.add(_name)
        peak_windows.append((_name, min(_a, _b), max(_a, _b)))
    return peak_parse_errors, peak_windows


@app.cell
def _(
    baseline_mode,
    gc_signal,
    integrate_window,
    n_edge,
    np,
    pd,
    peak_windows,
    time_unit,
    traces,
):
    _u = time_unit.value
    _scale = 60.0 if _u == "min" else 1.0
    _cols = [
        "file", "peak", f"start ({_u})", f"end ({_u})", f"apex ({_u})",
        "height", "area (signal·s)", "FWHM (s)", "points", "flags",
    ]
    peak_fits = {}
    _rows = []
    for _file, _df in traces.items():
        _t, _y = gc_signal(_df)
        _timed = _t is not None
        if not _timed:
            _t = np.arange(len(_y), dtype=float)
        _ws = _scale if _timed else 1.0
        for _name, _a, _b in peak_windows:
            _r = integrate_window(
                _t, _y, _a * _ws, _b * _ws, baseline_mode.value, int(n_edge.value)
            )
            _row = {"file": _file, "peak": _name, f"start ({_u})": _a, f"end ({_u})": _b}
            _flags = [] if _timed else ["no sampling rate: x/area/FWHM in samples"]
            if _r is None:
                _flags.append("window outside data or < 3 points")
            else:
                peak_fits[(_file, _name)] = _r
                if _r["apex_at_edge"]:
                    _flags.append("apex at window edge")
                if np.isnan(_r["fwhm"]):
                    _flags.append("half-height not reached on both sides")
                if abs(_r["edge_step"]) > 0.1 * abs(_r["height"]):
                    _flags.append("baseline step >10% of height")
                if _r["n"] < 10:
                    _flags.append("<10 points")
                _row.update(
                    {
                        f"apex ({_u})": _r["apex"] / _ws,
                        "height": _r["height"],
                        "area (signal·s)": _r["area"],
                        "FWHM (s)": _r["fwhm"],
                        "points": _r["n"],
                    }
                )
            _row["flags"] = "; ".join(_flags)
            _rows.append(_row)
    peak_results_df = pd.DataFrame(_rows, columns=_cols)
    return peak_fits, peak_results_df


@app.cell
def _():
    # _scale = 60.0 if time_unit.value == "min" else 1.0
    # _ends = []
    # for _df in traces.values():
    #     _t, _y = gc_signal(_df)
    #     _ends.append(_t[-1] / _scale if _t is not None else len(_y) - 1)
    # _tmax = float(max(_ends, default=1.0)) or 1.0
    # _names = list(traces)

    # preview_file = mo.ui.dropdown(
    #     options=_names, value=_names[0] if _names else None, label="Preview file"
    # )
    # preview_range = mo.ui.range_slider(
    #     start=0, stop=_tmax, step=_tmax / 2000, value=[0, _tmax],
    #     label=f"Zoom ({time_unit.value})", show_value=True, full_width=True,
    # )
    # overlay_all = mo.ui.checkbox(label="Overlay other selected files (grey)")
    # mo.vstack([mo.hstack([preview_file, overlay_all], justify="start"), preview_range])
    return


@app.cell
def _():
    import altair as alt
    alt.data_transformers.disable_max_rows()
    return (alt,)


@app.cell
def _(mo, traces):
    _names = list(traces)
    preview_file = mo.ui.dropdown(
        options=_names, value=_names[0] if _names else None, label="Preview file"
    )
    overlay_all = mo.ui.checkbox(label="Overlay other selected files (grey)")
    show_cursor = mo.ui.checkbox(value=True, label="Cursor readout")
    max_pts = mo.ui.number(
        start=500, stop=50000, step=500, value=4000, label="Max points per trace (display)"
    )
    mo.hstack([preview_file, overlay_all, show_cursor, max_pts], justify="start")
    return max_pts, overlay_all, preview_file, show_cursor


@app.cell
def _(
    alt,
    gc_signal,
    max_pts,
    mo,
    np,
    overlay_all,
    pd,
    peak_fits,
    peak_windows,
    preview_file,
    show_cursor,
    signal,
    time_unit,
    traces,
):
    def _thin(t, y):
        """Min/max decimation for display: keeps peak extremes, caps point count."""
        n, m = len(t), int(max_pts.value)
        if n <= m:
            return t, y
        k = int(np.ceil(n / max(1, m // 2)))
        nb = n // k
        tb, yb = t[: nb * k].reshape(nb, k), y[: nb * k].reshape(nb, k)
        i1, i2 = yb.argmin(1), yb.argmax(1)
        lo, hi = np.minimum(i1, i2), np.maximum(i1, i2)
        r = np.arange(nb)
        tt = np.column_stack([tb[r, lo], tb[r, hi]]).ravel()
        yy = np.column_stack([yb[r, lo], yb[r, hi]]).ravel()
        return np.concatenate([tt, t[nb * k :]]), np.concatenate([yy, y[nb * k :]])

    if not traces or preview_file.value is None:
        _out = mo.md("_No files selected._")
    else:
        _scale = 60.0 if time_unit.value == "min" else 1.0

        def _xy(df):
            t, y = gc_signal(df)
            if t is None:
                return np.arange(len(y), dtype=float), y, False
            return t / _scale, y, True

        _t, _y, _timed = _xy(traces[preview_file.value])
        _ws = _scale if _timed else 1.0
        _xtitle = f"Time ({time_unit.value})" if _timed else "Sample index"
        _ytitle = signal.selected_key

        _tt, _yy = _thin(_t, _y)
        _main = pd.DataFrame({"t": _tt, "y": _yy})
        _x = alt.X("t:Q", title=_xtitle)
        _yenc = alt.Y("y:Q", title=_ytitle)
        _layers = []

        # Grey overlay of the other selected files
        if overlay_all.value:
            _ov = []
            for _f, _d in traces.items():
                if _f == preview_file.value:
                    continue
                _to, _yo, _ = _xy(_d)
                _to, _yo = _thin(_to, _yo)
                _ov.append(pd.DataFrame({"t": _to, "y": _yo, "file": _f}))
            if _ov:
                _layers.append(
                    alt.Chart(pd.concat(_ov, ignore_index=True))
                    .mark_line(strokeWidth=1, color="lightgrey")
                    .encode(_x, _yenc, detail="file:N")
                )

        # Window bands, shaded areas, baselines
        if peak_windows:
            _order = [w[0] for w in peak_windows]
            _col = alt.Color(
                "peak:N",
                scale=alt.Scale(domain=_order, scheme="category10"),
                legend=alt.Legend(title="Peak"),
            )
            _win = pd.DataFrame(peak_windows, columns=["peak", "start", "end"])
            _layers.append(
                alt.Chart(_win)
                .mark_rect(opacity=0.08)
                .encode(x=alt.X("start:Q", title=_xtitle), x2="end:Q", color=_col)
            )
            _layers.append(
                alt.Chart(_win)
                .mark_text(align="left", baseline="top", dx=3, dy=3, fontSize=11)
                .encode(x=alt.X("start:Q", title=_xtitle), y=alt.value(0), text="peak:N", color=_col)
            )

            _fits = []
            for _name in _order:
                _fit = peak_fits.get((preview_file.value, _name))
                if _fit is not None:
                    _fits.append(
                        pd.DataFrame(
                            {
                                "t": _fit["t"] / _ws,
                                "y": _fit["y"],
                                "base": _fit["base"],
                                "peak": _name,
                                "area": _fit["area"],
                            }
                        )
                    )
            if _fits:
                _fd = pd.concat(_fits, ignore_index=True)
                _layers.append(
                    alt.Chart(_fd)
                    .mark_area(opacity=0.35)
                    .encode(
                        x=_x,
                        y=_yenc,
                        y2="base:Q",
                        color=_col,
                        tooltip=["peak:N", alt.Tooltip("area:Q", format=".4g")],
                    )
                )
                _layers.append(
                    alt.Chart(_fd)
                    .mark_line(strokeDash=[4, 3], strokeWidth=1)
                    .encode(x=_x, y=alt.Y("base:Q", title=_ytitle), color=_col, detail="peak:N")
                )

        # Main trace, with x-axis zoom/pan (drag to pan, scroll to zoom, double-click to reset)
        _zoom = alt.selection_interval(bind="scales", encodings=["x"])
        _layers.append(
            alt.Chart(_main)
            .mark_line(color="black", strokeWidth=1.2)
            .encode(_x, _yenc)
            .add_params(_zoom)
        )

        # Cursor readout: vertical rule + "t, y" label at the nearest point
        if show_cursor.value:
            _hover = alt.selection_point(
                fields=["t"], nearest=True, on="mouseover", clear="mouseout", empty=False
            )
            _base = alt.Chart(_main).encode(_x)
            _layers.append(_base.mark_point(opacity=0).encode(_yenc).add_params(_hover))
            _layers.append(
                _base.mark_rule(color="grey", strokeWidth=1).transform_filter(_hover)
            )
            _layers.append(
                _base.mark_text(align="left", dx=6, dy=-8, fontSize=11)
                .encode(_yenc)
                .transform_calculate(
                    label="format(datum.t, '.3f') + ', ' + format(datum.y, '.0f')"
                )
                .encode(text="label:N")
                .transform_filter(_hover)
            )

        _out = alt.layer(*_layers).properties(width="container", height=420)
    _out
    return


@app.cell
def _(mo, pd, peak_parse_errors, peak_results_df, peak_windows):
    _items = []
    if peak_parse_errors:
        _items.append(
            mo.callout(mo.md("**Could not parse:**\n\n" + "\n".join(f"- {e}" for e in peak_parse_errors)), kind="danger")
        )
    if not peak_windows:
        _items.append(mo.md("_Add peak windows above (name, start, end) to integrate._"))
    elif peak_results_df.empty:
        _items.append(mo.md("_No files selected._"))
    else:
        _order = [w[0] for w in peak_windows]
        _area = "area (signal·s)"
        _apex = [c for c in peak_results_df.columns if c.startswith("apex")][0]

        _wide = (
            peak_results_df.pivot_table(index="file", columns="peak", values=_area, aggfunc="first", sort=False)
            .reindex(columns=_order)
            .reset_index()
        )

        _g = peak_results_df.groupby("peak", sort=False)
        _stats = pd.DataFrame(
            {
                "n": _g[_area].count(),
                "mean area": _g[_area].mean(),
                "SD area": _g[_area].std(ddof=1),
                f"mean {_apex}": _g[_apex].mean(),
                f"SD {_apex}": _g[_apex].std(ddof=1),
                "mean FWHM (s)": _g["FWHM (s)"].mean(),
            }
        ).reindex(_order)
        _stats.insert(3, "RSD area (%)", 100 * _stats["SD area"] / _stats["mean area"].abs())

        _n_flag = int((peak_results_df["flags"] != "").sum())
        if _n_flag:
            _items.append(
                mo.callout(f"{_n_flag} integration(s) flagged — check the 'flags' column.", kind="warn")
            )
        _items.append(
            mo.ui.tabs(
                {
                    "Per peak": mo.ui.table(peak_results_df, selection=None, page_size=25),
                    "Areas (file × peak)": mo.ui.table(_wide, selection=None, page_size=25),
                    "Repeatability": mo.ui.table(_stats.reset_index(), selection=None),
                }
            )
        )
    mo.vstack(_items)
    return


@app.cell
def _(mo, traces):

    # To keep your groups in the file, paste the final text here as a
    # triple-quoted string, e.g. _saved_spec = """Blank, 3\nSample A, 4"""
    _saved_spec = None

    _n = len(traces)
    _lines = [
        "# One group per line: label, number of injections",
        "# Groups are assigned consecutively in run order.",
        "# Label 'skip' drops injections; repeating a label pools them.",
    ]
    _lines += [f"G{_i + 1}, {min(3, _n - 3 * _i)}" for _i in range((_n + 2) // 3)]
    default_group_spec = _saved_spec if _saved_spec is not None else "\n".join(_lines)

    group_order_by = mo.ui.dropdown(
        options={"Start time": "start", "Filename": "file"},
        value="Start time",
        label="Run order",
    )
    group_form = mo.ui.text_area(
        value=default_group_spec,
        label="Groups",
        rows=min(20, default_group_spec.count("\n") + 3),
        full_width=True,
    ).form(submit_button_label="Apply groups", clear_on_submit=False)

    mo.vstack([mo.md("## Replicate groups"), group_order_by, group_form])

    return default_group_spec, group_form, group_order_by


@app.cell
def _(default_group_spec, group_form, group_order_by, mo, np, pd, traces):
    _spec = group_form.value if group_form.value is not None else default_group_spec

    # Run-order table built directly from the loaded traces: one row per file,
    # with the first timestamp in each file as its start time.
    _ord = pd.DataFrame(
        {
            "file": list(traces),
            "start": [_df["timestamp"].iloc[0] for _df in traces.values()],
        }
    )
    _keys = ["start", "file"] if group_order_by.value == "start" else ["file"]
    _ord = _ord.sort_values(_keys, na_position="last").reset_index(drop=True)

    _groups, group_errors = [], []
    for _ln, _raw in enumerate(_spec.splitlines(), 1):
        _line = _raw.split("#")[0].strip()
        if not _line:
            continue
        _parts = [p.strip() for p in _line.rsplit(",", 1)]  # labels may contain commas
        try:
            if len(_parts) != 2 or not _parts[0]:
                raise ValueError
            _count = int(_parts[1])
            if _count < 1:
                raise ValueError
        except ValueError:
            group_errors.append(f"line {_ln}: `{_line}` (expected: label, count ≥ 1)")
            continue
        _groups.append((_parts[0], _count))

    _labels = [lab for lab, c in _groups for _ in range(c)]
    _n = len(_ord)
    if len(_labels) < _n:
        group_errors.append(
            f"Groups cover {len(_labels)} injections but {_n} files are selected: "
            f"the last {_n - len(_labels)} are unassigned."
        )
    elif len(_labels) > _n:
        group_errors.append(
            f"Groups cover {len(_labels)} injections but only {_n} files are selected: "
            f"the extra {len(_labels) - _n} slots are ignored."
        )
    _labels = (_labels + [None] * _n)[:_n]

    group_assign_df = _ord.assign(run=np.arange(1, _n + 1), group=_labels)[
        ["run", "file", "start", "group"]
    ]
    _skip = group_assign_df["group"].fillna("").str.lower().isin(["", "skip"])
    group_assign_df["rep"] = (
        (group_assign_df.groupby("group", dropna=False).cumcount() + 1)
        .where(~_skip)
        .astype("Int64")
    )
    group_order = list(dict.fromkeys(lab for lab, _ in _groups if lab.lower() != "skip"))

    _sizes = group_assign_df[~_skip].groupby("group", sort=False).size()
    _items = [
        mo.md(
            f"**{len(group_order)}** group(s): "
            + ", ".join(f"`{g}` (n={_sizes.get(g, 0)})" for g in group_order)
        )
    ]
    if group_errors:
        _items.append(
            mo.callout(mo.md("\n".join(f"- {e}" for e in group_errors)), kind="warn")
        )
    _items.append(mo.ui.table(group_assign_df, selection=None, page_size=25))
    mo.vstack(_items)
    return group_assign_df, group_order


@app.cell
def _(mo):
    area_value = mo.ui.dropdown(
        options={"Area": "area (signal·s)", "Height": "height"},
        value="Area",
        label="Quantity",
    )
    err_mode = mo.ui.dropdown(
        options={"SD": "sd", "SEM": "sem", "95% CI": "ci95", "None": "none"},
        value="SD",
        label="Error bars",
    )
    drop_flagged = mo.ui.checkbox(label="Exclude flagged integrations")
    show_points = mo.ui.checkbox(value=True, label="Show individual injections")
    bar_layout = mo.ui.radio(
        options={"Grouped": "grouped", "One panel per peak": "facet"},
        value="Grouped",
        label="Layout",
        inline=True,
    )
    mo.vstack(
        [
            mo.md("## Group averages"),
            mo.hstack([area_value, err_mode, bar_layout], justify="start"),
            mo.hstack([drop_flagged, show_points], justify="start"),
        ]
    )
    return area_value, bar_layout, drop_flagged, err_mode, show_points


@app.cell
def _(
    area_value,
    drop_flagged,
    err_mode,
    group_assign_df,
    group_order,
    np,
    peak_results_df,
    peak_windows,
):
    def _tcrit(dof):
        dof = np.asarray(dof, dtype=float)
        try:
            from scipy.stats import t
            return t.ppf(0.975, dof)
        except ImportError:
            table = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
                     6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228}
            return np.array([table.get(int(d), 1.96) if d >= 1 else np.nan for d in dof])

    _v = area_value.value
    _peaks = [w[0] for w in peak_windows]

    _d = peak_results_df.merge(
        group_assign_df[["file", "run", "group", "rep"]], on="file", how="inner"
    )
    _d = _d[_d["group"].isin(group_order)]
    if drop_flagged.value:
        _d = _d[_d["flags"].fillna("") == ""]
    group_inj_df = (
        _d[["group", "rep", "run", "file", "peak", _v, "flags"]]
        .rename(columns={_v: "value"})
        .dropna(subset=["value"])
        .reset_index(drop=True)
    )
    group_inj_df["rep"] = group_inj_df["rep"].astype(int)

    group_stats_df = (
        group_inj_df.groupby(["group", "peak"], sort=False)["value"]
        .agg(n="count", mean="mean", sd="std")
        .reset_index()
    )
    group_stats_df["sem"] = group_stats_df["sd"] / np.sqrt(group_stats_df["n"])
    group_stats_df["ci95"] = group_stats_df["sem"] * _tcrit(group_stats_df["n"] - 1)
    group_stats_df["rsd_pct"] = 100 * group_stats_df["sd"] / group_stats_df["mean"].abs()
    _e = 0.0 if err_mode.value == "none" else group_stats_df[err_mode.value].fillna(0)
    group_stats_df["lo"] = group_stats_df["mean"] - _e
    group_stats_df["hi"] = group_stats_df["mean"] + _e

    _gi = {g: i for i, g in enumerate(group_order)}
    _pi = {p: i for i, p in enumerate(_peaks)}
    group_stats_df = group_stats_df.sort_values(
        ["group", "peak"], key=lambda s: s.map(_gi if s.name == "group" else _pi)
    ).reset_index(drop=True)
    return group_inj_df, group_stats_df


@app.cell
def _(group_inj_df, group_order, group_stats_df, mo, peak_windows):
    if group_stats_df.empty:
        _out = mo.md("_No grouped results yet: need peak windows, selected files and groups._")
    else:
        _peaks = [w[0] for w in peak_windows]
        _txt = group_stats_df.assign(
            txt=lambda d: d.apply(
                lambda r: f"{r['mean']:.4g} ± {r['sd']:.2g} (n={r['n']})"
                if r["n"] > 1 else f"{r['mean']:.4g} (n=1)",
                axis=1,
            )
        )
        _wide = (
            _txt.pivot(index="group", columns="peak", values="txt")
            .reindex(index=group_order, columns=_peaks)
            .reset_index()
        )
        _mean_wide = (
            group_stats_df.pivot(index="group", columns="peak", values="mean")
            .reindex(index=group_order, columns=_peaks)
            .reset_index()
        )
        _items = []
        _low_n = group_stats_df[group_stats_df["n"] < 2]
        if len(_low_n):
            _items.append(
                mo.callout(
                    f"{len(_low_n)} group/peak combination(s) have n < 2 (no SD).",
                    kind="warn",
                )
            )
        _items.append(
            mo.ui.tabs(
                {
                    "Mean ± SD": mo.ui.table(_wide, selection=None),
                    "Means (numeric)": mo.ui.table(_mean_wide, selection=None),
                    "Stats (long)": mo.ui.table(
                        group_stats_df.drop(columns=["lo", "hi"]), selection=None, page_size=25
                    ),
                    "Per injection": mo.ui.table(group_inj_df, selection=None, page_size=25),
                }
            )
        )
        _out = mo.vstack(_items)
    _out
    return


@app.cell
def _(
    alt,
    area_value,
    bar_layout,
    err_mode,
    group_inj_df,
    group_order,
    group_stats_df,
    mo,
    peak_windows,
    show_points,
):
    if group_stats_df.empty:
        _out = mo.md("_Nothing to plot yet._")
    else:
        _peaks = [w[0] for w in peak_windows]
        _ytitle = "Area (signal·s)" if area_value.value.startswith("area") else "Height"
        _color = alt.Color(
            "peak:N",
            scale=alt.Scale(domain=_peaks, scheme="category10"),
            legend=alt.Legend(title="Peak"),
        )
        _tip = [
            "group:N", "peak:N", "n:Q",
            alt.Tooltip("mean:Q", format=".4g"),
            alt.Tooltip("sd:Q", format=".3g"),
            alt.Tooltip("rsd_pct:Q", title="RSD %", format=".2f"),
        ]

        def _panel(stats, inj, offset, title=None):
            enc = {"x": alt.X("group:N", sort=group_order, title=None,
                              axis=alt.Axis(labelAngle=-30))}
            if offset:
                enc["xOffset"] = alt.XOffset("peak:N", sort=_peaks)
            base = alt.Chart(stats).encode(**enc)
            layers = [
                base.mark_bar().encode(
                    y=alt.Y("mean:Q", title=_ytitle), color=_color, tooltip=_tip
                )
            ]
            if err_mode.value != "none":
                layers += [
                    base.mark_rule(color="black").encode(
                        y=alt.Y("lo:Q", title=_ytitle), y2="hi:Q"
                    ),
                    base.mark_tick(color="black", thickness=1.5, size=8).encode(
                        y=alt.Y("lo:Q", title=_ytitle)
                    ),
                    base.mark_tick(color="black", thickness=1.5, size=8).encode(
                        y=alt.Y("hi:Q", title=_ytitle)
                    ),
                ]
            if show_points.value and not inj.empty:
                layers.append(
                    alt.Chart(inj)
                    .mark_circle(color="black", size=18, opacity=0.7)
                    .encode(
                        **enc,
                        y=alt.Y("value:Q", title=_ytitle),
                        tooltip=["file:N", "group:N", "rep:Q",
                                 alt.Tooltip("value:Q", format=".4g")],
                    )
                )
            ch = alt.layer(*layers)
            return ch.properties(title=title) if title else ch

        if bar_layout.value == "grouped":
            _out = _panel(group_stats_df, group_inj_df, True).properties(height=380)
        else:
            _charts = [
                _panel(
                    group_stats_df[group_stats_df["peak"] == p],
                    group_inj_df[group_inj_df["peak"] == p],
                    False,
                    title=p,
                ).properties(height=280)
                for p in _peaks
                if (group_stats_df["peak"] == p).any()
            ]
            _out = alt.concat(*_charts, columns=3).resolve_scale(y="independent")
    _out
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
