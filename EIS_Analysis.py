import marimo

__generated_with = "0.23.15"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import numpy as np
    from plotly.subplots import make_subplots
    import altair as alt
    import matplotlib.pyplot as plt
    import re,os

    return alt, mo, np, os, pd, plt, re


@app.cell
def _(os):
    import shutil

    cache_dir = '.marimo'
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)

    # basepath = r'C:\Users\oschn\Dropbox (MIT)\jaramillogroupshared\Data\Jaramillo lab\CryoEchem'
    basepath = r'/Users/ods/MIT Dropbox/Olivia Schneble/jaramillogroupshared/Data/Jaramillo lab/CryoEchem/Gamry Data'

    return (basepath,)


@app.cell
def _(alt, pd):
    molarity = [0.01,0.02,0.04,0.06,0.08,0.1] #M
    kappa = [1.2,2.3,4.36,6.34,8.03,9.82] #mS/cm
    nacldf = pd.DataFrame({'Molarity':molarity,'Conductivity (mS/cm)':kappa})
    testchart = alt.Chart(nacldf).mark_line(point=True,strokeDash=[5,5]).encode(
        x='Molarity',
        y='Conductivity (mS/cm)'
    )
    rhofit = testchart.transform_regression( 'Molarity', 'Conductivity (mS/cm)', params=True).transform_calculate().mark_text(align='left').encode(x=alt.value(20),  # pixels from left
        y=alt.value(20),  # pixels from top
        text='coef:N')

    testchart.interactive()+rhofit
    return


@app.cell
def _():
    kappa_10mM_NaCl = 1.2e-3 #S/cm
    kappa_100mM_NaCl = 10e-3 #S/cm
    kappa_5mM_NaCl = 0.9e-3 #S/cm
    return (kappa_10mM_NaCl,)


@app.cell(hide_code=True)
def _(os, pd):
    def meas_sweep_to_dataframe(file_path):
        """ takes impedance analyzer .txt data and returns dtaframe matching gamry"""
        df0 = pd.read_csv(file_path,sep=',',header=6)
        n = len(df0) // 2
        df = pd.concat([
            df0.iloc[:n].set_axis(['Frequency', 'Impedance'], axis=1),
            df0.iloc[n:, 1].rename('Phase').reset_index(drop=True)
        ], axis=1)
        df=df.rename(columns={'Frequency':'Freq','Impedance':'Zmod','Phase':'Zphz'})
        df['Measurement'] = os.path.basename(file_path)
        return df

    return


@app.cell(hide_code=True)
def _(np, os, pd, re):
    ## Helper Functions to Load Data
    def read_gamry_EIS_dta(file_path):
        """
        Imports a Gamry .DTA file as a pandas DataFrame. Looks for 'ZCURVE' data.

        Args:
            file_path (str): The path to the .DTA file.

        Returns:
            df (pd.DataFrame): The experimental data.
        """
        header_row_idx = 0

        # 1. Scan the file to find the start of the data table
        # We use 'latin-1' encoding because Gamry files often contain 
        # non-standard symbols (like µ or degree signs).
        with open(file_path, 'r', encoding='latin-1') as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                # Gamry data tables usually follow a line containing "CURVE" and "TABLE"
                # e.g., "ZCURVE \t TABLE" or "CURVE \t TABLE"
                # print(line)
                if 'ZCURVE' in line and 'TABLE' in line:
                    header_row_idx = i + 1
                    continue
                if 'ABORTED' in line:
                    footer = 1
                    break
                else:
                    footer=0

        # 2. Read the data using the detected header location
        # We skip the footer because Gamry sometimes writes status messages 
        # (like "EXPERIMENT ABORTED") at the very end that break float parsing.
        try:
            df = pd.read_csv(
                file_path, engine='python',
                sep='\t', 
                header=[header_row_idx,header_row_idx+1], 
                encoding='latin-1',
                skipfooter=footer,
                on_bad_lines='skip' # Skips footer text garbage if present
            )
            df['Measurement'] = os.path.basename(file_path)
        except Exception as e:
            print(f"Error reading file: {e}")
            return None

        return df

    def EIS_csv_to_df(csv_file,searchphrase=None):
        """
        Reads csv created manually from copying EIS data out of Echem Analyst
        Inputs: csv_file (str) and 'searchphrase' (str), filters for filename w/ 'searchphrase'
        Returns: 3D dataframe of combined measurements
        """
        df = pd.read_csv(csv_file,header=1)
        measurement_list = pd.read_csv(csv_file).columns
        df = df.dropna(axis=1,how='all')
        headers = df.columns.tolist()
        measurements = {}
        for i in range(0, len(headers), 3):
            if i + 2 < len(headers):
                freq_col = headers[i]
                zmod_col = headers[i + 1]
                zphz_col = headers[i + 2]

                # Extract measurement name (try to get from first row or use column names)
                measurement_name = measurement_list[i]

                # Store data (convert to numeric, coerce errors to NaN)
                # zmod = pd.to_numeric(df[zmod_col], errors='coerce').dropna().values,
                # zphz = pd.to_numeric(df[zphz_col], errors='coerce').dropna().values,
                zmod = df[zmod_col]
                zphz = df[zphz_col]
                measurements[measurement_name] = {
                    'Freq': pd.to_numeric(df[freq_col], errors='coerce').dropna().values,
                    'Zreal': pd.to_numeric(zmod*np.cos(zphz*np.pi/180),errors='coerce').dropna().values,
                    'Zimag': pd.to_numeric(zmod*np.sin(zphz*np.pi/180),errors='coerce').dropna().values,
                    'Zmod': pd.to_numeric(df[zmod_col], errors='coerce').dropna().values,
                    'Zphz': pd.to_numeric(df[zphz_col], errors='coerce').dropna().values           
                }
        mega_df = pd.DataFrame(measurements)
        return mega_df

    def EIS_csv_to_df_alt(csv_file,searchphrase=None):
        """
        Reads csv created manually from copying EIS data out of Echem Analyst
        Inputs: csv_file (str) and 'searchphrase' (str), filters for filename w/ 'searchphrase'
        Returns: 2D dataframe of combined measurements, where measurement name is a column
        """
        measurement_list = pd.read_csv(csv_file).columns[::3] # top-level header
        df = pd.read_csv(csv_file,header=1) # second level header
        freqlist = []
        zmodlist = []
        zphzlist = []
        namelist = []
        for (ind,name) in enumerate(measurement_list):
            if (searchphrase == None) or re.search(searchphrase,name):
                freqs = df.iloc[:,3*ind].dropna().tolist()
                freqlist.extend(freqs)
                zmodlist.extend(df.iloc[:,3*ind+1].dropna().tolist())
                zphzlist.extend(df.iloc[:,3*ind+2].dropna().tolist())
                namelist.extend([name]*len(freqs))

        bigdf = pd.DataFrame({'Measurement':namelist, 'Freq':freqlist, 'Zmod':zmodlist, 'Zphz':zphzlist})
        bigdf['Zreal']=bigdf['Zmod']*np.cos(bigdf['Zphz']*np.pi/180)
        bigdf['Zreal']=bigdf['Zmod']*np.sin(bigdf['Zphz']*np.pi/180)
        return bigdf

    from io import StringIO

    def read_gamry_dta_alt(path):
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        # Find where the data block begins
        start = None
        for i, line in enumerate(lines):
            if line.strip().startswith("ZCURVE"):
                start = i
                break
        if start is None:
            raise ValueError("ZCURVE marker not found")

        # Keep everything after the ZCURVE line
        data_lines = lines[start+1:]

        # Remove unit row(s) and any trailing error/abort lines
        cleaned = []
        for ln in data_lines:
            s = ln.strip()
            if not s:
                continue
            if s.startswith("#"):          # units row
                continue
            if "Measurement aborted" in s:
                continue
            cleaned.append(ln)

        # Read as strings first to avoid dtype mixing
        df = pd.read_csv(
            StringIO("".join(cleaned)),
            sep="\t",
            header=0,          # first remaining line is the column header
            dtype=str,
            engine="python"
        )

        # Optional: convert numeric columns
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df['Measurement'] = os.path.basename(path)
        return df

    return (read_gamry_dta_alt,)


