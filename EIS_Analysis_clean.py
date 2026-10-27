import marimo

__generated_with = "0.25.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import numpy as np
    import altair as alt
    import os
    from io import StringIO
    from scipy import stats

    return StringIO, alt, mo, np, os, pd, stats


@app.cell
def _():
    basepath = r'C:\Users\oschn\Dropbox (MIT)\jaramillogroupshared\Data\Jaramillo lab\CryoEchem'
    kappa_10mM_NaCl = 1.2e-3  # S/cm, calibration standard conductivity
    GAS_HEADSPACE_VOLUME_CM3 = 620  # cm3 of gas headspace used to convert Gas Volume to a liquid-equivalent volume
    PRESSURE_REL_ERR = 0.01  # hard-coded fractional (1%) uncertainty on every Pressure reading
    DEFAULT_ADDITIVE_PATTERNS = {
        "IL+Sulfolane": r"sulf|S3MS",
        "IL+Pyridine": r"Pyr",
        "IL+PC": r"PC",
        "Pyridine": r"pyr",
    }
    # molar mass (g/mol) and density (g/mL) used for mole-fraction calculations.
    # regex `pattern` identifies the compound from a Measurement filename.
    # `mmol_to_uL`, if given, is the volume (uL) added to the cell per mmol of
    # that IL - used when the filename gives an explicit '<N>mmol<IL>' amount
    # (e.g. '1mmolBmimTf2N') instead of (or in addition to) a liquid-volume token.
    IONIC_LIQUID_PROPERTIES = {
        "BmimTf2N": {"pattern": r"Bmim", "MW": 419.36, "density": 1.437, "mmol_to_uL": 560},
        "BmPTf2N": {"pattern": r"BmP", "MW": 422.41, "density": 1.45},
    }
    ADDITIVE_PROPERTIES = {
        "Sulfolane": {"pattern": r"sulf|S3MS", "MW": 120.17, "density": 1.261},
        "Pyridine": {"pattern": r"[Pp]yr", "MW": 79.10, "density": 0.9819},
        "PC": {"pattern": r"PC", "MW": 102.09, "density": 1.205},
    }
    return (
        ADDITIVE_PROPERTIES,
        DEFAULT_ADDITIVE_PATTERNS,
        GAS_HEADSPACE_VOLUME_CM3,
        IONIC_LIQUID_PROPERTIES,
        PRESSURE_REL_ERR,
        basepath,
        kappa_10mM_NaCl,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # EIS Analysis

    1. **Calibration** - load NaCl standard EIS runs, fit cell constant vs. liquid volume.
    2. **Data analysis** - load experimental EIS runs, compute conductivity, export to csv.
    3. **Further data analysis** - load a saved csv and explore trends vs. metadata.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ### Helper functions: loading
    """)
    return


@app.cell(hide_code=True)
def _(StringIO, os, pd):
    def read_gamry_dta(path):
        """Reads a Gamry .DTA file's ZCURVE table into a DataFrame."""
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        start = None
        for i, line in enumerate(lines):
            if line.strip().startswith("ZCURVE"):
                start = i
                break
        if start is None:
            raise ValueError("ZCURVE marker not found")

        data_lines = lines[start + 1:]

        cleaned = []
        for ln in data_lines:
            s = ln.strip()
            if not s:
                continue
            if s.startswith("#"):  # units row
                continue
            if "Measurement aborted" in s:
                continue
            cleaned.append(ln)

        df = pd.read_csv(
            StringIO("".join(cleaned)),
            sep="\t",
            header=0,
            dtype=str,
            engine="python",
        )

        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df['Measurement'] = os.path.basename(path)
        return df

    return (read_gamry_dta,)


@app.cell(hide_code=True)
def _(mo, pd, read_gamry_dta):
    def load_eis_files(browser):
        """Loads and concatenates all files selected in a mo.ui.file_browser into one DataFrame."""
        if not browser.value:
            mo.output.replace(mo.md("No files selected."))
            return pd.DataFrame()

        dfs = []
        for file_info in browser.value:
            data = read_gamry_dta(file_info.path)
            if data is not None:
                dfs.append(data)

        if not dfs:
            mo.output.replace(mo.md("Selected files do not contain valid ZCURVE data."))
            return pd.DataFrame()

        combined = pd.concat(dfs, ignore_index=True)
        if isinstance(combined.columns, pd.MultiIndex):
            combined.columns = combined.columns.get_level_values(0)

        mo.output.replace(mo.md(f"**Loaded {len(dfs)} files.** Total data points: {len(combined)}"))
        return combined

    return (load_eis_files,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ### Helper functions: parsing & metadata
    """)
    return


@app.cell(hide_code=True)
def _(np):
    A_h2s = 4.43681
    B_h2s = 829.439
    C_h2s = -25.412
    def InvAntoine(A,B,C,P):
        ## computes temperature in Kelvin from Pressure in Torr based on Antoine eqn
        Pbar = P/750
        T = B/(A-np.log10(Pbar))-C
        return T

    return A_h2s, B_h2s, C_h2s, InvAntoine


@app.function(hide_code=True)
def filter_good_measurements(df, phase_thresh=10):
    """Keeps only measurements whose max |Zphz| stays below phase_thresh (i.e. reached the resistive plateau)."""
    maxphase = df.groupby('Measurement', as_index=False)['Zphz'].max()
    good = maxphase[maxphase['Zphz'].abs() < phase_thresh]
    return df[df['Measurement'].isin(good['Measurement'])]


@app.function(hide_code=True)
def extract_date(measurement_series, pattern=r"(20\d{6})_"):
    """Extracts a run date (YYYYMMDD) from a Measurement filename column."""
    return measurement_series.str.extract(pattern)


@app.cell(hide_code=True)
def _(np):
    def extract_rsoln_metadata(
        df,
        tempstring=r'(\d+)K',
        presstring=r'(\d+)[Tt]orr',
        gasvolstring=r'(\d+)cm3',
        liqvolstring=r'(\d+(?:p\d+)?)[u|m]L',
        il_properties=None,
        searchphrase=None,
    ):
        """
        Groups EIS data by Measurement, computes Rsoln (mean Zmod where |Zphz|<10)
        plus its standard error of the mean (Rsoln_SEM), and parses
        Temperature/Pressure/Gas Volume/Liquid Volume out of the filename.

        'Liquid Volume' here is only the volume given by an explicit uL/mL
        token in the filename - it does NOT yet include any IL volume implied
        by a '<N>mmol<IL>' token (e.g. '1mmolBmimTf2N'). If `il_properties` is
        given (dict of name -> {"pattern", ...}), an 'IL mmol' column is also
        parsed from that token; combining it into a volume happens downstream,
        after the user has had a chance to review/fill in missing metadata.
        """
        if searchphrase is not None:
            df = df[df['Measurement'].str.contains(searchphrase)]

        plateau = df[df['Zphz'].abs() < 10].groupby('Measurement')['Zmod']
        subdf = plateau.mean().reset_index(name='Rsoln')
        subdf['Rsoln_SEM'] = (plateau.std() / np.sqrt(plateau.count())).values
        subdf['Temperature'] = subdf['Measurement'].str.extract(tempstring).astype('float')
        subdf['Pressure'] = subdf['Measurement'].str.extract(presstring).astype('float')
        subdf['Gas Volume'] = subdf['Measurement'].str.extract(gasvolstring).astype('float')

        liquidvolume = (
            subdf['Measurement']
            .str.extract(liqvolstring, expand=False)
            .str.replace('p', '.')
            .astype(float)
        )
        subdf['Liquid Volume'] = np.where(
            subdf['Measurement'].str.contains(r'uL'), liquidvolume / 1000, liquidvolume
        )

        subdf['IL mmol'] = np.nan
        subdf['Cosolvent mmol'] = np.nan
        if il_properties:
            for _name, _props in il_properties.items():
                _match = subdf['Measurement'].str.extract(
                    rf'(\d+(?:\.\d+)?)mmol(?:{_props["pattern"]})', expand=False
                ).astype(float)
                subdf['IL mmol'] = subdf['IL mmol'].fillna(_match)
        return subdf

    return (extract_rsoln_metadata,)


@app.cell(hide_code=True)
def _(np):
    def classify_additive(measurement_series, patterns):
        """Classifies each Measurement by the first matching pattern in `patterns` (dict label -> regex), else 'IL only'."""
        result = np.full(len(measurement_series), 'IL only', dtype=object)
        for label, pattern in reversed(list(patterns.items())):
            matches = measurement_series.str.contains(pattern, regex=True)
            result = np.where(matches, label, result)
        return result

    return (classify_additive,)


@app.cell(hide_code=True)
def _(np, pd):
    def compute_mole_fraction_h2s(
        df,
        additive_properties,
        il_properties,
        measurement_col='Measurement',
        gasvol_col='Gas Volume',
        liqvol_col='Liquid Volume',
        il_mmol_col='IL mmol',
    ):
        """
        Computes the overall H2S mole fraction x_H2S = n_H2S / (n_H2S + n_additive + n_IL).

        - n_H2S comes from Gas Volume via a fixed ideal-gas conversion factor (moles per cm3).
        - n_additive: for each additive, first tries parsing a '<N>mmol<additive>' token
          directly from the filename; if that's absent, falls back to the parsed Liquid
          Volume together with the additive's MW/density (moles = volume * density / MW).
        - n_IL: for each IL, first tries the (possibly user-edited) `il_mmol_col` value
          directly - moles = mmol / 1000. If the IL's properties define 'mmol_to_uL'
          (the volume of the stock solution/aliquot delivering 1 mmol of that IL - not
          generally equal to mmol * MW / density, since the IL may be added as a diluted
          stock rather than pure compound), that factor converts the mmol amount into an
          added liquid volume; otherwise MW/density is used instead. ILs with no mmol
          value fall back to the previous behavior: whatever liquid volume is left over
          after the additive volume, converted via the IL's own density/MW.
        - Any value that can't be determined (no match) defaults to 0, not NaN.

        `additive_properties` / `il_properties` are dicts of name -> {"pattern", "MW" (g/mol),
        "density" (g/mL), optionally "mmol_to_uL" for il_properties}.
        Returns (moles_h2s, moles_additive, moles_il, mole_fraction_h2s, liquid_volume_total_mL).
        `liquid_volume_total_mL` is `df[liqvol_col]` plus any IL volume implied by an
        explicit mmol amount (so it reflects IL added via a mmol token, not just uL/mL).
        """
        meas = df[measurement_col]
        moles_h2s = df[gasvol_col].fillna(0) * 0.0000446  # moles per cm3

        moles_additive = pd.Series(0.0, index=df.index)
        volume_additive_mL = pd.Series(0.0, index=df.index)
        for _name, props in additive_properties.items():
            is_additive = meas.str.contains(props['pattern'], regex=True)

            mmol_match = meas.str.extract(
                rf'(\d+(?:\.\d+)?)mmol(?:{props["pattern"]})', expand=False
            ).astype(float)
            has_mmol = mmol_match.notna()
            moles_additive.loc[has_mmol] = mmol_match[has_mmol] / 1000
            volume_additive_mL.loc[has_mmol] = moles_additive.loc[has_mmol] * props['MW'] / props['density']

            needs_fallback = is_additive & ~has_mmol
            volume_additive_mL.loc[needs_fallback] = df.loc[needs_fallback, liqvol_col].fillna(0)
            moles_additive.loc[needs_fallback] = (
                volume_additive_mL.loc[needs_fallback] * props['density'] / props['MW']
            )

        il_mmol = df[il_mmol_col] if il_mmol_col in df.columns else pd.Series(np.nan, index=df.index)
        moles_il = pd.Series(0.0, index=df.index)
        volume_il_from_mmol_mL = pd.Series(0.0, index=df.index)
        liquid_vol_leftover_mL = (df[liqvol_col].fillna(0) - volume_additive_mL).clip(lower=0)
        for _name, props in il_properties.items():
            is_il = meas.str.contains(props['pattern'], regex=True)
            has_mmol = is_il & il_mmol.notna()

            moles_il.loc[has_mmol] = il_mmol.loc[has_mmol] / 1000
            if 'mmol_to_uL' in props:
                volume_il_from_mmol_mL.loc[has_mmol] = il_mmol.loc[has_mmol] * props['mmol_to_uL'] / 1000
            else:
                volume_il_from_mmol_mL.loc[has_mmol] = moles_il.loc[has_mmol] * props['MW'] / props['density']

            needs_fallback = is_il & ~has_mmol
            moles_il.loc[needs_fallback] = (
                liquid_vol_leftover_mL.loc[needs_fallback] * props['density'] / props['MW']
            )

        total_moles = moles_h2s + moles_additive + moles_il
        mole_fraction_h2s = moles_h2s / total_moles
        liquid_volume_total_mL = df[liqvol_col].fillna(0) + volume_il_from_mmol_mL
        return moles_h2s, moles_additive, moles_il, mole_fraction_h2s, liquid_volume_total_mL

    return (compute_mole_fraction_h2s,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ### Helper functions: fitting
    """)
    return


@app.cell(hide_code=True)
def _(np, stats):
    def fit_cell_constant_vs_volume(caldf, volume_col="Liquid Volume", const_col="Cell Constant", mode="linear"):
        """
        Fits a line through calibration Cell Constant vs. Liquid Volume data.
        mode="linear" fits Cell Constant vs. volume_col directly; mode="inverse" fits
        Cell Constant vs. 1/volume_col instead.
        Returns (predict_fn, predict_err_fn, slope, intercept, r_value); predict_fn(volume)
        gives the fitted cell constant, predict_err_fn(volume) gives the standard error of
        that fitted value (uncertainty of the calibration line itself).
        """
        x = 1 / caldf[volume_col] if mode == "inverse" else caldf[volume_col]
        y = caldf[const_col]
        fit = stats.linregress(x, y)

        n = len(x)
        x_mean = x.mean()
        ss_x = ((x - x_mean) ** 2).sum()
        residuals = y - (fit.intercept + fit.slope * x)
        resid_std = np.sqrt((residuals ** 2).sum() / (n - 2)) if n > 2 else np.nan

        def predict_fn(volume):
            xv = 1 / volume if mode == "inverse" else volume
            return fit.intercept + fit.slope * xv

        def predict_err_fn(volume):
            xv = 1 / volume if mode == "inverse" else volume
            return resid_std * np.sqrt(1 / n + (xv - x_mean) ** 2 / ss_x)

        return predict_fn, predict_err_fn, fit.slope, fit.intercept, fit.rvalue

    return (fit_cell_constant_vs_volume,)


@app.cell(hide_code=True)
def _(stats):
    def getslope(df, x='invT', y='logKappa'):
        """Linear regression slope of y vs. x (e.g. an Arrhenius plot)."""
        slope, intercept, r_value, _, _ = stats.linregress(df[x], df[y])
        return slope

    def slope_to_Ea(slope):
        """Converts the slope of a ln(kappa) vs. 1000/T plot into an activation energy (kJ/mol)."""
        R_gas = 8.314  # J/mol*K
        return (-slope * R_gas * 1000) / 1000

    return getslope, slope_to_Ea


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ### Helper functions: plotting
    """)
    return


@app.cell(hide_code=True)
def _(alt, pd):
    def plot_bode_pair(data, groupby=None, title="Bode Plot"):
        """Interactive dual-panel Bode plot (|Z| and phase vs. frequency), colored by `groupby`."""
        df = data.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        base = alt.Chart(df).encode(
            x=alt.X('Freq', scale=alt.Scale(type='log'), title='Frequency (Hz)'),
            tooltip=[
                alt.Tooltip(groupby if groupby is not None else ' '),
                alt.Tooltip('Freq', format='.2e', title='Freq (Hz)'),
                alt.Tooltip('Zmod', format='.2s', title="|Z| (Ohm)"),
                alt.Tooltip('Zphz', format='.1f', title="Phase (°)"),
            ],
        )

        mag_chart = base.mark_line(point=True).encode(
            y=alt.Y('Zmod', scale=alt.Scale(type='log'), title='|Z| (Ohm)'),
            detail='Measurement:N',
            color=groupby if groupby is not None else alt.value("#0f4c75"),
        )

        phase_chart = base.mark_line(point=True, strokeDash=[3, 3]).encode(
            y=alt.Y('Zphz', title='Phase Angle (°)'),
            detail='Measurement:N',
            color=groupby if groupby is not None else alt.value("#ee8430"),
        )

        return (mag_chart | phase_chart).properties(title=title).interactive()

    return (plot_bode_pair,)


@app.cell
def _(alt, pd):
    def scatter_vs_metadata(df, x, y, color=None, size=None,shape=None, log_y=False, title=None, tooltip=None, xerr=None, yerr=None):
        """Scatter plot of y vs. x, optionally colored by a metadata column. x/color may be numeric or categorical.
        xerr, if given, is a constant +/- error drawn as horizontal error bars on x (x must be numeric)."""
        x_type = 'Q' if pd.api.types.is_numeric_dtype(df[x]) else 'N'
        encode_kwargs = dict(
            x=alt.X(f'{x}:{x_type}', scale=alt.Scale(domain=[df[x].min()*0.9, df[x].max()*1.05])),
            y=alt.Y(f'{y}:Q', scale=alt.Scale(type='log' if log_y else 'linear'), axis=alt.Axis(format='.0e')),
        )
        if color is not None:
            color_type = 'Q' if pd.api.types.is_numeric_dtype(df[color]) else 'N'
            encode_kwargs['color'] = alt.Color(f'{color}:{color_type}', scale=alt.Scale(scheme='turbo'))
        if tooltip is not None:
            encode_kwargs['tooltip'] = tooltip
        if size is not None:
            size_type = 'Q' if pd.api.types.is_numeric_dtype(df[size]) else 'N'
            encode_kwargs['size'] = alt.Size(f'{size}:{size_type}', scale=alt.Scale(range=[100,200]))
        if shape is not None:
            encode_kwargs['shape'] = alt.Shape(f'{shape}:N',range=['circle','triangle','square','cross'])

        chart = alt.Chart(df).mark_point(size=150,filled=True, opacity=0.6, stroke = 'black').encode(**encode_kwargs).interactive()

        if xerr is not None:
            errdf = df.copy()
            errdf['_x_lo'] = df[x] - df[xerr]
            errdf['_x_hi'] = df[x] + df[xerr]
            x_error_bars = alt.Chart(errdf).mark_errorbar(ticks=True).encode(
                alt.X('_x_lo:Q', title=x, scale=alt.Scale(domain=[df[x].min()*0.9, df[x].max()*1.05])),
                alt.X2('_x_hi:Q'),
                alt.Y(f'{y}:Q', scale=alt.Scale(type='log' if log_y else 'linear')),
            )
            chart = x_error_bars + chart

        if yerr is  not None:
            yerrdf = df.copy()
            yerrdf['_y_lo'] = df[y] - df[yerr]
            yerrdf['_y_hi'] = df[y] + df[yerr]
            y_error_bars = alt.Chart(yerrdf).mark_errorbar(ticks=True).encode(
                alt.X(f'{x}:Q',title=x, scale=alt.Scale(domain=[df[x].min()*0.9, df[x].max()*1.05])),
                alt.Y('_y_lo:Q', scale=alt.Scale(type='log' if log_y else 'linear'), title=y),
                alt.Y2('_y_hi:Q', scale=alt.Scale(type='log' if log_y else 'linear'))
            )
            chart = y_error_bars + chart

        if title:
            chart = chart.properties(title=title)
        return chart

    return (scatter_vs_metadata,)


@app.cell
def _(alt, pd):
    def boxplot_by_category(df, category, value, log_y=True, color=None):
        """Boxplot of `value` grouped by `category`, with jittered individual points overlaid."""
        base_x = alt.X(f'{category}:N', axis=alt.Axis(title=category, labelAngle=-45))
        y_scale = alt.Scale(type='log') if log_y else alt.Scale(type='linear')

        box = alt.Chart(df).mark_boxplot(extent='min-max', opacity=0.5, color='gray').encode(
            x=base_x,
            y=alt.Y(f'{value}:Q', scale=y_scale, axis=alt.Axis(format='.0e')),
        )

        point_encode = dict(
            x=base_x,
            y=alt.Y(f'{value}:Q', scale=y_scale),

        )
        if color is not None:
            color_type = 'Q' if pd.api.types.is_numeric_dtype(df[color]) else 'N'
            point_encode['color'] = alt.Color(f'{color}:{color_type}', scale=alt.Scale(scheme='turbo'))

        # points = alt.Chart(df).mark_circle(size=40, opacity=0.6).encode(**point_encode).transform_calculate(
        #     jitter="(random() - 0.5) * 0.05"
        # )
        points = alt.Chart(df).mark_circle(size=40, opacity=0.6).encode(**point_encode,
        xOffset=alt.XOffset("jitter:Q", scale=alt.Scale(domain=[-1, 1]), axis=None),
    ).transform_calculate(
        jitter="(random() - 0.5) * 0.4"   # ±0.2 of domain [-1, 1] → ~20% of band width
    )

        return (box + points).properties(width=350)

    return (boxplot_by_category,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 1. Calibration
    """)
    return


