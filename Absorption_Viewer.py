import marimo

__generated_with = "0.23.15"
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
    Browse to one or more CSV files with `wavelength` (nm) and `absorption`
    columns. Selected files are overlaid on a single plot.
    """)
    return


@app.cell
def _(mo):
    browser = mo.ui.file_browser(filetypes=[".csv"], multiple=True,
                                 selection_mode="file",
                                 label="Select CSV file(s)")
    browser
    return (browser,)


@app.cell
def _(pd):
    def _find_col(columns, name):
        for c in columns:
            if c.strip().lower() == name:
                return c
        return None

    def load_spectra(browser):
        spectra = {}  # {label: DataFrame with 'wavelength', 'absorption'}
        # if not browser.value:
        #     return spectra
        for file_info in browser.value:
            df = pd.read_csv(file_info.path,header=1)
            # wcol = _find_col(df.columns, "nm")
            # tcol = _find_col(df.columns, "%T")
            spectra[file_info.name] = df
        return spectra

    return (load_spectra,)


@app.cell
def _(browser, load_spectra):
    spectra = load_spectra(browser)
    # spectra = {'spectrum1':pd.read_csv(browser.value[0].path,header=1)}
    spectra
    return (spectra,)


@app.cell
def _(mo):
    show_ev = mo.ui.switch(value=False, label="Show energy (eV) axis below wavelength (nm)")
    show_ev
    return (show_ev,)


@app.cell
def _(plt, show_ev, spectra):
    # E (eV) = hc / wavelength(nm), with hc/e in eV*nm
    _HC_EV_NM = 1239.84193

    def _nm_to_ev(nm):
        return _HC_EV_NM / nm

    def _ev_to_nm(ev):
        return _HC_EV_NM / ev

    fig, ax = plt.subplots(figsize=(7, 5))
    for _label, _df in spectra.items():
        ax.plot(_df['nm'], _df['%T'], label=_label)

    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("%Transmission")
    ax.legend(fontsize="small")
    ax.grid(alpha=0.3)

    if show_ev.value:
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
