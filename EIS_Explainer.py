import marimo

__generated_with = "0.19.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import numpy as np
    import plotly.express as px
    import plotly.graph_objects as go
    import altair as alt
    import pandas as pd
    return alt, go, mo, np, pd


@app.cell
def _(mo):
    mo.md(r"""
    **(Electrochemical) Impedance Spectroscopy**

    Basic idea (applies to non-chemical systems as well): apply ac signal, measure electrical response.

    Applied voltage called potentiostatic, applied current called galvanostatic.
    """)
    return


@app.cell
def _(mo, np):
    phase = mo.ui.slider(start=0,stop=2*np.pi,step=np.pi/10,value=0,label='Phase')
    minifreq = mo.ui.slider(0.1,100,value=10,label='Frequency')
    amp = mo.ui.slider(0.1,10,value=2,label='Amplitude')
    freq = mo.ui.slider(steps=np.logspace(start=-2,stop=6,num=100),value=0.01,label='Frequency (Hz)')
    return amp, freq, minifreq, phase


@app.cell
def _(amp, minifreq, mo, phase):
    mo.hstack([phase, minifreq, amp], justify="start",gap=2)
    return


@app.cell
def _(amp, go, minifreq, np, phase):
    t = np.linspace(0, 10,num=1000)
    # timefig = px.line(x=t, y=np.sin(freq.value*t), labels={'x':'t'},title='Simple Sine')
    # timefig.add_scatter(x=t,y=amp.value*np.sin(freq.value*t+phase.value))

    simple_sine = go.Figure()
    simple_sine.add_trace(go.Scatter(x=t,y=np.sin(minifreq.value*t),mode='lines',name='Test Signal'))
    simple_sine.add_trace(go.Scatter(x=t,y=amp.value*np.sin(minifreq.value*t+phase.value),mode='lines',name='Response Signal'))

    simple_sine.update_layout(
        xaxis=dict(title='time'),
        yaxis = dict(range=[-5,5]),
        template='plotly_white'
    )

    simple_sine
    return


@app.cell
def _(mo):
    mo.md(r"""
    **Complex Impedance**

    Z = R for resistor, Z = $\frac{1}{j\omega C}$ for capacitor, Z = $j\omega L$ for inductor.

    **Bode Plots**

    1. Plot |Z| (real part of impedance) vs frequency. Pure resistor gives horizontal line, pure capacitor gives a line (vs log(f)) with slope -1/C

    2. Plot phase angle vs frequency. Pure resistor has phase of 0$^{\circ}$ and pure capacitor has phase of 90$^{\circ}$.
    """)
    return


@app.cell
def _(np):
    def cap_impedance(f,C):
        Z = 1/(f*C)
        return Z
    def randles_impedance(f,C,Rs,Rp):
        # simple randles circuit has double layer capacitance in parallel with charge transfer resistance, both in series with solution resistance (sometimes called uncompensated resistance)
        Zp = 1/(1/cap_impedance(f,C) + 1/Rp)
        return Zp + Rs
    def randles_impedance_stray_capacitance(f,C,Rs,Rp,Cstray):
        zrandles = randles_impedance(f,C,Rs,Rp)
        ztotal= 1/(1/zrandles+1/cap_impedance(f,Cstray))
        return ztotal

    def randles_cstray(f,C,Rs,Rp,Cstray):
        omega = 2*np.pi*f
        randles = randles_Z(f,C,Rs,Rp)
        Zstray = 1/(1j*omega*Cstray)
        Zcombined = 1/(1/Zstray+1/randles)
        return Zcombined

    def randles_Z(f,C,Rs,Rp):
        omega = 2*np.pi*f
        Z_parallel = Rp / (1 + 1j * omega * Rp * C)
        Z_total = Rs + Z_parallel
        return Z_total
    return randles_Z, randles_cstray


