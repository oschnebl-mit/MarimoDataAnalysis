import marimo

__generated_with = "0.25.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import matplotlib
    import matplotlib.pyplot as plt
    import pandas as pd
    import numpy as np
    import re
    from datetime import datetime as dt

    return dt, matplotlib, mo, np, pd, plt, re


@app.cell
def _(mo):
    mo.md("""
    # Cryo Temperature Comparison

    Compares the two measured temperatures (`Cryo Temperature`,
    `Reaction Temperature`) against a temperature estimated by inverting
    the H2S Antoine equation using the measured `Reaction Pressure`.
    """)
    return


@app.cell
def _(np):
    A_h2s = 4.43681
    B_h2s = 829.439
    C_h2s = -25.412

    def Antoine(A, B, C, T):
        ## takes temperature in kelvin, returns pressure in Torr
        log10P = A - B / (T + C)
        Pbar = 10**log10P
        Ptorr = 750 * Pbar
        return Ptorr

    def Antoine_T_from_P(A, B, C, P_torr):
        ## inverse of Antoine: takes pressure in Torr, returns temperature in kelvin
        log10P_bar = np.log10(P_torr / 750)
        return B / (A - log10P_bar) - C

    templist = np.linspace(50, 250)
    psat_h2s = Antoine(A_h2s, B_h2s, C_h2s, templist)
    return A_h2s, Antoine_T_from_P, B_h2s, C_h2s, psat_h2s, templist


@app.cell
def _(A_h2s, Antoine_T_from_P, B_h2s, C_h2s, pd):
    def load_and_augment(path):
        df = pd.read_csv(path)
        time = pd.to_datetime(df["DateTime"])
        df["Estimated Temperature"] = Antoine_T_from_P(
            A_h2s, B_h2s, C_h2s, df["Reaction Pressure"]
        )
        return df, time

    return (load_and_augment,)


@app.cell
def _(re):
    def label_from_filename(name):
        ## name should be the bare filename (no directory), e.g. from file_info.name
        m = re.search(r"(\d{8}-\d{6})", name)
        if m:
            return m.group(1)
        return name.rsplit(".", 1)[0]

    return (label_from_filename,)


@app.cell
def _(mo):
    mo.md("""
    ## Single-file explorer
    """)
    return


@app.cell
def _(mo):
    browser = mo.ui.file_browser(initial_path=r"C:\Users\oschn\MIT Dropbox\Olivia Schneble\jaramillogroupshared\Data", filetypes=[".csv"], multiple=False, label="Select a CSV file")
    browser
    return (browser,)


@app.cell
def _(browser, load_and_augment, mo):
    mo.stop(not browser.value, mo.md("Select a CSV file above to begin."))

    filepath = browser.value[0].path
    df, time = load_and_augment(filepath)
    unix_time = time.astype("int64") // 1e9
    xrange = mo.ui.range_slider(
        start=unix_time.iloc[0],
        stop=unix_time.iloc[-1],
        step=30,
        label="Time Range",
        full_width=True,
    )
    return df, time, xrange


@app.cell
def _(xrange):
    xrange
    return


@app.cell
def _(df, dt, pd, plt, time, xrange):
    fig, (ax1, ax2, ax4) = plt.subplots(3, 1, sharex=True)
    plt.xticks(rotation=45)

    F1 = df["H2S sccm"]
    F2 = df["Ar sccm"]
    P1 = df["Reaction Pressure"]
    Tcryo = df["Cryo Temperature"]
    Trxn = df["Reaction Temperature"]
    Test = df["Estimated Temperature"]

    ax1.plot(time, F1, marker=".", color="darkblue", label="H2S sccm")
    ax1.plot(time, F2, marker=".", color="lightblue", label="Ar sccm")

    ax2.plot(time, P1, color="tab:orange", label="Rxn")

    ax4.plot(time, Tcryo, color="red", label="Cryo Temp")
    ax4.plot(time, Trxn, color="pink", label="Reaction Temp")
    ax4.plot(time, Test, color="goldenrod", label="Estimated Temp")

    ax1.set_ylabel("Flow (sccm)")
    ax2.set_ylabel("Pressure (Torr)")
    ax4.set_ylabel("Temperature (K)")
    ax1.legend()
    ax2.legend()
    ax4.legend()

    ax1.grid(visible=True)
    ax2.grid(visible=True)
    ax4.grid(visible=True)

    timestart = dt.utcfromtimestamp(xrange.value[0])
    timestop = dt.utcfromtimestamp(xrange.value[1])
    mask = (time >= timestart) & (time <= timestop)

    if mask.any():
        ax1.set_xlim(timestart, timestop)

        yvals1 = pd.concat([F1[mask], F2[mask]])
        ax1.set_ylim(-0.1, yvals1.max() * 1.1)

        ax2.set_ylim(P1[mask].min() * 0.9, P1[mask].max() * 1.1)

        yvals4 = pd.concat([Tcryo[mask], Trxn[mask], Test[mask]])
        ax4.set_ylim(yvals4.min() * 0.9, yvals4.max() * 1.1)
    return P1, Tcryo, fig, mask