@app.cell(hide_code=True)
def _(alt, np, pd, plt, re):
    ## Helper Fucntions to Plot Data
    def single_nyquist(data):
        df = data.copy()
        # 2. FLATTEN HEADERS: Check if it's a MultiIndex (2-level header)
        if isinstance(df.columns, pd.MultiIndex):
            # This keeps the top level (e.g., 'Freq', 'Zmod') and drops the units
            df.columns = df.columns.get_level_values(0)
        # Create a column for -Z'' so it plots correctly
        df['NegZimag'] = -1*df['Zimag']
        # Create a Log Frequency column for coloring (optional but recommended)
        df['LogFreq'] = np.log10(df['Freq'])
        chart = alt.Chart(df).mark_circle(size=60).encode(
            x=alt.X('Zreal', title="Z' (Ohm)", scale=alt.Scale(zero=False)),
            y=alt.Y('NegZimag', title="-Z'' (Ohm)", scale=alt.Scale(zero=False)),
            # Color points by Frequency (using a spectral scale usually looks nice)
            color=alt.Color('LogFreq', title='log(Freq)', scale=alt.Scale(scheme='turbo')),

            # What shows up when you hover
            tooltip=[
                alt.Tooltip('Freq', format='.2e', title='Frequency (Hz)'),
                alt.Tooltip('Zreal', format='.1f', title="Z'"),
                alt.Tooltip('NegZimag', format='.1f', title="-Z''"),
                alt.Tooltip('Zphz', format='.1f', title="Phase (deg)")
            ]
        ).properties(
            title='Nyquist Plot',
            width=600,
            height=600
        ).interactive() # Enables Zoom and Pan
        return chart
    def plot_dual_bode(data, groupby=None, title="Bode Plot"):
        """
        Creates an interactive dual-axis Bode plot (Magnitude & Phase vs Freq).
        """
        # 1. FLATTEN HEADERS (Handle Gamry 2-level structure)
        df = data.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 3. Create a Base Chart (Shared X-axis: Frequency)
        base = alt.Chart(df).encode(
            x=alt.X(
                'Freq', 
                scale=alt.Scale(type='log'), # Bode plots always use Log Freq
                title='Frequency (Hz)'
            ),
            tooltip=[
                alt.Tooltip(groupby if groupby is not None else ' '),
                alt.Tooltip('Freq', format='.2e', title='Freq (Hz)'),
                alt.Tooltip('Zmod', format='.2s', title="|Z| (Ohm)"),
                alt.Tooltip('Zphz', format='.1f', title="Phase (°)")
            ]
        )

        # 4. Layer 1: Impedance Modulus (|Z|) - LEFT AXIS
        # We use scale(type='log') for the Y-axis
        mag_chart = base.mark_line(point=True).encode(
            y=alt.Y(
                'Zmod', 
                scale=alt.Scale(type='log'), 
                title='|Z| (Ohm)'
                # axis=alt.Axis(titleColor=color_mag, labelColor=color_mag)
            ),
            color= groupby if groupby is not None else alt.value("#0f4c75")
        )

        # 5. Layer 2: Phase Angle - RIGHT AXIS
        # Linear scale for degrees
        phase_chart = base.mark_line(point=True,strokeDash=[3,3]).encode(
            y=alt.Y('Zphz', 
                # scale=alt.Scale(domain=[-90, 0] if df['Phase'].max() <= 0 else [-90, 90]), 
                title='Phase Angle (°)'
                # axis=alt.Axis(titleColor=color_phase, labelColor=color_phase)
            ),
            color=groupby if groupby is not None else alt.value("#ee8430")
        )

        # 6. Combine and Resolve Scales independently
        chart = (mag_chart | phase_chart).properties(
            title=title
            # width=600,
            # height=400
        ).interactive()

        return chart

    def plot_bode(data,group=None, title="Bode Plot"):
        """
        Creates an interactive dual-axis Bode plot (Magnitude & Phase vs Freq).
        """
        # 1. FLATTEN HEADERS (Handle Gamry 2-level structure)
        df = data.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 2. Define Colors for the two axes
        color_mag = "#0f4c75"  # Blue
        color_phase = "#ee8430"  # Orange

        # 3. Create a Base Chart (Shared X-axis: Frequency)
        base = alt.Chart(df).encode(
            x=alt.X(
                'Freq', 
                scale=alt.Scale(type='log'), # Bode plots always use Log Freq
                title='Frequency (Hz)'
            ),
            tooltip=[
                alt.Tooltip('Freq', format='.2e', title='Freq (Hz)'),
                alt.Tooltip('Zmod', format='.2s', title="|Z| (Ohm)"),
                alt.Tooltip('Zphz', format='.1f', title="Phase (°)")
            ]
        )

        # 4. Layer 1: Impedance Modulus (|Z|) - LEFT AXIS
        # We use scale(type='log') for the Y-axis
        mag_chart = base.mark_line(point=True).encode(
            y=alt.Y(
                'Zmod', 
                scale=alt.Scale(type='log'), 
                title='|Z| (Ohm)',
                axis=alt.Axis(titleColor=color_mag, labelColor=color_mag)
            ),
            color= (group if group is not None else alt.value(color_mag))
        )

        # 5. Layer 2: Phase Angle - RIGHT AXIS
        # Linear scale for degrees
        phase_chart = base.mark_line(point=True,strokeDash=[5,5]).encode(
            y=alt.Y('Zphz', 
                scale=alt.Scale(domain=[-90, 0] if df['Zphz'].max() <= 0 else [-90, 90]), 
                title='Phase Angle (°)',
                axis=alt.Axis(titleColor=color_phase, labelColor=color_phase)
            ),
            color= (group if group is not None else alt.value(color_phase))
        )

        # 6. Combine and Resolve Scales independently
        chart = alt.layer(mag_chart, phase_chart).resolve_scale(
            y='independent'
        ).properties(
            title=title,
            width=600,
            height=400
        ).interactive()

        return chart

    def multi_EIS_bode_Ru(bigDF,searchphrase=None,tmin=150, tmax=200,showplot=True):
        ''' Takes multi-measurement dataframe, takes the ones with searchphrase in the title
        extracts Rsolution (avg(Zmod) wherever Zphz = 0), shows Bode plot by default
        Assumes filename contains info like '620cm3H2S_183K_190Torr'
        '''

        if showplot:
            fig,(ax1,ax2) = plt.subplots(2,1,figsize=(12,10))

        measurements = bigDF.columns

        templist = []
        pressurelist = []
        volumelist = []
        Rulist = []
        # tmax = max(templist_total)
        # tmin = min(templist_total)
        crange = int(tmax-tmin)
        colors = plt.cm.coolwarm(np.linspace(0, 1, num=crange+1))
        # print(tmin,tmax)
        for idx, name in enumerate(measurements):
            if (searchphrase == None) or re.search(searchphrase,name):
                # print(name)
                data = bigDF[name]
                ## extract metadata
                try:
                    newtemp = float(re.search(r'\d+K',name).group(0)[0:3])
                    newvolume = float(re.search(r'\d+cm3',name).group(0)[0:3])
                except:
                    print(f'{name} does not contain metadata with correct format')
                    continue

                newpressure = (re.search(r'\d+Torr',name).group(0) if re.search(r'\d+Torr',name) else '100Torr')
                # extract temp and add to list
                templist.append(newtemp)
                pressurelist.append(float(re.search(r'\d+',newpressure).group(0)))
                volumelist.append(newvolume)
                # extract Ru and add to list
                Ru = data['Zmod (ohm)'][abs(data['Zphz (deg)'])<10]
                Rufreq = data['Freq (Hz)'][abs(data['Zphz (deg)'])<10]
                Rulist.append(Ru.mean())
                if showplot:
                    # color index for shading by colog
                    # temp_ = float(re.search(r'\d+K',name).group(0)[0:3])
                    cind = int(newtemp-tmin)
                    l1, = ax1.loglog(data['Freq (Hz)'], data['Zmod (ohm)'], marker='o', markersize=4, linewidth=2,label=name, color=colors[cind], alpha=0.8)
                    ax1.scatter(Rufreq.mean(),Ru.mean(),color='red')
                    l2, = ax2.semilogx(data['Freq (Hz)'], data['Zphz (deg)'], marker='s', markersize=4, linewidth=2, label=name, color=colors[cind], alpha=0.8)

        if showplot:
            ## Format Plots
            ax1.set_title('Bode Plot - Magnitude', fontsize=14, fontweight='bold')
            ax1.grid(True, which='both', alpha=0.3, linestyle='--')
            # ax1.legend(loc='best', fontsize=10, framealpha=0.9)
            ax1.legend(loc='center left', bbox_to_anchor=(1, 0.5))
            # Format phase plot
            ax2.set_xlabel('Frequency (Hz)', fontsize=12, fontweight='bold')
            ax2.set_ylabel('Phase (°)', fontsize=12, fontweight='bold')
            ax2.set_title('Bode Plot - Phase', fontsize=14, fontweight='bold')
            ax2.grid(True, which='both', alpha=0.3, linestyle='--')
            # ax2.legend(loc='best', fontsize=10, framealpha=0.9)
            ax2.legend(loc='center left', bbox_to_anchor=(1, 0.5))
            plt.show()
        return(templist,pressurelist,volumelist,Rulist)

    def multi_EIS_bode_Alt(df,title='Bode Plot with Temperature',show_ru = False):
        newdf = df.copy()
        newdf['Temperature'] = newdf['Measurement'].str.extract(r'(\d+)K')
        bode = alt.Chart(newdf).mark_line().encode(
            x=alt.X('Freq',scale=alt.Scale(type='log'),title='Frequency (Hz)'),
            color = 'Measurement',
             # Condition: If Temp is valid, use gradient. If invalid (NaN), use Gray.
            # color=alt.condition('isValid(datum.Temperature)', # Check if valid
            # alt.Color('Temperature:Q', scale=alt.Scale(type='linear',scheme='redblue',reverse=True, domain=[175, 200])), 
            # alt.value('gray') # False (NaNs)
            # ),
        ).properties(title=title)
        magplot = bode.mark_line(point=True).encode(
            y=alt.Y('Zmod',scale=alt.Scale(type='log'),title='|Z| Ohms'),
            tooltip = ['Measurement']
            # color = 'Measurement'
        )
        phaseplot = bode.mark_line(point=True).encode(
            y=alt.Y('Zphz',title='Phase (Deg)'),
            tooltip = ['Measurement']
            # color='Measurement'
        )
        if show_ru:
            freqpts = newdf[newdf['Zphz'].abs()<10].groupby('Measurement')['Freq'].mean()
            magpts = newdf[newdf['Zphz'].abs()<10].groupby('Measurement')['Zmod'].mean()
            scatterdf = pd.DataFrame({'Freq':freqpts,'Zmod':magpts})
            scatter = alt.Chart(scatterdf).mark_point(color='red').encode(x='Freq',y='Zmod')
            bode = (magplot+scatter) | phaseplot
        else:
            bode = magplot | phaseplot
        return bode



    def parse_multi_EIS_alt(df,tempstring =r'(\d+)K', presstring = r'(\d+)[T|t]orr', gasvolstring = r'(\d+)cm3', liqvolstring=r'(\d+)mL',searchphrase=None, showbode=False):
        if showbode:
            plot = multi_EIS_bode_Alt(df,show_ru=True)
        if searchphrase is not None:
            newdf = df[df['Measurement'].str.contains(searchphrase)]
        else:
            newdf = df.copy()
        subdf = newdf[newdf['Zphz'].abs()<10].groupby('Measurement')['Zmod'].mean().reset_index(name='Rsoln')
        subdf['Temperature'] = subdf['Measurement'].str.extract(tempstring).astype('float')
        subdf['Pressure'] = subdf['Measurement'].str.extract(presstring).astype('float')
        subdf['Gas Volume'] = subdf['Measurement'].str.extract(gasvolstring).astype('float')
        subdf['Liquid Volume'] = subdf['Measurement'].str.extract(liqvolstring, expand=False).str.replace('p', '.') .astype(float)
        # subdf['Liquid Volume'] = subdf['Measurement'].str.extract(r'(\d+(?:p\d+)?)[u|m]L', expand=False).str.replace('p', '.') .astype(float)
        # subdf['Liquid Volume'] = subdf['Measurement'].str.extract(liqvolstring).astype('float')
        if showbode:
            return plot, subdf
        else:
            return subdf


    def parse_multi_EIS(df,tempstring =r'\d+K', presstring = r'\d+[T|t]orr', gasvolstring = r'\d+cm3', liqvolstring=r'\d+mL'):
        newdf = df.copy()
        subdf = newdf[newdf['Zphz'].abs()<10].groupby('Measurement')['Zmod'].mean()
        gasvollist = []
        liqvollist = []
        templist = []
        presslist = []
        rulist = []
        for (index,value) in subdf.items():
            try:
                gasvollist.append(re.search(gasvolstring,index).group(0))
            except:
                gasvollist.append(np.nan)
                print(f'No gas volume found in {index}')
            try:
                liqvollist.append(re.search(liqvolstring,index).group(0))
            except:
                liqvollist.append(np.nan)
                print(f'No liquid volume found in {index}')
            try: 
                templist.append(re.search(tempstring,index).group(0))
            except:
                templist.append(np.nan)
                print(f'No temperature found in {index}')
            try:
                presslist.append(re.search(presstring,index).group(0))
            except:
                presslist.append(np.nan)
                print(f'No pressure found in {index}')
            try:
                rulist.append(value)
            except:
                rulist.append(np.nan)
                print(f'Failed to append Rsoln in {index}')

        return_df = pd.DataFrame({
            'Gas Volume':gasvollist, 'Liquid Volume':liqvollist, 'Pressure':presslist, 'Temperature':templist, 'Rsoln':rulist
        })
        return return_df

    return parse_multi_EIS_alt, plot_dual_bode


