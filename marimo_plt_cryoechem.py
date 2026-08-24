import marimo

__generated_with = "0.23.15"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import matplotlib.pyplot as plt
    import pandas as pd
    from datetime import datetime as dt
    import numpy as np

    return dt, mo, np, pd, plt


@app.cell
def _(mo):
    fileinput = mo.ui.text(placeholder="Paste file path here",full_width=True)
    fileinput
    return (fileinput,)


@app.cell
def _(mo):
    browser = mo.ui.file_browser(filetypes=['.csv'],multiple=False)
    browser
    return (browser,)


@app.cell
def _(browser, fileinput, mo, pd):
    # filepath = fileinput.value
    if not browser.value:
        filepath = fileinput.value
    else:
        filepath = browser.value[0].id
    # filepath = r'C:\Users\oschn\Dropbox (MIT)\jaramillogroupshared\Data\Jaramillo lab\CryoEchem\raw_logs\CryoTest_20251211-090846.csv'
    df = pd.read_csv(filepath)
    # how I got date previously: time = pd.to_datetime(df['DateTime'], format="%Y%m%d-%H%M%S")
    time = pd.to_datetime(df['DateTime'])
    unix_time = time.astype('int64')//1e9
    xrange = mo.ui.range_slider(start=unix_time[0],stop=unix_time.iloc[-1],step=30,label='Time Range',full_width=True)
    return df, time, xrange


@app.cell
def _(mo):
    tgms_input = mo.ui.text(placeholder = "Paste TGMS filepath here, if applicable", full_width=True)
    tgms_input
    return (tgms_input,)


@app.cell
def _(mo):
    tgms_browser = mo.ui.file_browser(label='Select TGMS files, if applicable',multiple=False)
    tgms_browser
    return (tgms_browser,)


@app.cell
def _(mo):
    tgms_date = mo.ui.text(placeholder = "YYYY-MM-DD",max_length=10)
    tgms_date
    return (tgms_date,)


@app.cell
def _(pd, tgms_browser, tgms_date, tgms_input):
    if not tgms_browser.value and tgms_input.value == '':
        tgms_df = None
    else:
        if not tgms_browser.value:
            tgms_df = pd.read_csv(tgms_input.value)
        else:
            tgms_df = pd.read_csv(tgms_browser.value[0].id)
        date = tgms_date.value
        if 'time' in tgms_df.columns:
            tgms_time = pd.to_datetime(date+' '+tgms_df['time'],format='%Y-%m-%d %H:%M')
        elif 'Time' in tgms_df.columns:
            tgms_time = pd.to_datetime(date+' '+tgms_df['Time'],format='%Y-%m-%d %H:%M')
    return tgms_df, tgms_time


@app.cell
def _():
    # ## for manual TGMS data, need to make sure date and time align
    # if tgms_input.value != '':
    #     tgms_df = pd.read_csv(tgms_input.value)
    #     date = tgms_date.value
    #     if 'time' in tgms_df.columns:
    #         tgms_time = pd.to_datetime(date+' '+tgms_df['time'],format='%Y-%m-%d %H:%M')
    #     elif 'Time' in tgms_df.columns:
    #         tgms_time = pd.to_datetime(date+' '+tgms_df['Time'],format='%Y-%m-%d %H:%M')
    #     # tgms_df.columns[1]
    # else:
    #     tgms_df = None
    return


@app.cell
def _(np):
    A_h2s = 4.43681
    B_h2s = 829.439
    C_h2s = -25.412

    A_co = 3.81912
    B_co = 291.743
    C_co = -5.151

    A_o2 = 3.85845
    B_o2 = 325.675
    C_o2 = -5.667


    def Antoine(A,B,C,T):
        ## takes temperature in kelvin, returns pressure in Torr
        log10P = A - B/(T+C)
        Pbar = 10**log10P
        Ptorr = 750*Pbar
        return Ptorr

    templist = np.linspace(50,250)
    psat_co = Antoine(A_co, B_co, C_co, templist)
    psat_o2 = Antoine(A_o2,B_o2,C_o2,templist)
    psat_h2s = Antoine(A_h2s, B_h2s, C_h2s, templist)
    return psat_h2s, psat_o2, templist