@app.cell
def _(fig):
    fig
    return


@app.cell
def _(P1, Tcryo, mask, plt, psat_h2s, templist):
    fig2, ptax = plt.subplots(1, 1)

    ptax.plot(templist, psat_h2s, color="goldenrod", label="Psat H2S")

    if mask.any():
        ptax.scatter(
            Tcryo[mask], P1[mask], label="Reaction Pressure", color="lightblue", marker="."
        )
        ptax.set_ylim(P1[mask].min() * 0.9, P1[mask].max() * 1.1)
        ptax.set_xlim(Tcryo[mask].min() * 0.9, Tcryo[mask].max() * 1.1)
    else:
        ptax.scatter(Tcryo, P1, color="lightblue", marker=".")

    ptax.grid(visible=True)
    ptax.set_xlabel("Cryo Temperature (K)")
    ptax.set_ylabel("Reaction Pressure (Torr)")
    ptax.legend()
    return (fig2,)


@app.cell
def _(fig2):
    fig2
    return


@app.cell
def _(mo):
    mo.md("""
    ## Multi-file comparison
    """)
    return


@app.cell
def _(mo):
    multi_browser = mo.ui.file_browser(initial_path=r"C:\Users\oschn\MIT Dropbox\Olivia Schneble\jaramillogroupshared\Data\Jaramillo lab\CryoEchem\raw_logs",
        filetypes=[".csv"], multiple=True, selection_mode="file", label="Select CSV file(s)"
    )
    multi_browser
    return (multi_browser,)


@app.cell
def _(label_from_filename, load_and_augment, mo, multi_browser):
    mo.stop(not multi_browser.value, mo.md("Select one or more CSV files above."))

    multi_data = {}
    for _file_info in multi_browser.value:
        _label = label_from_filename(_file_info.name)
        _df, _time = load_and_augment(_file_info.path)
        multi_data[_label] = (_df, _time)

    run_labels = sorted(multi_data.keys())
    return multi_data, run_labels


@app.cell
def _(mo):
    mo.md("""
    Select the time range to analyze for each run (defaults to the full
    file), same as the single-file explorer above.
    """)
    return


@app.cell
def _(mo, multi_data, run_labels):
    range_sliders_dict = mo.ui.dictionary(
        {_label: mo.ui.range_slider(
                start=multi_data[_label][1].astype("int64").iloc[0] // 1e9,
                stop=multi_data[_label][1].astype("int64").iloc[-1] // 1e9,
                step=30,
                label=_label,
                full_width=True,
            )
            for _label in run_labels }
    )
    range_sliders_dict.vstack()
    return (range_sliders_dict,)


@app.cell
def _(dt, multi_data, range_sliders_dict, run_labels):
    runs = {}
    for _label in run_labels:
        _df, _time = multi_data[_label]
        _tstart = dt.utcfromtimestamp(range_sliders_dict[_label].value[0])
        _tstop = dt.utcfromtimestamp(range_sliders_dict[_label].value[1])
        _mask = (_time >= _tstart) & (_time <= _tstop)
        _sub = _df[_mask].copy()
        _sub["Time"] = _time[_mask]
        _sub["Time since start (min)"] = (_sub["Time"] - _tstart).dt.total_seconds() / 60
        runs[_label] = _sub
    return (runs,)