@app.cell
def _(basepath, mo):
    cal_browser = mo.ui.file_browser(
        initial_path=basepath, filetypes=['.dta', '.DTA'], multiple=True, selection_mode='file',
        label='Select NaCl calibration .dta files...',
    )
    cal_browser
    return (cal_browser,)


@app.cell
def _(cal_browser, extract_rsoln_metadata, kappa_10mM_NaCl, load_eis_files):
    caldata = load_eis_files(cal_browser)
    caldf = extract_rsoln_metadata(caldata)
    caldf['Cell Constant'] = caldf['Rsoln'] * kappa_10mM_NaCl
    caldf['Date'] = extract_date(caldf['Measurement'])
    caldf
    return caldata, caldf


@app.cell
def _(caldata, plot_bode_pair):
    plot_bode_pair(caldata, groupby='Measurement', title='Calibration Bode Plot')
    return


@app.cell
def _(mo):
    cell_const_fit_mode = mo.ui.radio(
        options={"Cell Constant vs. Volume": "linear", "Cell Constant vs. 1/Volume": "inverse"},
        value="Cell Constant vs. Volume",
        label="Cell constant fit model",
    )
    cell_const_fit_mode
    return (cell_const_fit_mode,)


@app.cell
def _(alt, caldf, cell_const_fit_mode):
    _x_col = 'Inverse Liquid Volume' if cell_const_fit_mode.value == 'inverse' else 'Liquid Volume'
    _plotdf = caldf.copy()
    _plotdf['Inverse Liquid Volume'] = 1 / _plotdf['Liquid Volume']

    cal_points = alt.Chart(_plotdf).mark_point(size=90).encode(
        x=alt.X(f'{_x_col}:Q'),
        y=alt.Y('Cell Constant:Q', scale=alt.Scale(type='linear')),
        color=alt.Color('Date:N'),
        tooltip=['Liquid Volume', 'Cell Constant', 'Measurement'],
    )
    cal_fitline = cal_points.transform_regression(
        on=_x_col, regression='Cell Constant'
    ).mark_line(color='black', strokeDash=[5, 5])

    (cal_points + cal_fitline).properties(title=f'Calibration: Cell Constant vs. {_x_col}').interactive()
    return