@app.cell
def _(mo, pd, read_gamry_dta_alt):
    def file_browser_to_dataframe(browser):
        combined_df = pd.DataFrame()

        # file_browser.value is a list of FileInfo objects
        if browser.value:
            dfs = []

            for file_info in browser.value:
                # file_info.path gives the absolute path on disk
                processed_data = read_gamry_dta_alt(file_info.path)

                if processed_data is not None:
                    dfs.append(processed_data)

            if dfs:
                combined_df = pd.concat(dfs, ignore_index=True)

                # Show a quick summary
                mo.output.replace(
                    mo.md(f"**Loaded {len(dfs)} files.** Total data points: {len(combined_df)}")
                )
            else:
                mo.output.replace(mo.md("Selected files do not contain valid ZCURVE data."))
        else:
            mo.output.replace(mo.md("No files selected."))

        if isinstance(combined_df.columns, pd.MultiIndex):
                # This keeps the top level (e.g., 'Freq', 'Zmod') and drops the units
                combined_df.columns = combined_df.columns.get_level_values(0)
        return combined_df

    return (file_browser_to_dataframe,)


@app.cell
def _(basepath, mo):
    # basepath = r'C:\Users\oschn\Dropbox (MIT)\jaramillogroupshared\Data\Jaramillo lab\CryoEchem'
    browser = mo.ui.file_browser(initial_path=basepath,multiple=True,selection_mode='file',label='Select Gamry .dta files for calibration...')
    return (browser,)