@app.cell
def _(mo):
    cap = mo.ui.slider(1e-6,10,value=0.1,label='$C_{dl}$') # minimum is 1e-6, but want 1e-12
    rsoln = mo.ui.slider(10,1e5,value=100,label='$R_{Soln}$')
    rct = mo.ui.slider(100,1e6,value=1e3,label='$R_{ct}$')
    cstray = mo.ui.slider(1,100,value=1,label='$C_{stray}$') # minimum is 1e-6, want 1e-12ish
    return cap, cstray, rct, rsoln


@app.cell
def _(cap, np, randles_Z, rct, rsoln):
    freqrange = np.logspace(-1,6)
    # magz = randles_impedance_stray_capacitance(freqrange,cap.value*1e-6,rsoln.value,rct.value,cstray.value*1e-13)
    complexZ = randles_Z(freqrange,cap.value*1e-6,rsoln.value,rct.value)
    magz = np.real(complexZ)
    phsz = np.angle(complexZ,deg=True)
    # phsz = (90/np.pi)*np.arctan2(np.real(complexZ),np.imag(complexZ))
    return freqrange, magz, phsz


@app.cell
def _(freqrange, go, magz, phsz):
    from plotly.subplots import make_subplots

    # Create a figure with two subplots (stacked vertically)
    bode1 = make_subplots(rows=1,cols=2)

    # 1. Magnitude Plot (Log-Log)
    bode1.add_trace(go.Scatter(x=freqrange, y=magz, mode='lines+markers', name='|Z|'), row=1, col=1)

    # 2. Phase Plot (Semi-Log: Log Freq, Linear Phase)
    bode1.add_trace(go.Scatter(x=freqrange,y=phsz, mode='lines+markers', name='Phase'), row=1, col=2)

    bode1.update_layout(template='plotly_white',    hovermode="x unified", margin=dict(l=60, r=20, t=50, b=50))
    # --- AXIS STYLING ---
    # Global X-Axis settings (Log scale, Grid, Spikelines)
    bode1.update_xaxes(
        type="log",
        showgrid=True,
        gridwidth=1,
        gridcolor='LightGrey',
        minor=dict(showgrid=True, gridcolor='#F0F0F0'), # Crucial for Log plots
        showspikes=True, # Crosshairs
        spikethickness=1,
        spikedash='dot',
        spikecolor='gray',
        spikemode='across'
    )

    # Specific X-Axis Label (only on bottom plot)
    bode1.update_xaxes(title_text="<b>Frequency (Hz)</b>")

    # Y-Axis 1: Magnitude (Log Scale)
    bode1.update_yaxes(
        title_text="<b>|Z| (Ω)</b>",
        type="log",
        row=1, col=1,
        showgrid=True,
        gridcolor='LightGrey',
        minor=dict(showgrid=True, gridcolor='#F0F0F0'),
        showspikes=True,
        spikecolor='gray'
    )

    # Y-Axis 2: Phase (Linear Scale)
    bode1.update_yaxes(
        title_text="<b>Phase (°)</b>",
        row=1, col=2,
        showgrid=True,
        gridcolor='LightGrey',
        zeroline=True,
        zerolinecolor='Black', # Highlight the 0 degree line
        zerolinewidth=1,
        showspikes=True,
        spikecolor='gray'
    )
    return


@app.cell
def _(cap, mo, rct, rsoln):
    mo.hstack([cap,rsoln,rct],justify='start',gap=2)
    return


@app.cell
def _(mo):
    mo.md(r"""
    A typical electrochemical cell has a solution resistance, then a resistance and capacitance in parallel representing the electrolyte-electrode interface (called charge-transfer resistance and double-layer capacitance).

    In a high-impedance system, the capacitive coupling to the environment (stray capacitance) becomes important.
    """)
    return


@app.cell
def _(cstray):
    cstray
    return