@app.cell
def _(caldf, cell_const_fit_mode, fit_cell_constant_vs_volume):
    cell_const_fn, cell_const_err_fn, cell_const_slope, cell_const_intercept, cell_const_r = fit_cell_constant_vs_volume(
        caldf, mode=cell_const_fit_mode.value
    )
    return (
        cell_const_err_fn,
        cell_const_fn,
        cell_const_intercept,
        cell_const_r,
        cell_const_slope,
    )


@app.cell
def _(
    cell_const_fit_mode,
    cell_const_intercept,
    cell_const_r,
    cell_const_slope,
    mo,
):
    _x_label = '1/Liquid Volume' if cell_const_fit_mode.value == 'inverse' else 'Liquid Volume'
    mo.md(f"""
    **Fitted cell constant:** `Cell Constant = {cell_const_slope:.4f} * {_x_label} + {cell_const_intercept:.4f}`
    (r = {cell_const_r:.3f})
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## 2. Data analysis
    """)
    return


@app.cell
def _(basepath, mo):
    data_browser = mo.ui.file_browser(
        initial_path=basepath, filetypes=['.dta', '.DTA'], multiple=True, selection_mode='file',
        label='Select experimental .dta files...',
    )
    data_browser
    return (data_browser,)


@app.cell
def _(data_browser, load_eis_files, plot_bode_pair):
    _rawdata = load_eis_files(data_browser)
    plot_bode_pair(_rawdata, groupby='Measurement')
    return