@app.cell
def _(browser):
    browser
    return


@app.cell
def _(
    browser,
    file_browser_to_dataframe,
    kappa_10mM_NaCl,
    parse_multi_EIS_alt,
    plot_dual_bode,
):
    caldata = file_browser_to_dataframe(browser)
    bplot = plot_dual_bode(caldata,groupby='Measurement')
    caldf = parse_multi_EIS_alt(caldata,liqvolstring=r'(\d+)uL')
    caldf['Cell Constant'] = round(caldf['Rsoln']*kappa_10mM_NaCl,ndigits=3)

    caldf
    return (caldf,)


app._unparsable_cell(
    r"""
    def nacl_molarity_fit(molarity):
        klist = []
        for m in molarity:
            klist.append(1e-3*(0.4+95*m))
        return klist

    Mlist = [0.001,0.01,0.1,1]
    Rlist = [1e3,120,13,2]
    kappalist = nacl_molarity_fit(Mlist) #expected conductivity
    Ccell = [round(r*k,ndigits=3) for r,k in zip(Rlist,kappalist)]
    bplot.properties(title=f'Calibration for 10 mM NaCl in H2O. Cell Constants:{caldf['Cell Constant'].values}')
    """,
    name="_"
)


@app.cell
def _(caldf):
    c1 = caldf['Cell Constant'][0:6].mean()
    c2 = caldf['Cell Constant'][6:12].mean()
    c3 = caldf['Cell Constant'][-3:-1].mean()
    print(c1,c2,c3)
    #cell const Nov 2025 = 0.001 cm-1
    # cell const Dec 2025 = 2kohm/18Mohmcm = 0.0001 cm-1... a whole order of magnitude seems wrong
    # cell const Jan 26 = 20k/18 MOhm cm = 0.001, 110k/18 Mohm cm = 0.006
    # cell constants from NaCl more like 0.1 cm-1
    # cell const from 11/11 NaCl 0.16
    return (c1,)