@app.cell
def _(alt, cap, cstray, freq, freqrange, np, pd, randles_cstray, rct, rsoln):
    zcomplex = randles_cstray(freqrange,cap.value*1e-6,rsoln.value,rct.value,cstray.value*1e-13)
    bode2df = pd.DataFrame({'Frequency':freqrange,'Magnitude':np.real(zcomplex),'Phase':np.angle(zcomplex,deg=True)})

    # Define the dashed line
    line_df = pd.DataFrame({'Frequency': [freq.value]})
    vline = alt.Chart(line_df).mark_rule(color='red', strokeDash=[5, 5]).encode(
        x='Frequency'
    )

    # Base chart (defines the data source and the X axis)
    bode2 = alt.Chart(bode2df).encode(
        x=alt.X('Frequency', scale=alt.Scale(type='log'), title='Frequency (Hz)')
    )
    # 4. Calculate Dynamic Limits for the Log Plot
    ydomain = [bode2df['Magnitude'].min()*0.99 , bode2df['Magnitude'].max()*1.01 ]
    # Magnitude Chart (Log-Log)
    mag_plot = bode2.mark_line(point=True).encode(
        y=alt.Y('Magnitude', scale=alt.Scale(type='log',domain=ydomain), title='|Z| (Ohms)'),
        tooltip=['Frequency', 'Magnitude']
    ).properties(height=250, width=400, title="Magnitude")

    # Phase Chart (Log-Linear)
    phase_plot = bode2.mark_line(point=True).encode(
        y=alt.Y('Phase', scale=alt.Scale(type='linear'), title='Phase (Deg)'),
        tooltip=['Frequency', 'Phase']
    ).properties(height=250, width=400, title="Phase")

    # Combine vertically
    bode2 = (mag_plot+vline) | (phase_plot+vline)
    #bode2 = mag_plot | phase_plot

    # Display
    bode2
    return


@app.cell
def _(mo):
    mo.md(r"""
    Just for fun, we can look at the oscilloscope view at different frequency values:
    """)
    return


@app.cell
def _(freq):
    freq
    return


@app.cell
def _(cap, cstray, freq, np, pd, randles_cstray, rct, rsoln):
    time = np.linspace(0,10/freq.value,num=1000)

    # Extract real and imaginary parts
    # Zt = randles_Z(freq.value,cap.value*1e-6,rsoln.value,rct.value)
    Zt = randles_cstray(freq.value,cap.value*1e-6,rsoln.value,rct.value,cstray.value*1e-13)
    Z_real = np.real(Zt)
    Z_imag = np.imag(Zt)
    Zph = 2*np.angle(Zt) ## factor of 2 makes it look right, not sure why though
    df2 = pd.DataFrame({
        'time': time,
        'applied voltage': 0.05*np.sin(2*np.pi*freq.value*time), # assume 50 mV
        # 'current response': np.sin(freq.value*t + phase.value)
        'current response':(0.05/Z_real)*np.sin(2*np.pi*freq.value*time+Zph)
    })

    # Reshape to long format 
    df2_long = df2.melt(id_vars='time', var_name='Signal', value_name='amplitude')
    return (df2,)


@app.cell
def _(alt, df2):
    time_domain = alt.Chart(df2).encode(x=alt.X('time:Q',title='Time (s)'),y=alt.Y('applied voltage:Q').axis(title='Applied Voltage (V)',titleColor='#0a69a1')).mark_line(color='#0a69a1')
    meas = time_domain.encode(y=alt.Y('current response:Q').axis(title='Measured Current (A)',titleColor='#e28743')).mark_line(color='#e28743')
    (time_domain + meas).resolve_scale(y='independent')
    return


@app.cell
def _():


    return


@app.cell
def _(alt):
    # example plot for reference
    from altair.datasets import data

    source = data.seattle_weather()

    base = alt.Chart(source).encode(
        alt.X('month(date):T').title(None)
    )

    # area = base.mark_area(opacity=0.3, color='#57A44C').encode(
    #     alt.Y('average(temp_max)').axis(title='Avg. Temperature (°C)', titleColor='#57A44C') ,alt.Y2('average(temp_min)')
    # )
    other_line = base.mark_line().encode(alt.Y('average(temp_max)').axis(title='avg temp max'))

    line = base.mark_line(color='orange').encode(
        alt.Y('average(precipitation)').axis(title='Precipitation (inches)', titleColor='orange')
    )

    # alt.layer(line,other_line).resolve_scale(
    #     y='independent'
    # )
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