@app.cell
def _(
    DEFAULT_ADDITIVE_PATTERNS,
    GAS_HEADSPACE_VOLUME_CM3,
    IONIC_LIQUID_PROPERTIES,
    classify_additive,
    data_browser,
    extract_rsoln_metadata,
    load_eis_files,
):
    rawdata = load_eis_files(data_browser)
    gooddata = filter_good_measurements(rawdata)
    _rawmeta = extract_rsoln_metadata(gooddata, il_properties=IONIC_LIQUID_PROPERTIES)
    _rawmeta['Date'] = extract_date(_rawmeta['Measurement'])
    _rawmeta['Additive'] = classify_additive(_rawmeta['Measurement'], DEFAULT_ADDITIVE_PATTERNS)
    _rawmeta['Total Volume'] = _rawmeta['Gas Volume'].fillna(0) / GAS_HEADSPACE_VOLUME_CM3 + _rawmeta['Liquid Volume'].fillna(0)
    rawmeta = _rawmeta
    return (rawmeta,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ### Review / fill in metadata

    Parsed from each filename: `Temperature` (K), `Pressure` (Torr),
    `Gas Volume` (cm3), `Liquid Volume` (mL, explicit uL/mL token only -
    does not yet include IL added via an `IL mmol` token), and `IL mmol`
    (parsed from e.g. `1mmolBmimTf2N`).

    Edit any cell below to fill in values missing from a filename, or to
    correct a mis-parsed one. Edits here flow into all downstream
    calculations (Kappa, mole fractions, Temperature Est, etc.).
    """)
    return


@app.cell
def _(mo, rawmeta):
    metadata_editor = mo.ui.data_editor(
        rawmeta[['Measurement', 'Temperature', 'Pressure', 'Gas Volume', 'Liquid Volume', 'IL mmol','Cosolvent mmol']],
        label='Measurement metadata',
        editable_columns=['Temperature', 'Pressure', 'Gas Volume', 'Liquid Volume', 'IL mmol','Cosolvent mmol'],
    )
    metadata_editor
    return (metadata_editor,)


@app.cell
def _(
    ADDITIVE_PROPERTIES,
    A_h2s,
    B_h2s,
    C_h2s,
    GAS_HEADSPACE_VOLUME_CM3,
    IONIC_LIQUID_PROPERTIES,
    InvAntoine,
    PRESSURE_REL_ERR,
    cell_const_err_fn,
    cell_const_fn,
    compute_mole_fraction_h2s,
    metadata_editor,
    np,
    rawmeta,
):
    datadf = rawmeta.drop(columns=['Temperature', 'Pressure', 'Gas Volume', 'Liquid Volume', 'IL mmol','Cosolvent mmol']).join(
        metadata_editor.value[['Temperature', 'Pressure', 'Gas Volume', 'Liquid Volume', 'IL mmol', 'Cosolvent mmol']]
    )

    _cell_const = cell_const_fn(datadf['Total Volume'])
    _cell_const_err = cell_const_err_fn(datadf['Total Volume'])
    # _cell_const = np.where(datadf['Date']=='20260422',0.08, np.where(datadf['Date'].str.contains('20260[2|1]'),0.4,0.8))
    # _cell_const_err = np.where(datadf['Date']=='20260422',0.04, np.where(datadf['Date'].str.contains('20260[2|1]'),0.2,0.4))
    datadf['Kappa'] = _cell_const / datadf['Rsoln']
    # propagate independent relative errors from the cell constant fit and Rsoln (SEM) in quadrature
    datadf['Kappa_err'] = datadf['Kappa'] * np.sqrt(
        (_cell_const_err / _cell_const) ** 2 + (datadf['Rsoln_SEM'] / datadf['Rsoln']) ** 2
    )

    _moles_h2s, _moles_additive, _moles_il, _x_h2s, _liquid_vol_total = compute_mole_fraction_h2s(
        datadf, ADDITIVE_PROPERTIES, IONIC_LIQUID_PROPERTIES
    )
    datadf['moles H2S'] = _moles_h2s
    datadf['moles Additive'] = _moles_additive
    datadf['moles IL'] = _moles_il
    datadf['Mole Fraction H2S'] = _x_h2s
    datadf['Mole Frac Err'] = 0.025*datadf['Mole Fraction H2S']
    datadf['Mole Fraction IL'] = _moles_il/(_moles_il+_moles_h2s+_moles_additive)
    datadf['Mole Fraction Cosolvent'] = _moles_additive/(_moles_il+_moles_h2s+_moles_additive)
    datadf['Liquid Volume'] = _liquid_vol_total
    datadf['Total Volume'] = datadf['Gas Volume'].fillna(0) / GAS_HEADSPACE_VOLUME_CM3 + datadf['Liquid Volume']

    _no_pressure = datadf['Pressure'].isna()
    # when Pressure is missing, fall back to a fixed linear estimate from the
    # nominal (filename) Temperature, with a hard-coded +/- 4 K uncertainty
    datadf['Temperature Est'] = np.where(
        _no_pressure,
        0.5 * datadf['Temperature'] + 100,
        InvAntoine(A_h2s, B_h2s, C_h2s, datadf['Pressure']),
    )
    # propagate a hard-coded 1% relative error on Pressure through InvAntoine:
    # T = B/(A - log10(P/750)) - C  =>  dT/dP = T'(P) = (T+C)^2 / (B * ln(10) * P)
    # so for dP = PRESSURE_REL_ERR * P, dT = PRESSURE_REL_ERR * (T+C)^2 / (B*ln(10))
    datadf['Temperature Est Err'] = np.where(
        _no_pressure,
        4,
        PRESSURE_REL_ERR * (datadf['Temperature Est'] + C_h2s) ** 2 / (B_h2s * np.log(10)),
    )
    datadf
    return (datadf,)


@app.cell
def _(mo):
    export_filename = mo.ui.text(value='eis_data_analysis.csv', label='Export filename')
    export_button = mo.ui.run_button(label='Export to CSV')
    mo.hstack([export_filename, export_button])
    return export_button, export_filename


@app.cell
def _(datadf, export_button, export_filename, mo):
    mo.stop(not export_button.value, mo.md("Click 'Export to CSV' above to save the data analysis table."))
    datadf.to_csv(export_filename.value, index=False)
    mo.md(f"Saved {len(datadf)} rows to `{export_filename.value}`.")
    return


@app.cell
def _(datadf, scatter_vs_metadata):
    top = scatter_vs_metadata(
        datadf, x='Temperature Est', y='Kappa', color ='Temperature Est', shape ='Additive',log_y=True,
        title='Conductivity vs. Temperature', tooltip=['Measurement', 'Rsoln', 'Kappa_err'],
        xerr='Temperature Est Err', yerr='Kappa_err'  
    )
    bottom = scatter_vs_metadata(
        datadf, x='Mole Fraction H2S', y='Kappa', color ='Temperature Est', shape ='Additive',log_y=True,
        title='Conductivity vs. Mole Fraction', tooltip=['Measurement', 'Rsoln', 'Kappa_err'],
        xerr='Mole Frac Err', yerr='Kappa_err'  
    )
    top|bottom
    return


@app.cell
def _(datadf, np):
    subdf = datadf.iloc[np.where((datadf['Temperature Est']>200)&(datadf['Mole Fraction H2S']>0.6))]
    sumdf = (
        subdf.groupby('Additive')
            .agg(
                Rsoln=('Rsoln', 'mean'),
                Kappa=('Kappa', 'mean'),
                Kappa_stdev=('Kappa', 'std'),
                Kappa_max=('Kappa', 'max'),
                Kappa_min=('Kappa','min'),
                Temp_max=('Temperature Est','max'),
                Temp_min=('Temperature Est','min'),
                Xh2s_max=('Mole Fraction H2S','max'),
                Xh2s_min=('Mole Fraction H2S','min'),
                XIL_max=('Mole Fraction IL','max'),
                XIL_min=('Mole Fraction IL','min'),
                Xcos_max=('Mole Fraction Cosolvent','max'),
                Xcos_min=('Mole Fraction Cosolvent','min')
            )
    )
    sumdf
    return


@app.cell
def _(boxplot_by_category, datadf):
    boxplot_by_category(datadf, category='Additive', color='Temperature Est', value='Kappa', log_y=True)
    return


@app.cell
def _(mo):
    mo.md("""
    ## 3. Further data analysis
    """)
    return


@app.cell
def _(mo):
    trend_browser = mo.ui.file_browser(filetypes=['.csv'], multiple=False, label='Select a saved CSV file')
    trend_browser
    return (trend_browser,)


@app.cell
def _(mo, pd, trend_browser):
    mo.stop(not trend_browser.value, mo.md("Select a CSV file above to begin."))
    trenddf = pd.read_csv(trend_browser.value[0].path)
    return (trenddf,)


@app.cell
def _(mo, trenddf):
    metadata_options = [
        c for c in ['Temperature', 'Pressure', 'Gas Volume', 'Liquid Volume', 'Total Volume', 'Mole Fraction H2S', 'Date']
        if c in trenddf.columns
    ]
    mo.stop(not metadata_options, mo.md("No recognized metadata columns found in this CSV."))
    metadata_dropdown = mo.ui.dropdown(options=metadata_options, value=metadata_options[0], label='Plot Kappa vs.')
    metadata_dropdown
    return (metadata_dropdown,)


@app.cell
def _(metadata_dropdown, scatter_vs_metadata, trenddf):
    scatter_vs_metadata(
        trenddf, x=metadata_dropdown.value, y='Kappa', log_y=True,
        title=f'Kappa vs. {metadata_dropdown.value}', tooltip=['Measurement'],
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ### Arrhenius trend

    `ln(Kappa)` vs. `1000/Temperature`, with a linear fit used to estimate an
    apparent activation energy.
    """)
    return