@app.cell(hide_code=True)
def _(alt, caldf):


    calpoints = alt.Chart(caldf).mark_point().encode(
        x=alt.X('Liquid Volume',scale=alt.Scale(type='linear')),
        y=alt.Y('Rsoln',scale=alt.Scale(type='linear'))
    )
    cellpoints = alt.Chart(caldf).mark_point(size=90).encode(
        x=alt.X('Liquid Volume'),
        y=alt.Y('Cell Constant',scale=alt.Scale(type='linear')),
        tooltip=['Liquid Volume','Cell Constant']
    )
    fitline = cellpoints.transform_regression(
        on='Liquid Volume',regression='Cell Constant'
    ).mark_line(color='black',strokeDash=[5,5]).encode(
    )

    params = cellpoints.transform_regression('Liquid Volume','Cell Constant',params=True).transform_calculate(
        intercept='datum.coef[0]',
        slope='datum.coef[1]',
    ).mark_text(align='left').encode(
        x=alt.value(20),  # pixels from left
        y=alt.value(20),  # pixels from top
        text='coef:N'
    )

    ptplot = (calpoints + cellpoints).resolve_scale(y='independent')
    ptplot.interactive()
    (cellpoints + fitline + params).properties(title='10mM NaCl SS Foil Electrodes Calibration').interactive()
    return


@app.cell
def _():
    def resistance_to_kappa(resistance,volume):
        ''' Takes resistance value in ohms, returns kappa in Siemens/cm based on cell constant'''
        cell = 1.28 - 0.45*volume
        kappa = cell/resistance
        return kappa

    def calcCellConst(volume):
        return 2.0-0.49*volume

    return (resistance_to_kappa,)


@app.cell
def _(basepath, mo):
    browser1 = mo.ui.file_browser(initial_path=basepath,multiple=True,selection_mode='file',label='Select Gamry .dta files...')
    return (browser1,)


@app.cell
def _(browser1):
    browser1
    return


@app.cell
def _(browser1, file_browser_to_dataframe):
    h2sdf = file_browser_to_dataframe(browser1)
    # extradf = meas_sweep_to_dataframe(r"C:\Users\oschn\MIT Dropbox\Olivia Schneble\jaramillogroupshared\Data\Jaramillo lab\CryoEchem\Impedance Analyzer\meas_sweep_20251120_153927.txt")
    # h2sdf =pd.concat((h2sdf,extradf),ignore_index=True)
    _minphase = h2sdf.groupby('Measurement',as_index=False)["Zphz"].max()
    _good_measurements = _minphase[abs(_minphase['Zphz'])<20]
    h2ssubdf = h2sdf[h2sdf["Measurement"].isin(_good_measurements['Measurement'])]
    return h2sdf, h2ssubdf


@app.cell
def _(h2sdf, h2ssubdf, plot_dual_bode):
    # bodeplot, h2sdata = parse_multi_EIS_alt(newdf,showbode=True)
    # h2sdata['Total Volume'] = h2sdata['Gas Volume']/620
    # h2sdata['Kappa'] = resistance_to_kappa(h2sdata['Rsoln'],h2sdata['Total Volume'])
    h2sdf['Date'] = h2sdf['Measurement'].str.extract(r"(202\d+)_")
    # minidf = h2sdf[h2sdf['Date']=='20251120']
    plot_dual_bode(h2ssubdf,groupby='Measurement')
    return


@app.cell
def _(h2ssubdf, np, parse_multi_EIS_alt):
    synthesis=parse_multi_EIS_alt(h2ssubdf,liqvolstring=r'(\d+)mL')
    synthesis['Gsoln']=1/synthesis['Rsoln']
    synthesis['Date'] = synthesis['Measurement'].str.extract(r"(202\d+)_")
    synthesis['Gas Volume'] = np.where(synthesis['Date']=='20260610',820,synthesis['Gas Volume'])
    synthesis['Liquid Volume'] = np.where(synthesis['Date'] == '20260501',1,np.where(synthesis['Date'] == '20260305', 1,synthesis['Liquid Volume']/1000))#mL
    synthesis['Liquid Volume'] = 0.0 #mL
    # synthesis['Gas Volume'] = synthesis['Gas Volume'].fillna(0)
    synthesis['Total Volume'] = synthesis['Gas Volume']/620 + synthesis['Liquid Volume']
    # synthesis['CellConst'] = 0.15-0.05*synthesis['Total Volume']
    synthesis['CellConst'] = np.where(synthesis['Date'].str.contains('202604'),0.08,0.8)
    synthesis['Kappa'] = synthesis['CellConst']/synthesis['Rsoln']
    synthesis['Solvent'] = np.where(synthesis['Measurement'].str.contains(r"(sulf)"), 'IL+Sulfolane', np.where(synthesis['Measurement'].str.contains(r"(S3MS)"),'IL+Sulfolane', np.where(synthesis['Measurement'].str.contains(r"Pyr"),'IL+Pyridine',np.where(synthesis['Measurement'].str.contains(r"(PC)"),'IL+PC','IL only'))))
    # synthesis
    return (synthesis,)


