import marimo

__generated_with = "0.23.15"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import plotly.graph_objects as go
    import numpy as np
    from io import StringIO


    return go, mo, pd


@app.cell
def _(mo):
    mo.md("""
    # UV-Vis Spectrophotometry Plotter

    Paste your UV-Vis data (nm, %T format) in the text area below.
    """)
    return


app._unparsable_cell(
    r"""
    file = mo.ui.file_browser(initial_path="/Users/ods/MIT Dropbox/Olivia Schneble/jaramillogroupshared/Data",filetypes=[".csv", ".txt"],
                       multiple=False, label="Select data file)
    file
    """,
    name="_"
)


@app.cell
def _(file):
    file.value[0].name
    return


@app.cell
def _(file, pd):
    df = pd.read_csv(file.value[0].path,header=1)
    return (df,)


@app.cell
def _(df):
    df.columns
    return


@app.cell
def _(df, file, go):


    # Get column names (handle variations)
    wl_col = [col for col in df.columns if 'nm' in col.lower()][0]
    t_col = [col for col in df.columns if '%t' in col.lower() or 't' in col.lower()][0]


    df_sorted = df.sort_values(by=wl_col)
    wavelength = df_sorted[wl_col].values
    transmittance = df_sorted[t_col].values
    energy_ev = 1239.84 / wavelength

    y_data = transmittance
    y_label = "Transmittance (%T)"
    # y_label = "Absorbance"
    title = file.value[0].name


    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=wavelength,
        y=y_data,
        mode='lines',
        name='UV-Vis',
        line=dict(color='#1f77b4', width=2),
        xaxis='x'
    ))

    energy_min = energy_ev.min()
    energy_max = energy_ev.max()
    wl_min = wavelength.min()
    wl_max = wavelength.max()

    fig.update_layout(
        title=title,
        xaxis=dict(
            title="Wavelength (nm)",
            autorange="reversed"
        ),
        # Secondary x-axis for energy
        xaxis2=dict(
            title="Photon Energy (eV)",
            overlaying="x",
            side="top",
            range=[energy_max, energy_min],  # Reversed like wavelength
            tickmode='linear',
            tick0=energy_min,
            dtick=(energy_max - energy_min) / 5  # ~5 ticks
        ),
        yaxis_title=y_label,
        template='plotly_white',
        hovermode='x unified',
        width=900,
        height=700,
        font=dict(size=12),
        margin=dict(t=100)
    )
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