@app.cell
def _(df, dt, pd, plt, tgms_df, tgms_time, time, xrange):
    if tgms_df is not None:
        fig,(ax1,ax2,ax4,ax5) = plt.subplots(4,1,sharex=True)
    else:
        fig,(ax1,ax2,ax4) = plt.subplots(3,1,sharex=True)

    F1 = df['H2S sccm']
    F2 = df['Ar sccm']
    P1 = df['Reaction Pressure']
    P2 = df['Cryo Pressure']
    Tcryo = df['Cryo Temperature']
    Trxn  = df['Reaction Temperature']

    # === PLOTS ===
    ax1.plot(time, F1, marker='.', color='darkblue', label='H2S sccm')
    ax1.plot(time, F2, marker='.', color='lightblue', label='Ar sccm')

    rxnP = ax2.plot(time, P1, color='tab:orange', label='Rxn')
    ax3 = ax2.twinx()
    vacP = ax3.plot(time, P2, color='tab:orange', linestyle='dashed', label='Cryo')

    ax4.plot(time, Tcryo, color='red', label='Cryo Setpoint')
    ax4.plot(time, Trxn, color='pink', label='Reaction Temp')

    if tgms_df is not None:
        tgms_values = tgms_df.iloc[:,-1]
        ax5.plot(tgms_time, tgms_values,marker='.',color='darkgreen',label=tgms_df.columns[1])
        ax5.grid(visible=True)
        ax5.legend()

    # === FORMATTING ===
    ax1.set_ylabel('Flow (sccm)')
    ax2.set_ylabel('Pressure (Torr)')
    # ax3.set_ylabel('Cryo Pressure (Torr)')
    ax4.set_ylabel('Temperature (K)')
    ax1.legend()
    pressureplots = rxnP + vacP
    pressurelabels = [l.get_label() for l in pressureplots]
    ax2.legend(pressureplots,pressurelabels)
    ax4.legend()

    ax1.grid(visible=True)
    ax2.grid(visible=True)
    ax4.grid(visible=True)

    ## === AUTOSCALING ===
    timestart = dt.utcfromtimestamp(xrange.value[0])
    # timestart = pd.Timestamp(xrange.value[0])
    timestop = dt.utcfromtimestamp(xrange.value[1])
    mask = (time >= timestart) & (time <= timestop)


    # Per-axis autoscale
    if mask.any():
        ax1.set_xlim(timestart,timestop)

        # Ax1 autoscale
        yvals = pd.concat([F1[mask], F2[mask]])
        ax1.set_ylim(-0.1, yvals.max()*1.1)

        # Ax2 + Ax3 (twin axes)
        ax2.set_ylim(P1[mask].min()*0.9, P1[mask].max()*1.1)
        ax3.set_ylim(P2[mask].min()*0.9, P2[mask].max()*1.1)

        # Ax4
        yvals4 = pd.concat([Tcryo[mask], Trxn[mask]])
        ax4.set_ylim(yvals4.min()*0.9, yvals4.max()*1.1)

        if tgms_df is not None:
            ax5.set_ylim(tgms_values[mask].min()*0.9,tgms_values[mask].max()*1.1)
    return P1, Tcryo, fig, mask, timestart, timestop


@app.cell
def _(fig):
    fig
    return


@app.cell
def _(xrange):
    xrange
    return


@app.cell
def _(
    P1,
    Tcryo,
    df,
    mask,
    np,
    plt,
    psat_h2s,
    psat_o2,
    templist,
    time,
    timestart,
    timestop,
):
    fig2,(dTax,dPax,dPTax) = plt.subplots(3,1,sharex=True)
    fig3,PTax = plt.subplots(1,1)

    # dTdt = df['Cryo Temperature'].diff()/unix_time.diff()
    dTdt = np.gradient(df['Cryo Temperature'],0.5)
    dPdt = np.gradient(P1, 0.5)
    # dPdT = np.gradient(df['Reaction Pressure'])/np.gradient(df['Cryo Temperature'].diff())
    dPdT = P1/df['Cryo Temperature']

    dTax.plot(time,dTdt,label='dTdt',color='red')
    dPax.plot(time,dPdt,label='dPdt',color='tab:orange')
    dPTax.plot(time,dPdT,label='dPdT')
    # PTax.scatter(Tcryo,P1, label='Reaction Pressure',color='lightblue')

    PTax.plot(templist-20,psat_h2s,color='goldenrod',label='Psat H2S')
    PTax.plot(templist-20,psat_o2,color='purple',label='Psat O2')


    # Per-axis autoscale
    if mask.any():
        dTax.set_xlim(timestart,timestop)
        dPax.set_xlim(timestart,timestop)

        dTax.set_ylim(dTdt[mask].min()*0.9, dTdt[mask].max()*1.1)
        dPax.set_ylim(dPdt[mask].min()*0.9, dPdt[mask].max()*1.1)
        # dPTax.set_ylim(dPdT[mask].min()*0.9, dPdT[mask].max()*1.1)

        # Set data not just limits based on mask
        PTax.scatter(Tcryo[mask],P1[mask],label='Reaction Pressure',color='lightblue',marker='.')
        PTax.set_ylim(P1[mask].min()*0.9,P1[mask].max()*1.1)
        PTax.set_xlim(Tcryo[mask].min()*0.9,Tcryo[mask].max()*1.1)
    else:
        PTax.scatter(Tcryo,P1,color='lightblue',marker='.')

    dTax.grid(visible=True)
    dPax.grid(visible=True)
    PTax.grid(visible=True)

    PTax.set_xlabel('Cryo Temperature (K)')
    PTax.set_ylabel('Reaction Pressure (Torr)')

    dTax.set_ylabel('dTdt (K/min)')
    dPax.set_ylabel('dPdt (Torr/min)')
    return (fig3,)


@app.cell
def _(fig3):
    fig3.legend()
    return


@app.cell
def _(mo):
    filename_input = mo.ui.text(value=r'C:\Users\oschn\Dropbox (MIT)\jaramillogroupshared\Data\Jaramillo lab\CryoEchem\plot.png',label="Put export filename here",full_width=True)
    save_button = mo.ui.run_button(label='Save PNG')
    mo.vstack([filename_input,save_button])
    return filename_input, save_button


@app.cell
def _(fig, filename_input, mo, save_button):
    mo.stop(not save_button.value, mo.md("Click save PNG to export"))

    fig.savefig(filename_input.value,dpi=300,bbox_inches='tight')
    mo.md(f"Saved as {filename_input.value}")
    return


if __name__ == "__main__":
    app.run()