@app.cell
def _(alt, synthesis):
    # boxplot1 = alt.Chart(synthesis).mark_boxplot(extent='min-max').encode(
    #     x='Date:N',
    #     y=alt.Y('Rsoln:Q',scale=alt.Scale(type='log'),axis=alt.Axis(format='.2s')),
    #     tooltip=[
    #             alt.Tooltip('Measurement'),
    #             alt.Tooltip('Rsoln', format='.2s', title="|Z| (Ohm)")
    #             # alt.Tooltip('Zphz', format='.1f', title="Phase (°)")
    #         ]
    #     # color='Temperature:Q'
    # ).properties(width=300)
    # boxplot2 = alt.Chart(synthesis).mark_boxplot(extent='min-max').encode(
    #     x='Date:N',
    #     y=alt.Y('Kappa:Q',scale=alt.Scale(type='log'),axis=alt.Axis(format='.2s')),
    #     tooltip=[
    #             alt.Tooltip('Measurement'),
    #             alt.Tooltip('Rsoln', format='.2s', title="|Z| (Ohm)")
    #             # alt.Tooltip('Zphz', format='.1f', title="Phase (°)")
    #         ]
    #     # color='Temperature:Q'
    # ).properties(width=300)
    # (boxplot1 | boxplot2)
    base_x = alt.X('Date:N', axis=alt.Axis(title='Date',labelAngle=-45))

    # Box + points for Rsoln
    box1 = alt.Chart(synthesis).mark_boxplot(extent='min-max',opacity=0.7).encode(
        x=base_x,
        y=alt.Y('Gsoln:Q',
                scale=alt.Scale(type='log'),
                axis=alt.Axis(format='.2s'))
    )

    points1 = alt.Chart(synthesis).mark_circle(size=40, opacity=0.6).encode(
        x=base_x,
        y=alt.Y('Gsoln:Q', scale=alt.Scale(type='log')),
        tooltip=[
            alt.Tooltip('Measurement'),
            alt.Tooltip('Rsoln', format='.2s', title="|Z| (Ohm)")
        ],
        color=alt.Color('Temperature:Q').scale(scheme="turbo"),
        # optional jitter to spread points
        xOffset=alt.X('jitter:Q')
    ).transform_calculate(
        jitter="(random() - 0.5) * 0.2"
    )

    boxplot1 = (box1 + points1).properties(width=300)


    # Box + points for Kappa
    box2 = alt.Chart(synthesis).mark_boxplot(extent='min-max',opacity=0.5).encode(
        x=base_x,
        y=alt.Y('Kappa:Q',
                scale=alt.Scale(type='log'),
                axis=alt.Axis(title='Conductivity (S/cm)',format='.2s')),
    )

    points2 = alt.Chart(synthesis).mark_circle(size=40, opacity=0.6).encode(
        x=base_x,
        y=alt.Y('Kappa:Q', scale=alt.Scale(type='log')),
        tooltip=[
            alt.Tooltip('Measurement'),
            alt.Tooltip('Rsoln', format='.2s', title="|Z| (Ohm)")
        ],
        color=alt.Color('Temperature:Q').scale(scheme="turbo"),
        xOffset=alt.X('jitter:Q')
    ).transform_calculate(
        jitter="(random() - 0.5) * 0.1"
    )

    boxplot2 = (box2 + points2).properties(width=300)

    bchart = (points1+box1).properties(width=400)|(points2+box2).properties(width=400)
    bchart
    return


@app.cell
def _(mo):
    browser2 = mo.ui.file_browser(initial_path=r'C:\Users\oschn\Dropbox (MIT)\jaramillogroupshared\Data\Jaramillo lab\CryoEchem\Gamry Data',multiple=True,selection_mode='file',label='Select files...')
    return (browser2,)


@app.cell
def _(browser2):
    browser2
    return


@app.cell
def _(
    browser2,
    c1,
    file_browser_to_dataframe,
    parse_multi_EIS_alt,
    plot_dual_bode,
):
    ## now look just at BSA/pyridine
    maindf = file_browser_to_dataframe(browser2)
    _minphase = maindf.groupby('Measurement',as_index=False)["Zphz"].max()
    _good_measurements = _minphase[abs(_minphase['Zphz'])<10]
    subdf = maindf[maindf["Measurement"].isin(_good_measurements['Measurement'])]
    subdf['Date'] = subdf['Measurement'].str.extract(r"(202\d+)_")
    plot = plot_dual_bode(subdf,groupby='Measurement')
    pyrsyn = parse_multi_EIS_alt(maindf,liqvolstring=r'(\d+)uL')
    pyrsyn['Date'] = pyrsyn['Measurement'].str.extract(r"(202\d+)_")
    pyrsyn['Liquid Volume'] = 0.1
    pyrsyn['Total Volume'] = pyrsyn['Gas Volume']/620 + pyrsyn['Liquid Volume']
    pyrsyn['Gsoln'] = 1/pyrsyn['Rsoln']
    pyrsyn['CellConst'] = c1
    pyrsyn['Kappa'] = pyrsyn['CellConst']/pyrsyn['Rsoln']

    plot
    return


@app.cell
def _(alt, np, synthesis):
    pyrsyn2 = synthesis
    pyrsyn2['mmoles H2S'] = pyrsyn2['Gas Volume']*0.044
    pyrsyn2['Tinv'] = 1/pyrsyn2['Temperature']
    pyrsyn2['mmoles IL'] = np.where(pyrsyn2['Date'].str.contains('260512'),0.5,1)
    pyrsyn2['mmoles pyr'] = np.where(pyrsyn2['Date'].str.contains('260514'),1,0)
    pyrsyn2['Mole Fraction IL'] = pyrsyn2['mmoles IL']/(pyrsyn2['mmoles pyr']+pyrsyn2['mmoles IL']+pyrsyn2['mmoles H2S'])

    p1 = alt.Chart(pyrsyn2).mark_point(size=200,filled=True,stroke='black').encode(
        x=alt.X('Temperature:Q',scale=alt.Scale(domain=[150,205])),
        y=alt.Y('Kappa:Q',scale=alt.Scale(type='log'),axis=alt.Axis(title='Conductivity (S/cm)',format='.2s')),
        shape = alt.Shape('Solvent:N',scale=alt.Scale(domain=['IL+Sulfolane','IL+PC'],range=['circle','triangle','square','cross']), legend='Solvent'),
        tooltip = alt.Tooltip('Measurement'),
        color=alt.Color('Temperature:Q').scale(scheme="turbo")
    )
    p2 = alt.Chart(pyrsyn2).mark_point(size=200,filled=True,stroke='black').encode(
        x=alt.X('Mole Fraction IL:Q'),
        y=alt.Y('Kappa:Q',scale=alt.Scale(type='log'),axis=alt.Axis(title='Conductivity (S/cm)',format='.2s')),
        shape = alt.Shape('Solvent:N',scale=alt.Scale(domain=['IL+Sulfolane','IL+PC'],range=['circle','triangle','square','cross']), legend='Solvent'),
        tooltip = alt.Tooltip('Measurement'),
        color=alt.Color('Temperature:Q').scale(scheme="turbo")
    )

    pchart = p1|p2
    #checking for stronger dependence on temperature, volume, or date
    pchart.interactive().properties(title='IL+sulfolane',width=600)
    return


@app.cell
def _(plt, syndf):
    import seaborn as sns
    from matplotlib.ticker import ScalarFormatter
    from matplotlib.ticker import EngFormatter

    fmt = EngFormatter(places=1, sep="")  # e.g., 1.2k, 3.4M



    with plt.style.context("default"):
        sns.set_theme(style="whitegrid", context="talk")
        fig, axes = plt.subplots(1, 2, figsize=(16, 8), sharex=False)
        # Common boxplot style
        box_kws = dict(
            width=0.6,
            # fliersize=2,
            linewidth=1,
            palette="tab10"
        )
        # Plot 1
        sns.boxplot(data=syndf, x="Date", y="Gsoln", ax=axes[0], **box_kws)
        axes[0].set_yscale("log")
        axes[0].set_title("Gsoln")
        axes[0].set_xlabel("")
        axes[0].set_ylabel("Gsoln")

        # Plot 2
        sns.boxplot(data=syndf, x="Date", y="Gsoln/Vol", ax=axes[1], **box_kws)
        axes[1].set_yscale("log")
        axes[1].set_title("Gsoln/Vol")
        axes[1].set_xlabel("")
        axes[1].set_ylabel("Gsoln/Vol")

        # Ticks + grid formatting
        for ax in axes:
            ax.tick_params(axis="x", rotation=45)
            ax.yaxis.set_major_formatter(fmt)
            ax.grid(True, which="both", axis="y", alpha=0.3)


    fig
    return


