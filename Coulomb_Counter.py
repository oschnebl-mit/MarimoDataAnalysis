import marimo

__generated_with = "0.23.15"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import numpy as np
    import pandas as pd
    import altair as alt
    from pathlib import Path

    return Path, alt, mo, np, pd


@app.cell
def _(mo):
    mo.md("""
    # Faradaic Charge Counter

    Scan a folder of Gamry `.dta` files for a given day, exclude EIS files,
    and integrate current over time to estimate total charge passed
    (∫I·dt). Cathodic (reduction) and anodic (oxidation) charge are summed
    separately since they can partially cancel within a single sweep.
    Optionally trim the capacitive double-layer charging transient at the
    start of each step before integrating. Finally, convert a selected
    charge total to moles (and, for a gas product, volume) of product.
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
    folder_input = mo.ui.text(
        placeholder=r"C:\path\to\folder\with\dta\files",
        label="Folder to scan",
        full_width=True,
    )
    date_input = mo.ui.text(
        placeholder="yyyymmdd", label="Date to include (in filename)",
        max_length=8,
    )
    mo.vstack([folder_input, date_input])
    return date_input, folder_input


@app.cell
def _(Path, date_input, folder_input, mo, parse_gamry_dta):
    mo.stop(
        not folder_input.value or not date_input.value,
        mo.md("*Enter a folder and a `yyyymmdd` date to scan.*"),
    )

    _folder = Path(folder_input.value)
    mo.stop(not _folder.is_dir(),
            mo.md(f"❌ `{folder_input.value}` is not a folder."))

    _candidates = sorted({
        p.resolve() for p in list(_folder.glob("*.dta")) + list(_folder.glob("*.DTA"))
        if date_input.value in p.name
    })

    parsed = {}       # {filename: {"header", "tables", "tag"}}
    excluded_eis = []
    read_errors = []

    for _p in _candidates:
        try:
            _text = _p.read_text(encoding="latin-1")
        except Exception as _e:
            read_errors.append((_p.name, str(_e)))
            continue

        _hdr, _tabs = parse_gamry_dta(_text)
        _tag = (_hdr.get("TAG", [""])[0] or "").strip().upper()

        # Exclude EIS by header TAG; fall back to filename if TAG is missing.
        _is_eis = ("EIS" in _tag) if _tag not in ("", "?") else ("EIS" in _p.name.upper())

        if _is_eis:
            excluded_eis.append(_p.name)
            continue

        parsed[_p.name] = {"header": _hdr, "tables": _tabs, "tag": _tag or "?"}

    return excluded_eis, parsed, read_errors


@app.cell
def _(excluded_eis, mo, parsed, read_errors):
    _lines = [f"**Matched, non-EIS files ({len(parsed)}):**"]
    _lines += [f"- `{n}` (TAG: {i['tag']})" for n, i in parsed.items()] or ["- *none*"]

    if excluded_eis:
        _lines.append(f"\n**Excluded as EIS ({len(excluded_eis)}):**")
        _lines += [f"- `{n}`" for n in excluded_eis]

    if read_errors:
        _lines.append(f"\n**Failed to read ({len(read_errors)}):**")
        _lines += [f"- `{n}`: {e}" for n, e in read_errors]

    mo.md("\n".join(_lines))
    return


@app.cell
def _(mo):
    mo.md("""
    ## Settle-time trimming (optional)

    Double-layer charging current decays roughly as `exp(-t / (Rᵤ·Cdl))`
    after each potential/current step. Discarding the first
    `k · Rᵤ · Cdl` seconds of *each table/step* before integrating removes
    most of this non-faradaic contribution. Leave the switch off to
    integrate the full traces, or enter a manual override if you already
    know the settle time.
    """)
    return


@app.cell
def _(mo):
    trim_switch = mo.ui.switch(
        value=False, label="Apply settle-time trimming")
    ru_input = mo.ui.number(
        value=0.0, start=0.0, stop=1e6, step=0.1, label="Rᵤ (Ω)")
    cdl_input = mo.ui.number(
        value=0.0, start=0.0, stop=1e6, step=0.1, label="Cdl (µF)")
    k_input = mo.ui.number(
        value=5.0, start=1.0, stop=20.0, step=0.5,
        label="Settle multiple (× Rᵤ·Cdl)")
    manual_settle = mo.ui.number(
        value=0.0, start=0.0, stop=1e6, step=0.1,
        label="Manual settle time override (s, 0 = use Rᵤ·Cdl·k)")
    mo.vstack([
        trim_switch,
        mo.hstack([ru_input, cdl_input, k_input]),
        manual_settle,
    ])
    return cdl_input, k_input, manual_settle, ru_input, trim_switch


@app.cell
def _(cdl_input, k_input, manual_settle, mo, ru_input, trim_switch):
    if manual_settle.value > 0:
        settle_time_s = manual_settle.value
    else:
        settle_time_s = k_input.value * ru_input.value * cdl_input.value * 1e-6

    if trim_switch.value:
        _msg = f"**Settle time applied: {settle_time_s:.3g} s** (trimmed from the start of each table/step)."
    else:
        _msg = "*Settle-time trimming is off — full traces will be integrated.*"
    mo.md(_msg)
    return (settle_time_s,)


@app.cell
def _(np):
    def integrate_charge(df, settle_time=0.0):
        """Trapezoidal ∫I dt over a (T, Im) table, split by current sign.

        Each interval's charge increment is bucketed by the sign of the
        average current over that interval. Returns (q_cathodic, q_anodic,
        n_points_used) in coulombs; q_cathodic <= 0, q_anodic >= 0.
        """
        t = df["T"].to_numpy(dtype=float)
        i = df["Im"].to_numpy(dtype=float)
        order = np.argsort(t)
        t, i = t[order], i[order]

        if settle_time > 0 and len(t):
            keep = (t - t.min()) >= settle_time
            t, i = t[keep], i[keep]

        if len(t) < 2:
            return 0.0, 0.0, len(t)

        dt = np.diff(t)
        i_avg = 0.5 * (i[:-1] + i[1:])
        incr = i_avg * dt

        q_cathodic = float(incr[incr < 0].sum())
        q_anodic = float(incr[incr >= 0].sum())
        return q_cathodic, q_anodic, len(t)

    return (integrate_charge,)


@app.cell
def _(integrate_charge, parsed, pd, settle_time_s, trim_switch):
    _rows = []
    for _fname, _info in parsed.items():
        for _tname, _tinfo in _info["tables"].items():
            if _tname == "OCVCURVE":
                continue
            _df = _tinfo["data"]
            if "T" not in _df.columns or "Im" not in _df.columns:
                continue
            _settle = settle_time_s if trim_switch.value else 0.0
            _qc, _qa, _n = integrate_charge(_df, _settle)
            _rows.append({
                "File": _fname,
                "Curve": _tname,
                "Tag": _info["tag"],
                "q_cathodic_C": _qc,
                "q_anodic_C": _qa,
                "q_net_C": _qc + _qa,
                "n_points_used": _n,
            })

    breakdown = pd.DataFrame(_rows, columns=[
        "File", "Curve", "Tag", "q_cathodic_C", "q_anodic_C", "q_net_C",
        "n_points_used",
    ])

    total_cathodic = breakdown["q_cathodic_C"].sum() if not breakdown.empty else 0.0
    total_anodic = breakdown["q_anodic_C"].sum() if not breakdown.empty else 0.0
    total_net = total_cathodic + total_anodic
    return breakdown, total_anodic, total_cathodic, total_net


@app.cell
def _(breakdown, mo, total_anodic, total_cathodic, total_net):
    mo.stop(breakdown.empty, mo.md("*No integrable (T, Im) tables found in the matched files.*"))

    mo.vstack([
        mo.md(
            f"### Totals for the day\n"
            f"**Cathodic (reduction) charge:** {total_cathodic:.4g} C "
            f"(|Q| = {abs(total_cathodic):.4g} C)  \n"
            f"**Anodic (oxidation) charge:** {total_anodic:.4g} C  \n"
            f"**Net charge:** {total_net:.4g} C"
        ),
        mo.ui.table(breakdown, label="Per-file / per-curve breakdown"),
    ])
    return


@app.cell
def _(alt, breakdown, mo):
    mo.stop(breakdown.empty, mo.md(""))

    _plot_df = breakdown.melt(
        id_vars=["File", "Curve"],
        value_vars=["q_cathodic_C", "q_anodic_C"],
        var_name="direction", value_name="charge_C",
    )
    _plot_df["direction"] = _plot_df["direction"].map({
        "q_cathodic_C": "Cathodic", "q_anodic_C": "Anodic",
    })
    _plot_df["abs_charge_C"] = _plot_df["charge_C"].abs()

    _chart = alt.Chart(_plot_df).mark_bar().encode(
        x=alt.X("File:N", title=None, axis=alt.Axis(labelAngle=-40)),
        xOffset="direction:N",
        y=alt.Y("abs_charge_C:Q", title="|Charge| (C)"),
        color=alt.Color(
            "direction:N", title="Direction",
            scale=alt.Scale(domain=["Cathodic", "Anodic"],
                             range=["#1f77b4", "#d62728"]),
        ),
        tooltip=["File:N", "Curve:N", "direction:N",
                 alt.Tooltip("charge_C:Q", title="Charge (C)", format=".4g")],
    ).properties(width=650, height=320, title="Charge by file")

    mo.ui.altair_chart(_chart, chart_selection=False, legend_selection=False)
    return


@app.cell
def _(mo):
    mo.md("""
    ---
    ## Convert to moles (and volume)

    `moles = Q / (n · F)`, where `F` is the Faraday constant and `n` is
    electrons transferred per mole of product for your expected
    half-reaction.
    """)
    return


@app.cell
def _(mo, total_anodic, total_cathodic, total_net):
    charge_source = mo.ui.dropdown(
        options=["Cathodic (reduction)", "Anodic (oxidation)", "Net"],
        value="Cathodic (reduction)", label="Charge to convert",
    )
    n_input = mo.ui.number(
        value=2.0, start=0.01, stop=100.0, step=1.0,
        label="n (mol e⁻ per mol product)",
    )
    gas_toggle = mo.ui.switch(
        value=False, label="Product is a gas (compute volume)")
    mo.vstack([
        mo.md(
            f"Available: cathodic |Q| = {abs(total_cathodic):.4g} C, "
            f"anodic |Q| = {abs(total_anodic):.4g} C, "
            f"net |Q| = {abs(total_net):.4g} C"
        ),
        mo.hstack([charge_source, n_input]),
        gas_toggle,
    ])
    return charge_source, gas_toggle, n_input


@app.cell
def _(gas_toggle, mo):
    temp_input = mo.ui.number(
        value=298.15, start=0.0, stop=2000.0, step=1.0,
        label="Temperature (K)")
    pressure_input = mo.ui.number(
        value=1.0, start=1e-6, stop=1000.0, step=0.1, label="Pressure")
    pressure_unit = mo.ui.dropdown(
        options=["atm", "Torr", "kPa"], value="atm", label="Pressure unit")

    gas_inputs_view = (
        mo.hstack([temp_input, pressure_input, pressure_unit])
        if gas_toggle.value
        else mo.md("*Toggle 'Product is a gas' above to compute volume.*")
    )
    gas_inputs_view
    return pressure_input, pressure_unit, temp_input


@app.cell
def _(
    charge_source,
    gas_toggle,
    mo,
    n_input,
    pressure_input,
    pressure_unit,
    temp_input,
    total_anodic,
    total_cathodic,
    total_net,
):
    FARADAY = 96485.33212  # C / mol e-
    GAS_R = 8.314462618  # J / (mol K)
    PRESSURE_TO_PA = {"atm": 101325.0, "Torr": 133.322368, "kPa": 1000.0}

    _q_by_source = {
        "Cathodic (reduction)": abs(total_cathodic),
        "Anodic (oxidation)": abs(total_anodic),
        "Net": abs(total_net),
    }
    Q_selected = _q_by_source.get(charge_source.value, 0.0)

    n = n_input.value or 0.0
    moles = Q_selected / (n * FARADAY) if n else 0.0

    _lines = [
        f"**Charge used:** {Q_selected:.4g} C  ({charge_source.value})",
        f"**n:** {n:g} mol e⁻ / mol product",
        f"**Moles of product:** {moles:.4g} mol",
    ]

    if gas_toggle.value:
        p_pa = PRESSURE_TO_PA[pressure_unit.value] * pressure_input.value
        volume_m3 = (moles * GAS_R * temp_input.value / p_pa) if p_pa else 0.0
        volume_L = volume_m3 * 1000.0
        _lines.append(
            f"**Volume** at {temp_input.value:g} K, "
            f"{pressure_input.value:g} {pressure_unit.value}: "
            f"{volume_L:.4g} L ({volume_L * 1000:.4g} mL)"
        )

    mo.md("\n\n".join(_lines))
    return


if __name__ == "__main__":
    app.run()