@app.cell
def _(matplotlib, run_labels):
    palette = matplotlib.colormaps["tab10" if len(run_labels) <= 10 else "tab20"]
    run_colors = {label: palette(i % palette.N) for i, label in enumerate(run_labels)}
    return (run_colors,)


@app.cell
def _(np, pd, plt, psat_h2s, run_colors, run_labels, runs, templist):
    fig3, ((tax, ptax2), (rxnax, estax), (residax, residhistax)) = plt.subplots(3, 2, figsize=(10, 12))

    for _label in run_labels:
        _sub = runs[_label]
        if _sub.empty:
            continue
        _color = run_colors[_label]
        tax.plot(_sub["Time since start (min)"], _sub["Cryo Temperature"], color=_color, linestyle="-", label=f"{_label} Cryo")
        tax.plot(_sub["Time since start (min)"], _sub["Reaction Temperature"], color=_color, linestyle="--")
        tax.plot(_sub["Time since start (min)"], _sub["Estimated Temperature"], color=_color, linestyle=":")

        ptax2.scatter(_sub["Cryo Temperature"], _sub["Reaction Pressure"], color=_color, marker=".", label=_label)
        rxnax.scatter(_sub["Cryo Temperature"],_sub["Reaction Temperature"], color=_color, marker=".", label = _label)
        estax.scatter(_sub["Cryo Temperature"], _sub["Estimated Temperature"], color = _color, marker=".", label = _label)

    ptax2.plot(templist, psat_h2s, color="black", linestyle="--", label="Psat H2S")

    _pooled = pd.concat([runs[_l] for _l in run_labels if not runs[_l].empty])

    fit3_slope = np.nan
    fit3_intercept = np.nan
    fit3_rmse = np.nan
    fit3_n = len(_pooled)

    if len(_pooled) >= 2:
        _fit_coef = np.polyfit(_pooled["Cryo Temperature"], _pooled["Estimated Temperature"], 1)
        fit3_slope, fit3_intercept = _fit_coef[0], _fit_coef[1]

        _fit_x = np.array([_pooled["Cryo Temperature"].min(), _pooled["Cryo Temperature"].max()])
        _fit_y = np.polyval(_fit_coef, _fit_x)

        _pooled_resid = _pooled["Estimated Temperature"] - np.polyval(_fit_coef, _pooled["Cryo Temperature"])
        fit3_rmse = np.sqrt(np.mean(_pooled_resid**2))

        estax.plot(
            _fit_x, _fit_y, color="black", linestyle="-", linewidth=2,
            label=f"Fit: y={fit3_slope:.3f}x+{fit3_intercept:.2f}, RMSE={fit3_rmse:.2f} K",
        )

        for _label in run_labels:
            _sub = runs[_label]
            if _sub.empty:
                continue
            _color = run_colors[_label]
            _resid = _sub["Estimated Temperature"] - np.polyval(_fit_coef, _sub["Cryo Temperature"])
            residax.scatter(_sub["Cryo Temperature"], _resid, color=_color, marker=".", label=_label)

        residax.axhline(0, color="black", linestyle="--", linewidth=1)

        residhistax.hist(_pooled_resid, bins=20, color="goldenrod", edgecolor="black")
        residhistax.axvline(0, color="black", linestyle="--", linewidth=1)
        residhistax.set_title(f"RMSE = {fit3_rmse:.2f} K, std = {_pooled_resid.std():.2f} K, n = {fit3_n}", fontsize="small")

    tax.set_xlabel("Time since start of selection (min)")
    tax.set_ylabel("Temperature (K)")

    ptax2.set_xlim([170,225])
    ptax2.set_ylim([-5,755])
    ptax2.set_ylabel("Sample Pressure (Torr)")

    rxnax.set_ylabel("Sample Temperature")
    estax.set_ylabel("Estimated Temperature from Pressure")

    for ax in [ptax2, rxnax, estax]:
        ax.set_xlabel("Control Temperature (K)")

    residax.set_xlabel("Control Temperature (K)")
    residax.set_ylabel("Residual: Estimated − fit (K)")
    residhistax.set_xlabel("Residual (K)")
    residhistax.set_ylabel("Count")

    for ax in [tax, ptax2, rxnax, estax, residax]:
        ax.grid(visible=True)
        ax.legend(fontsize="small")
    residhistax.grid(visible=True)

    fig3.tight_layout()
    return fig3, fit3_intercept, fit3_n, fit3_rmse, fit3_slope