@app.cell
def _(mo):
    browser3 = mo.ui.file_browser(initial_path=r'C:\Users\oschn\Dropbox (MIT)\jaramillogroupshared\Data\Jaramillo lab\CryoEchem',multiple=True,selection_mode='file',label='Going back for h2s only data')
    browser3
    return (browser3,)


@app.cell
def _(browser3, file_browser_to_dataframe, plot_dual_bode):
    h2snew = file_browser_to_dataframe(browser3)
    _minphase = h2snew.groupby('Measurement',as_index=False)["Zphz"].max()
    _good_measurements = _minphase[abs(_minphase['Zphz'])<10]
    dfnew = h2snew[h2snew["Measurement"].isin(_good_measurements['Measurement'])]
    dfnew['Date'] = dfnew['Measurement'].str.extract(r"(202\d+)_")
    dfnew['Vol'] = dfnew['Measurement'].str.extract(r"(\d+)cm3")
    plot_dual_bode(dfnew,groupby='Vol')
    return (dfnew,)


@app.cell
def _(alt, dfnew, parse_multi_EIS_alt, resistance_to_kappa):
    newh2sdata = parse_multi_EIS_alt(dfnew)
    newh2sdata['Date'] = newh2sdata['Measurement'].str.extract(r"(2026\d+)_")
    newh2sdata['Total Volume'] = newh2sdata['Gas Volume']/620
    newh2sdata['Gsoln'] = 1/newh2sdata['Rsoln']
    newh2sdata['Kappa'] = resistance_to_kappa(newh2sdata['Rsoln'],newh2sdata['Total Volume'])
    newh2sdata['InvT'] = 1/newh2sdata['Temperature']
    tregpoints = alt.Chart(newh2sdata).mark_circle(opacity=0.8,size=300,stroke='black').encode(
        x=alt.X('Temperature:Q', scale=alt.Scale(domain=[170,210])).title('Temperature (K)'),
        y=alt.Y('Kappa:Q',scale=alt.Scale(type='linear'), axis=alt.Axis(format=".2s")).title('Conductivity (S/cm)'),
        color=alt.Color('Pressure:Q',scale=alt.Scale(scheme='viridis')),
        size = alt.Size('Gas Volume:Q', legend=alt.Legend(title="Gas Volume (cm3)")),
        # color=alt.Color('Mole Frac Pyridine:Q').scale(range=['slategray','navy']),
        tooltip=['Measurement']
    ).properties(title='H2S Only')
    rregpoints = alt.Chart(newh2sdata).mark_circle(opacity=0.8,size=300,stroke='black').encode(
        x=alt.X('InvT:Q', scale=alt.Scale(domain=[0.0045,0.006])).title('1/Temperature (K^-1)'),
        y=alt.Y('Kappa:Q',scale=alt.Scale(type='log'), axis=alt.Axis(format=".2s")).title('Conductivity (S/cm)'),
        color=alt.Color('Pressure:Q',scale=alt.Scale(scheme='viridis')),
        size = alt.Size('Gas Volume:Q', legend=alt.Legend(title="Gas Volume (cm3)")),
        shape=alt.condition(
            alt.FieldOneOfPredicate('Date', ['20260127', '20260211']),
            alt.Shape('Date:N').scale(domain=['20260127', '20260211'], range=['circle', 'square']),
            alt.value('triangle')
        ),
        # color=alt.Color('Mole Frac Pyridine:Q').scale(range=['slategray','navy']),
        tooltip=['Measurement']
    ).properties(title='H2S Only')


    (tregpoints).configure_axis(
        labelFontSize=14,   # Tick numbers
        titleFontSize=16,   # Axis titles
        grid=True           # Keep gridlines for readability
    ).configure_title(
        fontSize=18         # Chart titles
    ).configure_legend(
        labelFontSize=12,
        titleFontSize=14
    ).properties(width=300,height=300).interactive()

    tregpoints|rregpoints
    return


@app.cell
def _(dfnew, np, parse_multi_EIS_alt, resistance_to_kappa):
    pyrdf = parse_multi_EIS_alt(dfnew)
    pyrdf['Date'] = pyrdf['Measurement'].str.extract(r"(2026\d+)_")
    pyrdf['Liquid Volume'] = np.where(pyrdf['Date']=='20260127',0.5,0.1)
    pyrdf['Total Volume'] = round(pyrdf['Gas Volume']/620,ndigits=3)+pyrdf['Liquid Volume']
    moles_pyr = pyrdf['Liquid Volume']*0.98/79
    moles_h2s = pyrdf['Gas Volume']/620*0.92/34
    pyrdf['Mole Frac Pyridine'] = round(moles_pyr/(moles_pyr+moles_h2s),ndigits=3)
    pyrdf['Kappa'] = resistance_to_kappa(pyrdf['Rsoln'],pyrdf['Total Volume'])
    pyrdf['Lambda'] = pyrdf['Kappa']/(moles_pyr/pyrdf['Total Volume'])
    return (pyrdf,)


@app.cell
def _(alt, pyrdf):

    rpts = alt.Chart(pyrdf).mark_point(size=99).encode(
        x=alt.X('Mole Frac Pyridine:Q'),
        y=alt.Y('Kappa:Q',scale=alt.Scale(type='log'),axis=alt.Axis(format=".2s")),
        size = 'Total Volume:Q',
        color=alt.Color('Temperature:Q').scale(scheme="turbo")
    ).properties(title='Soln. Conductivity (S/cm)',width=400)

    rhopts = alt.Chart(pyrdf).mark_point(size=99).encode(
        x=alt.X('Temperature:Q',scale=alt.Scale(domain=[140,220])),
        y=alt.Y('Kappa:Q', scale=alt.Scale(type='log'),axis=alt.Axis(format=".2s")),
        size = 'Total Volume:Q',
        color=alt.Color('Temperature:Q').scale(scheme="turbo")
    ).properties(title='Soln. Conductivity (S/cm )',width=400)

    (rpts|rhopts).interactive()
    return