@app.cell
def _(mo, np, trenddf):
    mo.stop(
        not {'Temperature', 'Kappa'}.issubset(trenddf.columns),
        mo.md("CSV must contain `Temperature` and `Kappa` columns for the Arrhenius trend."),
    )
    arrhenius_df = trenddf.copy()
    arrhenius_df['invT'] = 1000 / arrhenius_df['Temperature']
    arrhenius_df['logKappa'] = np.log(arrhenius_df['Kappa'])
    return (arrhenius_df,)


@app.cell
def _(alt, arrhenius_df):
    arrhenius_points = alt.Chart(arrhenius_df).mark_point(size=70).encode(
        x=alt.X('invT', title='1000/T (1/K)'),
        y=alt.Y('logKappa', title='ln(Kappa)'),
        tooltip=['Temperature', 'Rsoln', 'Measurement'],
    )
    arrhenius_line = arrhenius_points.transform_regression('invT', 'logKappa').mark_line(
        color='black', strokeDash=[5, 5]
    )
    (arrhenius_points + arrhenius_line).properties(title='Arrhenius Plot', width=400, height=400).interactive()
    return


@app.cell
def _(arrhenius_df, getslope, mo, slope_to_Ea):
    arrhenius_slope = getslope(arrhenius_df)
    arrhenius_Ea = slope_to_Ea(arrhenius_slope)
    mo.md(f"**Apparent activation energy:** {arrhenius_Ea:.2f} kJ/mol")
    return


if __name__ == "__main__":
    app.run()