@app.cell
def _(fig3, mo, run_labels):
    mo.stop(not run_labels, mo.md("No runs to plot."))
    fig3
    fig3.savefig('BmimExpts_PT_manualrangeslider_v3.svg')
    return


@app.cell
def _(fit3_intercept, fit3_n, fit3_rmse, fit3_slope, mo, run_labels):
    mo.stop(not run_labels, mo.md(""))
    mo.md(f"""
    **Pooled linear fit (Estimated vs. Cryo Temperature, n={fit3_n}):**
    Estimated = {fit3_slope:.3f} &times; Cryo + {fit3_intercept:.2f}

    **Estimated-temperature uncertainty (RMSE of residuals about this fit): {fit3_rmse:.2f} K**

    This RMSE is the number to quote as the precision of the
    pressure-based temperature estimate: on top of any systematic
    offset captured by the slope/intercept above, individual estimated
    temperatures scatter about the fit line by roughly this much.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    Solid = Cryo Temperature, dashed = Reaction Temperature, dotted =
    Estimated Temperature (color indicates run).
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Condition-based selection (independent of range sliders above)

    Select data by conditions instead of a single contiguous time
    window — useful when the segments of interest for a run are
    non-contiguous (e.g. several separate plateaus). Applied to the
    full file, independent of the range sliders above.
    """)
    return


@app.cell
def _(mo):
    cryo_temp_range = mo.ui.range_slider(
        start=50, stop=300, step=1, value=[175, 210], label="Cryo Temperature (K) between",
        full_width=True,
    )
    h2s_max = mo.ui.number(start=0, stop=100, step=0.1, value=1.0, label="H2S sccm below")
    ar_max = mo.ui.number(start=0, stop=100, step=0.1, value=1.0, label="Ar sccm below")
    Pmin = mo.ui.number(start=0, stop=1000, step=0.1, value=1.0, label="Pressure above")
    mo.vstack([cryo_temp_range, mo.hstack([h2s_max, ar_max, Pmin], justify="start")])
    return Pmin, ar_max, cryo_temp_range, h2s_max


@app.cell
def _(Pmin, ar_max, cryo_temp_range, h2s_max, multi_data, run_labels):
    mask_runs = {}
    for _label in run_labels:
        _df, _time = multi_data[_label]
        _cond = (
            (_df["Cryo Temperature"] >= cryo_temp_range.value[0])
            & (_df["Cryo Temperature"] <= cryo_temp_range.value[1])
            & (_df["H2S sccm"] < h2s_max.value)
            & (_df["Ar sccm"] < ar_max.value)
            & (_df["Reaction Pressure"] >= Pmin.value)
        )
        _sub = _df[_cond].copy()
        _sub["Time"] = _time[_cond]
        _tstart = _sub["Time"].iloc[0]
        _sub["Time since start (min)"] = (_sub["Time"] - _tstart).dt.total_seconds() / 60
        mask_runs[_label] = _sub
    return (mask_runs,)