@app.cell
def _(alt, pyrdf):


    # 1. Do the calculation BEFORE creating the chart
    # (Assuming 'moles_pyr' and 'Total Volume' are defined in your scope)
    # synthesis['Lambda'] = synthesis['Kappa'] / (moles_pyr / synthesis['Total Volume'])

    # 2. Define a common "Base" to avoid repeating code
    # We use mark_circle (filled) with a black outline to make them "bold"
    base = alt.Chart(pyrdf).mark_circle(
        opacity=0.8,       # Slight transparency helps if points overlap
        stroke='black',    # Adds a black border to make points "bold"
        strokeWidth=1
    ).encode(
        y=alt.Y(
            'Kappa:Q', 
            scale=alt.Scale(type='log'), 
            axis=alt.Axis(format=".2e", titlePadding=10), # .2e (scientific) usually fits log scales better
            title='Solution Conductivity (S/cm)'
        ),
        color=alt.Color(
            'Temperature:Q', 
            scale=alt.Scale(scheme="turbo"), 
            legend=alt.Legend(title="Temp (K)")
        ),
        # Make the points vary in size, but ensure the SMALLEST point is still big (range 100-500)
        size=alt.Size(
            'Total Volume:Q', 
            # scale=alt.Scale(range=[0.5, 2]),
            legend=alt.Legend(title="Volume (mL)")
        )
    )

    # 3. Create the two subplots
    rpts2 = base.encode(
        x=alt.X('Mole Frac Pyridine:Q', title='Mole Fraction Pyridine')
    ).properties(
        title='Conductivity vs Composition',
        width=400,
        height=400
    )

    rhopts2 = base.encode(
        x=alt.X(
            'Temperature:Q', 
            scale=alt.Scale(domain=[140, 220], zero=False), # zero=False zooms in on the data
            title='Temperature (K)'
        )
    ).properties(
        title='Conductivity vs Temperature',
        width=400,
        height=400
    )

    # 4. Combine and Configure Fonts for Readability
    chart = (rpts2 | rhopts2).configure_axis(
        labelFontSize=14,   # Tick numbers
        titleFontSize=16,   # Axis titles
        grid=True           # Keep gridlines for readability
    ).configure_title(
        fontSize=18         # Chart titles
    ).configure_legend(
        labelFontSize=12,
        titleFontSize=14
    )

    chart.interactive()
    return


@app.cell
def _(alt, h2sdatatrimmed, np):
    h2sdatatrimmed['invT'] = 1000/h2sdatatrimmed['Temperature']
    h2sdatatrimmed['logKappa'] = np.log(h2sdatatrimmed['Kappa'])
    # synthesis['gasmL'] = synthesis['Gas Volume']
    # synsmall = synthesis[synthesis['Mole Frac Pyridine']>0.1]
    points = alt.Chart(h2sdatatrimmed).mark_point(size=70).encode(
        x=alt.X('invT',title='1000/T'),
        y=alt.Y('logKappa',title='log(kappa)'),
        # color='Mole Frac Pyridine:N',
        tooltip = ['Temperature','Rsoln','Measurement']
    )
    line = points.transform_regression(
        'invT','logKappa', method = 'linear' , groupby = ['Mole Frac Pyridine']
    ).mark_line()
        # strokeDash=[5,5]).encode(color=alt.value('black'))
    arrheniuschart = (points + line ).properties(
        title='Arrhenius Plot',
        width=400,
        height=400
    ).interactive()

    arrheniuschart.configure_axis(
        labelFontSize=14,   # Tick numbers
        titleFontSize=16,   # Axis titles
        grid=True           # Keep gridlines for readability
    ).configure_title(
        fontSize=18         # Chart titles
    ).configure_legend(
        labelFontSize=12,
        titleFontSize=14
    )
    return


@app.cell
def _(getslope, h2sdatatrimmed, slope_to_Ea):
    m = getslope(h2sdatatrimmed)
    energy = slope_to_Ea(m)
    energy
    return


@app.cell
def _():
    from scipy import stats
    # 2. Calculate Slope & Ea (Physics Part)
    def getslope(df):
        slope, intercept, r_value, _, _ = stats.linregress(df['invT'],df['logKappa'])
        return slope
    # slopelist = synthesis.groupby('Mole Frac Pyridine').apply(getslope)

    # for slope in slopelist:
    #     # Ea = -Slope * R * 1000 (The 1000 is because x-axis is 1000/T)
    #     R_gas = 8.314 # J/mol*K
    #     Ea_kJ = (-slope * R_gas * 1000) / 1000 

    #     # Create a label string for the plot
    #     label_text = f"Ea = {Ea_kJ:.2f} kJ/mol "
    #     print(label_text) # Check it in console

    def slope_to_Ea(slope):
        """Take float slope from fit of 1000/T, ln(kappa) and returns activation energy"""
        R_gas = 8.314 # J/mol*K
        Ea_kJ = (-slope * R_gas * 1000) / 1000 
        return Ea_kJ

    return getslope, slope_to_Ea


@app.cell
def _():
    return


@app.cell
def _():
    # newdata = file_browser_to_dataframe(browser1)
    # olddf = EIS_csv_to_df_alt(browser2.value[0].path)
    # synthesis1 = parse_multi_EIS_alt(newdata,liqvolstring=r'(\d+)uL')
    # synthesis1['Liquid Volume'] = synthesis1['Liquid Volume']/1000
    # synthesis2 = parse_multi_EIS_alt(olddf,liqvolstring=r'(\d+(?:p\d+)?)mL')
    # synthesis2['Liquid Volume'] = synthesis2['Liquid Volume']
    # synthesis = pd.concat([synthesis1,synthesis2])

    # synthesis['Total Volume'] = synthesis['Liquid Volume']+synthesis['Gas Volume']/620
    # synthesis['Rsoln/Vol'] = synthesis['Rsoln']/synthesis['Total Volume']
    # synthesis['Kappa'] = resistance_to_kappa(synthesis['Rsoln'],synthesis['Total Volume'])
    # moles_pyr = synthesis['Liquid Volume']*0.98/79
    # moles_h2s = synthesis['Gas Volume']/620*0.92/34
    # synthesis['Mole Frac Pyridine'] = round(moles_pyr/(moles_pyr+moles_h2s),ndigits=3)
    # synthesis
    return


if __name__ == "__main__":
    app.run()
