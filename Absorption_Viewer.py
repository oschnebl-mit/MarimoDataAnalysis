import marimo

__generated_with = "0.25.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import matplotlib.pyplot as plt

    return mo, pd, plt


@app.cell
def _(mo):
    mo.md("""
    # Absorption Spectrum Overlay Viewer

    Works with CSVs from different instruments:

    - **UV-Vis** exports usually have a header row (e.g. `nm`, `%T`).
    - **FTIR** exports are often bare numeric columns with no header at all.

    For each file, every column gets a role picker below (pre-filled with a
    guess when a header name makes it obvious). Set a column's role to
    `Wavelength (nm)` / `Wavenumber (cm^-1)` for the x-axis, and
    `Absorbance` / `Transmission (%)` for the signal; anything else can be
    left as `Ignore`. Selected files are then overlaid on one plot.
    """)
    return


@app.cell
def _(mo):
    browser = mo.ui.file_browser(
        initial_path=r'C:\Users\oschn\MIT Dropbox\Olivia Schneble\jaramillogroupshared\Data',
        filetypes=[".csv"], multiple=True,
        selection_mode="file",
        label="Select CSV file(s)",
    )
    browser
    return (browser,)


@app.cell
def _(pd):
    ROLE_OPTIONS = ["Ignore", "Wavelength (nm)", "Wavenumber (cm^-1)", "Absorbance", "Transmission (%)"]

    def is_numeric_token(s):
        try:
            float(s)
            return True
        except ValueError:
            return False

    def read_csv_auto(path):
        """Reads a CSV, auto-detecting whether the first row is a header.
        If every field in the first row looks numeric, the file has no
        header and columns are named 'Column 0', 'Column 1', ...;
        otherwise the first row is used as the column names.
        """
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            first_line = f.readline()
        fields = [v for v in first_line.strip().split(",") if v != ""]
        has_header = not all(is_numeric_token(v) for v in fields)

        df = pd.read_csv(path, header=0 if has_header else None)
        if not has_header:
            df.columns = [f"Column {i}" for i in range(len(df.columns))]
        return df

    def guess_column_role(colname):
        """Best-effort guess of a header column's role, or None if unclear."""
        c = str(colname).strip().lower()
        if "nm" in c or "wavelength" in c:
            return "Wavelength (nm)"
        if "wavenumber" in c or "cm-1" in c or "cm^-1" in c:
            return "Wavenumber (cm^-1)"
        if "%t" in c or "trans" in c or c == "t":
            return "Transmission (%)"
        if "abs" in c or c in ("a", "od"):
            return "Absorbance"
        return None

    return ROLE_OPTIONS, guess_column_role, read_csv_auto


@app.cell
def _(browser, mo, read_csv_auto):
    mo.stop(not browser.value, mo.md("Select one or more CSV files above to begin."))

    raw_frames = {file_info.name: read_csv_auto(file_info.path) for file_info in browser.value}
    return (raw_frames,)


@app.cell
def _(mo):
    mo.md("""
    ## Column types
    """)
    return


@app.cell
def _(ROLE_OPTIONS, guess_column_role, mo, raw_frames):
    column_role_editors = mo.ui.dictionary(
        {
            name: mo.ui.dictionary(
                {
                    str(col): mo.ui.dropdown(
                        options=ROLE_OPTIONS,
                        value=guess_column_role(col) or "Ignore",
                        label=str(col),
                    )
                    for col in df.columns
                }
            )
            for name, df in raw_frames.items()
        }
    )
    column_role_editors
    return (column_role_editors,)


@app.cell
def _(column_role_editors, mo, pd, raw_frames):
    spectra = {}
    x_kinds = {}
    warnings = []

    for _name, _df in raw_frames.items():
        _roles = column_role_editors[_name].value  # {column name: role}

        _x_col = next((c for c, r in _roles.items() if r in ("Wavelength (nm)", "Wavenumber (cm^-1)")), None)
        _abs_col = next((c for c, r in _roles.items() if r == "Absorbance"), None)
        _trans_col = next((c for c, r in _roles.items() if r == "Transmission (%)"), None)

        if _x_col is None or (_abs_col is None and _trans_col is None):
            warnings.append(f"**{_name}**: assign a wavelength/wavenumber column and an absorbance/transmission column above.")
            continue

        x_kinds[_name] = _roles[_x_col]
        # %T -> %Absorption is only an approximation (ignores reflectance),
        if _abs_col is None:
            _absorption = 1 - _df[_trans_col]/100
            _name = f'{_name}_AbsCalc'
            # spectra[_name] = pd.DataFrame({"x": _df[_x_col], "Absorption": _absorption})
        else:
            _absorption = _df[_abs_col] if _abs_col is not None else 1 - _df[_trans_col]/100
    
        spectra[_name] = pd.DataFrame({"x": _df[_x_col], "Absorption": _absorption})

    if warnings:
        mo.output.replace(mo.md("\n".join(f"- {w}" for w in warnings)))
    return spectra, x_kinds


@app.cell
def _(mo):
    show_ev = mo.ui.switch(value=False, label="Show energy (eV) axis below wavelength (nm)")
    show_ev
    return (show_ev,)


@app.cell
def _(mo, plt, show_ev, spectra, x_kinds):
    mo.stop(not spectra, mo.md("No spectra ready to plot yet - assign column roles above."))

    # E (eV) = hc / wavelength(nm), with hc/e in eV*nm; only meaningful when
    # every plotted spectrum's x-axis is actually wavelength in nm.
    _HC_EV_NM = 1239.84193
    _all_nm = all(k == "Wavelength (nm)" for k in x_kinds.values())

    def _nm_to_ev(nm):
        return _HC_EV_NM / nm

    def _ev_to_nm(ev):
        return _HC_EV_NM / ev

    fig, ax = plt.subplots(figsize=(7, 5))
    for _name, _df in spectra.items():
        ax.plot(_df["x"], _df["Absorption"], label=_name)

    ax.set_xlabel("Wavelength (nm)" if _all_nm else "x value")
    ax.set_ylabel("Absorption")
    ax.legend(fontsize="small")
    ax.grid(alpha=0.3)

    if show_ev.value and _all_nm:
        secax = ax.secondary_xaxis(-0.18, functions=(_nm_to_ev, _ev_to_nm))
        secax.set_xlabel("Energy (eV)")

    fig.tight_layout()
    fig
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