@app.cell
def _(mask_runs, np, pd, plt, psat_h2s, run_colors, run_labels, templist):
    fig4, ((tax2, ptax3), (rxnax2,estax2)) = plt.subplots(2, 2, figsize=(8, 8))

    for _label in run_labels:
        _sub2 = mask_runs[_label]
        if _sub2.empty:
            continue
        _color = run_colors[_label]
        tax2.plot(_sub2["Time since start (min)"], _sub2["Cryo Temperature"], color=_color, linestyle="solid", label=f"{_label} Cryo")
        tax2.plot(_sub2["Time since start (min)"], _sub2["Reaction Temperature"], color=_color, linestyle="--")
        tax2.plot(_sub2["Time since start (min)"], _sub2["Estimated Temperature"], color=_color, linestyle=":")

        ptax3.scatter(_sub2["Cryo Temperature"], _sub2["Reaction Pressure"], color=_color, marker=".", label=_label)
        rxnax2.scatter(_sub2["Cryo Temperature"],_sub2["Reaction Temperature"], color=_color, marker=".", label = _label)
        estax2.scatter(_sub2["Cryo Temperature"], _sub2["Estimated Temperature"], color = _color, marker=".", label = _label)

    ptax3.plot(templist, psat_h2s, color="black", linestyle="--", label="Psat H2S")

    _pooled2 = pd.concat([mask_runs[_l] for _l in run_labels if not mask_runs[_l].empty])
    if len(_pooled2) >= 2:
        _fit_coef2 = np.polyfit(_pooled2["Cryo Temperature"], _pooled2["Estimated Temperature"], 1)
        _fit_x2 = np.array([_pooled2["Cryo Temperature"].min(), _pooled2["Cryo Temperature"].max()])
        _fit_y2 = np.polyval(_fit_coef2, _fit_x2)
        estax2.plot(
            _fit_x2, _fit_y2, color="black", linestyle="-", linewidth=2,
            label=f"Fit: y={_fit_coef2[0]:.3f}x+{_fit_coef2[1]:.2f}",
        )



    tax2.set_xlabel("Time since start (min)")
    tax2.set_ylabel("Temperature (K)")
    plt.setp(tax2.get_xticklabels(), rotation=45)
    tax2.grid(visible=True)
    tax2.legend(fontsize="small", ncol=2)

    ptax3.set_xlabel("Cryo Temperature (K)")
    ptax3.set_ylabel("Reaction Pressure (Torr)")
    ptax3.grid(visible=True)
    ptax3.legend(fontsize="small")
    ptax3.set_xlim([170,225])
    ptax3.set_ylim([-5,755])

    fig4.tight_layout()
    return (fig4,)


@app.cell
def _(fig4, mask_runs, mo, run_labels):
    mo.stop(not run_labels, mo.md("No runs to plot."))
    mo.stop(not any(not mask_runs[l].empty for l in run_labels), mo.md("No data points match the current conditions."))
    fig4
    return


@app.cell
def _(mo):
    mo.md("""
    Dot = Cryo Temperature, x = Reaction Temperature, + = Estimated
    Temperature (color indicates run).
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Summary: temperature differences vs. Cryo Temperature
    """)
    return


@app.cell
def _(mo, pd, run_labels, runs):
    mo.stop(not run_labels, mo.md("Select multi-file runs above to see the summary table."))

    per_run_rows = []
    for _label in run_labels:
        _sub = runs[_label]
        if _sub.empty:
            continue
        per_run_rows.append(
            {
                "Run": _label,
                "N points": len(_sub),
                "Reaction - Cryo (K)": (_sub["Reaction Temperature"] - _sub["Cryo Temperature"]).mean(),
                "Estimated - Cryo (K)": (_sub["Estimated Temperature"] - _sub["Cryo Temperature"]).mean(),
            }
        )

    per_run_df = pd.DataFrame(per_run_rows)

    summary_df = pd.DataFrame(
        [
            {
                "Metric": "Average difference (K)",
                "Reaction - Cryo": per_run_df["Reaction - Cryo (K)"].mean(),
                "Estimated - Cryo": per_run_df["Estimated - Cryo (K)"].mean(),
            },
            {
                "Metric": "Run-to-run std dev (K)",
                "Reaction - Cryo": per_run_df["Reaction - Cryo (K)"].std(),
                "Estimated - Cryo": per_run_df["Estimated - Cryo (K)"].std(),
            },
        ]
    )
    return per_run_df, summary_df


@app.cell
def _(mo, per_run_df):
    mo.vstack([mo.md("### Per-run averages"), mo.ui.table(per_run_df, selection=None)])
    return


@app.cell
def _(mo, summary_df):
    mo.vstack([mo.md("### Summary"), mo.ui.table(summary_df, selection=None)])
    return


if __name__ == "__main__":
    app.run()
