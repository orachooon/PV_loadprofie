import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import io
import pvlib
from pvlib import iotools
from pvlib.location import Location
from pvlib.pvsystem import PVSystem
from pvlib.modelchain import ModelChain
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS

# ─────────────────────────────────────────
# Page Config
# ─────────────────────────────────────────
st.set_page_config(
    page_title="PV Load Profile Generator",
    page_icon="🌞",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.main-header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    padding: 2rem 2.5rem;
    border-radius: 16px;
    margin-bottom: 2rem;
    color: white;
}
.main-header h1 { font-size: 2rem; font-weight: 700; margin: 0; }
.main-header p  { font-size: 1rem; opacity: 0.75; margin: 0.4rem 0 0; }

.metric-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 1.2rem 1.5rem;
    border-radius: 12px;
    color: white;
    text-align: center;
}
.metric-card .val { font-size: 1.8rem; font-weight: 700; }
.metric-card .lbl { font-size: 0.82rem; opacity: 0.85; }

.info-box {
    background: #e8f4fd;
    border-left: 4px solid #3498db;
    padding: 1rem 1.2rem;
    border-radius: 8px;
    margin: 1rem 0;
}

/* ── Styled Tabs ── */
[data-testid="stTabs"] [role="tablist"] {
    gap: 8px;
    border-bottom: 2px solid #2d2d2d;
    padding-bottom: 4px;
}
[data-testid="stTabs"] button[role="tab"] {
    font-size: 1rem !important;
    font-weight: 600 !important;
    padding: 10px 22px !important;
    border-radius: 10px 10px 0 0 !important;
    border: none !important;
    background: #1e1e2e !important;
    color: #94a3b8 !important;
    transition: all 0.2s ease;
}
[data-testid="stTabs"] button[role="tab"]:nth-child(1) { border-top: 3px solid #3b82f6 !important; }
[data-testid="stTabs"] button[role="tab"]:nth-child(2) { border-top: 3px solid #f59e0b !important; }
[data-testid="stTabs"] button[role="tab"]:nth-child(3) { border-top: 3px solid #10b981 !important; }
[data-testid="stTabs"] button[role="tab"]:nth-child(4) { border-top: 3px solid #f43f5e !important; }
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: white !important;
    background: #2d2d3f !important;
}
[data-testid="stTabs"] button[role="tab"]:hover {
    background: #2d2d3f !important;
    color: white !important;
}

.econ-card {
    background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
    border: 1px solid #334155;
    border-radius: 14px;
    padding: 1.4rem 1.6rem;
    color: white;
    text-align: center;
    margin-bottom: 0.5rem;
}
.econ-card .val { font-size: 2rem; font-weight: 700; margin: 0.3rem 0; }
.econ-card .lbl { font-size: 0.8rem; opacity: 0.75; text-transform: uppercase; letter-spacing: 0.05em; }
.econ-card .sub { font-size: 0.85rem; opacity: 0.6; margin-top: 0.2rem; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# Header
# ─────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🌞 PV Load Profile Generator</h1>
    <p>สร้างข้อมูลการใช้ไฟฟ้าและการผลิตโซลาร์เซลล์ 8,760 ชั่วโมง พร้อม Export CSV</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# Core Functions (ported from main.py)
# ─────────────────────────────────────────
def interpolate_to_hourly(df_raw):
    df_raw = df_raw.sort_values('Time').reset_index(drop=True)
    t_start = pd.Timestamp('2000-01-01 00:00')
    t_end   = pd.Timestamp('2000-01-01 23:59')
    if df_raw['Time'].min() > t_start:
        val = df_raw.loc[df_raw['Time'].idxmin(), 'Load_kW']
        df_raw = pd.concat([pd.DataFrame({'Time': [t_start], 'Load_kW': [val]}), df_raw], ignore_index=True)
    if df_raw['Time'].max() < t_end:
        val = df_raw.loc[df_raw['Time'].idxmax(), 'Load_kW']
        df_raw = pd.concat([df_raw, pd.DataFrame({'Time': [t_end], 'Load_kW': [val]})], ignore_index=True)
    df_raw = df_raw.set_index('Time')
    hourly_index = pd.date_range(start='2000-01-01 00:00', end='2000-01-01 23:00', freq='1H')
    combined_index = df_raw.index.union(hourly_index).sort_values()
    df_interp = df_raw.reindex(combined_index).interpolate(method='time')
    df_hourly = df_interp.loc[hourly_index].copy()
    df_hourly.index = df_hourly.index.time
    return df_hourly['Load_kW']


def build_yearly_profile(hourly_weekday, hourly_weekend, monthly_targets):
    yearly_index = pd.date_range(start='2023-01-01 00:00', end='2023-12-31 23:00', freq='1H')
    df_year = pd.DataFrame(index=yearly_index)
    df_year['is_weekend'] = df_year.index.dayofweek >= 5
    df_year['time_only']  = df_year.index.time
    df_year['Raw_Load_kW'] = np.where(
        df_year['is_weekend'],
        df_year['time_only'].map(hourly_weekend),
        df_year['time_only'].map(hourly_weekday)
    )
    df_year['Month'] = df_year.index.month
    monthly_raw_sum = df_year.groupby('Month')['Raw_Load_kW'].sum()
    df_year['Target_Total']    = df_year['Month'].map(monthly_targets)
    df_year['Scaling_Factor']  = df_year['Target_Total'] / df_year['Month'].map(monthly_raw_sum)
    df_year['Adjusted_Load_kWh'] = df_year['Raw_Load_kW'] * df_year['Scaling_Factor']
    return df_year


@st.cache_data(show_spinner=False)
def run_pv_simulation(lat, lon, tilt, azimuth, dc_kw, ac_kw, eta):
    tmy_data = iotools.get_pvgis_tmy(lat, lon, map_variables=True)[0]
    tmy_data.index = tmy_data.index.tz_convert('Asia/Bangkok')
    tmy_data['month'] = tmy_data.index.month
    tmy_data['day']   = tmy_data.index.day
    tmy_data['hour']  = tmy_data.index.hour
    tmy_data = tmy_data.sort_values(['month', 'day', 'hour'])
    tmy_data.index = pd.date_range(start='2023-01-01 00:00', end='2023-12-31 23:00', freq='1H', tz='Asia/Bangkok')
    location = Location(latitude=lat, longitude=lon, tz='Asia/Bangkok')
    system = PVSystem(
        surface_tilt=tilt,
        surface_azimuth=azimuth,
        module_parameters={'pdc0': dc_kw * 1000, 'gamma_pdc': -0.0035},
        inverter_parameters={'pdc0': (ac_kw * 1000) / eta, 'pac0': ac_kw * 1000, 'eta_inv_nom': eta},
        temperature_model_parameters=TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']
    )
    mc = ModelChain(system, location,
                    aoi_model='physical', spectral_model='no_loss',
                    dc_model='pvwatts', ac_model='pvwatts', losses_model='pvwatts')
    mc.run_model(tmy_data)
    pv_kw = (mc.results.ac / 1000).clip(lower=0)
    pv_kw.index = pd.date_range(start='2023-01-01 00:00', end='2023-12-31 23:00', freq='1H')
    return pv_kw


# ─────────────────────────────────────────
# Template Excel Generator
# ─────────────────────────────────────────
@st.cache_data
def make_template_excel():
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        pd.DataFrame({'Time': ['00:00','06:00','09:00','12:00','18:00','21:00','23:59'],
                      'Load_kW': [20, 55, 90, 100, 80, 45, 22]}).to_excel(writer, sheet_name='Weekday', index=False)
        pd.DataFrame({'Time': ['00:00','08:00','12:00','20:00','23:59'],
                      'Load_kW': [15, 50, 65, 55, 20]}).to_excel(writer, sheet_name='Weekend', index=False)
        pd.DataFrame({'Month': list(range(1,13)),
                      'Target_kWh': [45000,42000,48000,50000,52000,55000,
                                     56000,55000,51000,48000,44000,43000]}).to_excel(writer, sheet_name='Targets', index=False)
    return buf.getvalue()

# ─────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📁 ข้อมูล Input")
    uploaded = st.file_uploader("อัปโหลด Inputs.xlsx", type=["xlsx"])
    st.download_button(
        label="📄 ดาวน์โหลด Template Inputs.xlsx",
        data=make_template_excel(),
        file_name="Inputs_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    st.markdown("---")

    st.markdown("## ⚙️ ตั้งค่าระบบ PV")
    lat  = st.number_input("Latitude",  value=13.75,  format="%.4f")
    lon  = st.number_input("Longitude", value=100.51, format="%.4f")
    tilt = st.slider("มุมเอียงแผง (°)", 0, 45, 15)
    azimuth = st.slider("Azimuth (°) — 180 = ทิศใต้", 90, 270, 180)
    dc_kw = st.number_input("ขนาดระบบ DC (kW)", value=120.0, min_value=1.0)
    ac_kw = st.number_input("ขนาด Inverter AC (kW)", value=100.0, min_value=1.0)
    eta   = st.slider("Inverter Efficiency (%)", 80, 99, 96) / 100

    st.markdown("---")
    run_btn = st.button("▶ Run Simulation", type="primary", use_container_width=True)

# ─────────────────────────────────────────
# Main Area
# ─────────────────────────────────────────
if uploaded is None:
    st.markdown("""
    <div class="info-box">
        <b>👈 เริ่มต้นใช้งาน</b><br>
        อัปโหลดไฟล์ <code>Inputs.xlsx</code> ที่ Sidebar ซ้ายมือ แล้วกด <b>Run Simulation</b>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("📋 รูปแบบไฟล์ Inputs.xlsx ที่ต้องการ"):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Sheet: Weekday**")
            st.dataframe(pd.DataFrame({'Time': ['00:00','06:00','18:00','23:59'], 'Load_kW': [20,80,60,25]}), hide_index=True)
        with c2:
            st.markdown("**Sheet: Weekend**")
            st.dataframe(pd.DataFrame({'Time': ['00:00','08:00','20:00','23:59'], 'Load_kW': [15,50,45,20]}), hide_index=True)
        with c3:
            st.markdown("**Sheet: Targets**")
            st.dataframe(pd.DataFrame({'Month': list(range(1,7)), 'Target_kWh': [45000,42000,48000,50000,52000,55000]}), hide_index=True)
    st.stop()

# ─────────────────────────────────────────
# Load Excel
# ─────────────────────────────────────────
try:
    weekday_raw = pd.read_excel(uploaded, sheet_name='Weekday')
    weekend_raw = pd.read_excel(uploaded, sheet_name='Weekend')
    df_targets  = pd.read_excel(uploaded, sheet_name='Targets')
except Exception as e:
    st.error(f"❌ อ่านไฟล์ไม่ได้: {e}")
    st.stop()

for df in [weekday_raw, weekend_raw]:
    df['Time'] = pd.to_datetime('2000-01-01 ' + df['Time'].astype(str), infer_datetime_format=True)

monthly_targets = dict(zip(df_targets['Month'], df_targets['Target_kWh']))

# Compute hourly profiles
hourly_weekday = interpolate_to_hourly(weekday_raw)
hourly_weekend = interpolate_to_hourly(weekend_raw)
df_year = build_yearly_profile(hourly_weekday, hourly_weekend, monthly_targets)

# ─────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Daily Profile",
    "⚡ Yearly + PV Simulation",
    "📥 Download",
    "💰 วิเคราะห์เศรษฐศาสตร์",
])

# ── Tab 1: Daily Profile ──────────────────
with tab1:
    st.subheader("รูปทรงการใช้ไฟรายวัน: Weekday vs Weekend")
    hours = list(range(24))
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=hours, y=hourly_weekday.values,
        mode='lines+markers', name='Weekday (จันทร์-ศุกร์)',
        line=dict(color='#3b82f6', width=2.5),
        marker=dict(size=5), fill='tozeroy', fillcolor='rgba(59,130,246,0.1)'))
    fig1.add_trace(go.Scatter(x=hours, y=hourly_weekend.values,
        mode='lines+markers', name='Weekend (เสาร์-อาทิตย์)',
        line=dict(color='#ef4444', width=2.5),
        marker=dict(size=5, symbol='square'), fill='tozeroy', fillcolor='rgba(239,68,68,0.1)'))
    fig1.update_layout(
        xaxis_title='ชั่วโมง (Hour)', yaxis_title='การใช้ไฟฟ้า (kW)',
        xaxis=dict(tickvals=hours, ticktext=[f'{h:02d}:00' for h in hours], tickangle=-45),
        legend=dict(orientation='h', y=-0.25),
        hovermode='x unified', height=420,
        plot_bgcolor='#0e1117', paper_bgcolor='#0e1117',
        font=dict(color='white'), xaxis_gridcolor='#2d2d2d', yaxis_gridcolor='#2d2d2d'
    )
    st.plotly_chart(fig1, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Weekday — 24 ชั่วโมง**")
        st.dataframe(
            pd.DataFrame({'Hour': [f'{h:02d}:00' for h in hours], 'Load_kW': hourly_weekday.values.round(2)}),
            hide_index=True, height=300
        )
    with c2:
        st.markdown("**Weekend — 24 ชั่วโมง**")
        st.dataframe(
            pd.DataFrame({'Hour': [f'{h:02d}:00' for h in hours], 'Load_kW': hourly_weekend.values.round(2)}),
            hide_index=True, height=300
        )

# ── Tab 2: Yearly + PV ───────────────────
with tab2:
    # Monthly summary bar chart
    st.subheader("ผลรวมการใช้ไฟรายเดือน (Monthly kWh)")
    monthly_actual = df_year.groupby('Month')['Adjusted_Load_kWh'].sum().reset_index()
    month_names = ['ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.','ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.']
    monthly_actual['MonthName'] = monthly_actual['Month'].apply(lambda m: month_names[m-1])

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=monthly_actual['MonthName'], y=monthly_actual['Adjusted_Load_kWh'],
        name='Actual (kWh)', marker_color='#6366f1',
        text=monthly_actual['Adjusted_Load_kWh'].round(0).astype(int),
        textposition='outside'))
    fig2.add_trace(go.Scatter(
        x=monthly_actual['MonthName'],
        y=[monthly_targets.get(m, 0) for m in monthly_actual['Month']],
        name='Target (kWh)', mode='markers+lines',
        line=dict(color='#f59e0b', dash='dash'), marker=dict(size=8)))
    fig2.update_layout(
        yaxis_title='kWh', hovermode='x unified', height=380,
        plot_bgcolor='#0e1117', paper_bgcolor='#0e1117',
        font=dict(color='white'), xaxis_gridcolor='#2d2d2d', yaxis_gridcolor='#2d2d2d',
        legend=dict(orientation='h', y=-0.2)
    )
    st.plotly_chart(fig2, use_container_width=True)

    # First-week hourly chart
    st.subheader("รายชั่วโมง — สัปดาห์แรกของปี (168 ชั่วโมง)")
    first_week = df_year.iloc[:168]
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=first_week.index, y=first_week['Adjusted_Load_kWh'],
        name='Building Load', line=dict(color='#a855f7', width=2), fill='tozeroy', fillcolor='rgba(168,85,247,0.1)'))
    fig3.update_layout(
        xaxis_title='วันที่/เวลา', yaxis_title='kWh',
        height=380, hovermode='x unified',
        plot_bgcolor='#0e1117', paper_bgcolor='#0e1117',
        font=dict(color='white'), xaxis_gridcolor='#2d2d2d', yaxis_gridcolor='#2d2d2d'
    )
    st.plotly_chart(fig3, use_container_width=True)

    # PV Simulation
    st.markdown("---")
    st.subheader("⚡ PV Simulation (pvlib + PVGIS)")

    if run_btn:
        with st.spinner("🌐 กำลังดึงข้อมูลสภาพอากาศจาก PVGIS และคำนวณ PV..."):
            try:
                pv_kw = run_pv_simulation(lat, lon, tilt, azimuth, dc_kw, ac_kw, eta)
                df_year['PV_Generation_kW'] = pv_kw.values
                df_year['Net_Load_kW'] = df_year['Adjusted_Load_kWh'] - df_year['PV_Generation_kW']
                st.session_state['df_year'] = df_year
                st.session_state['pv_done'] = True
                st.success("✅ PV Simulation สำเร็จ!")
            except Exception as e:
                st.error(f"❌ ไม่สามารถดึงข้อมูล PVGIS ได้: {e}")

    if st.session_state.get('pv_done') and 'PV_Generation_kW' in st.session_state.get('df_year', pd.DataFrame()).columns:
        df_y = st.session_state['df_year']

        # Metrics
        total_load = df_y['Adjusted_Load_kWh'].sum()
        total_pv   = df_y['PV_Generation_kW'].sum()
        self_ratio = min(total_pv / total_load * 100, 100)

        m1, m2, m3 = st.columns(3)
        m1.markdown(f'<div class="metric-card"><div class="val">{total_load:,.0f}</div><div class="lbl">Total Load (kWh/ปี)</div></div>', unsafe_allow_html=True)
        m2.markdown(f'<div class="metric-card"><div class="val">{total_pv:,.0f}</div><div class="lbl">PV Generation (kWh/ปี)</div></div>', unsafe_allow_html=True)
        m3.markdown(f'<div class="metric-card"><div class="val">{self_ratio:.1f}%</div><div class="lbl">PV Coverage Ratio</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Load vs PV vs Net Load chart (first week)
        fig4 = go.Figure()
        fw = df_y.iloc[:168]
        fig4.add_trace(go.Scatter(x=fw.index, y=fw['Adjusted_Load_kWh'],
            name='Building Load', line=dict(color='#a855f7', width=2)))
        fig4.add_trace(go.Scatter(x=fw.index, y=fw['PV_Generation_kW'],
            name='PV Generation', line=dict(color='#f59e0b', width=2), fill='tozeroy', fillcolor='rgba(245,158,11,0.15)'))
        fig4.add_trace(go.Scatter(x=fw.index, y=fw['Net_Load_kW'],
            name='Net Load (ซื้อจากกริด)', line=dict(color='#94a3b8', width=1.5, dash='dash')))
        fig4.add_hline(y=0, line_dash='dot', line_color='#ef4444', annotation_text='Export to Grid')
        fig4.update_layout(
            title='Load vs PV Generation vs Net Load (สัปดาห์แรก)',
            xaxis_title='วันที่/เวลา', yaxis_title='kW',
            height=450, hovermode='x unified',
            plot_bgcolor='#0e1117', paper_bgcolor='#0e1117',
            font=dict(color='white'), xaxis_gridcolor='#2d2d2d', yaxis_gridcolor='#2d2d2d',
            legend=dict(orientation='h', y=-0.2)
        )
        st.plotly_chart(fig4, use_container_width=True)

        # Monthly PV bar chart
        monthly_pv = df_y.groupby(df_y.index.month)['PV_Generation_kW'].sum().reset_index()
        monthly_pv.columns = ['Month', 'PV_kWh']
        monthly_pv['MonthName'] = monthly_pv['Month'].apply(lambda m: month_names[m-1])
        fig5 = go.Figure()
        fig5.add_trace(go.Bar(x=monthly_pv['MonthName'], y=monthly_pv['PV_kWh'],
            name='PV (kWh)', marker_color='#f59e0b',
            text=monthly_pv['PV_kWh'].round(0).astype(int), textposition='outside'))
        fig5.update_layout(
            title='การผลิตไฟฟ้าจากโซลาร์รายเดือน',
            yaxis_title='kWh', height=350,
            plot_bgcolor='#0e1117', paper_bgcolor='#0e1117',
            font=dict(color='white'), xaxis_gridcolor='#2d2d2d', yaxis_gridcolor='#2d2d2d'
        )
        st.plotly_chart(fig5, use_container_width=True)

    else:
        st.info("👆 กด **Run Simulation** ที่ Sidebar เพื่อเริ่มจำลอง PV")

# ── Tab 3: Download ───────────────────────
with tab3:
    st.subheader("📥 ดาวน์โหลดไฟล์ผลลัพธ์")

    # Load-only CSV
    csv_load = df_year['Adjusted_Load_kWh'].round(4).to_csv(index=False, header=False).encode('utf-8')
    st.download_button(
        label="⬇️ load_profile_8760.csv  (Load เท่านั้น)",
        data=csv_load, file_name='load_profile_8760.csv', mime='text/csv',
        use_container_width=True
    )

    st.markdown("<br>", unsafe_allow_html=True)

    if st.session_state.get('pv_done') and 'PV_Generation_kW' in st.session_state.get('df_year', pd.DataFrame()).columns:
        df_y = st.session_state['df_year']
        csv_combined = df_y[['Adjusted_Load_kWh', 'PV_Generation_kW', 'Net_Load_kW']].round(4).to_csv().encode('utf-8')
        st.download_button(
            label="⬇️ combined_profile_8760.csv  (Load + PV + Net Load)",
            data=csv_combined, file_name='combined_profile_8760.csv', mime='text/csv',
            use_container_width=True
        )
    else:
        st.info("รัน PV Simulation ก่อนเพื่อดาวน์โหลด combined_profile_8760.csv")

    st.markdown("---")
    st.markdown("**ตัวอย่างข้อมูล (50 แถวแรก)**")
    preview_cols = ['Adjusted_Load_kWh']
    if 'PV_Generation_kW' in df_year.columns:
        preview_cols += ['PV_Generation_kW', 'Net_Load_kW']
    st.dataframe(df_year[preview_cols].head(50).round(4), use_container_width=True)

# ── Tab 4: Economics ─────────────────────
with tab4:
    st.subheader("💰 วิเคราะห์การลงทุนและผลตอบแทน")

    if not (st.session_state.get('pv_done') and
            'PV_Generation_kW' in st.session_state.get('df_year', pd.DataFrame()).columns):
        st.warning("⚠️ กรุณารัน **PV Simulation** ที่ Tab 2 ก่อน เพื่อให้มีข้อมูล PV Generation")
        st.stop()

    df_y = st.session_state['df_year']
    total_load_yr = df_y['Adjusted_Load_kWh'].sum()
    total_pv_yr   = df_y['PV_Generation_kW'].sum()

    st.markdown("### ⚙️ ข้อมูลสำหรับคำนวณ")
    ec1, ec2, ec3 = st.columns(3)
    with ec1:
        st.markdown("**💵 ต้นทุนและราคา**")
        total_capex    = st.number_input("มูลค่าการลงทุนรวม (บาท)", value=3_000_000, step=100_000, min_value=0)
        elec_tariff    = st.number_input("ค่าไฟฟ้าที่ประหยัดได้ (บาท/kWh)", value=4.50, step=0.10, min_value=0.0, format="%.2f")
        fit_tariff     = st.number_input("อัตรา Feed-in / Net Metering (บาท/kWh)", value=2.20, step=0.10, min_value=0.0, format="%.2f",
                                         help="ราคาที่ได้รับสำหรับไฟฟ้าที่ Export กลับกริด (0 = ไม่มี FiT)")
        elec_escalation= st.number_input("อัตราค่าไฟขึ้นราคาต่อปี (%)", value=3.0, step=0.5, min_value=0.0, format="%.1f") / 100
    with ec2:
        st.markdown("**📅 พารามิเตอร์โครงการ**")
        project_life   = st.slider("อายุโครงการ (ปี)", 10, 30, 25)
        discount_rate  = st.number_input("Discount Rate / WACC (%)", value=6.0, step=0.5, min_value=0.0, format="%.1f") / 100
        degradation    = st.number_input("อัตราเสื่อมสภาพแผง PV ต่อปี (%)", value=0.5, step=0.1, min_value=0.0, format="%.1f") / 100
        opex_pct       = st.number_input("ค่าบำรุงรักษารายปี (% ของ CAPEX)", value=1.0, step=0.1, min_value=0.0, format="%.1f") / 100
    with ec3:
        st.markdown("**🔋 Self-Consumption**")
        st.info("คำนวณจากข้อมูล 8,760 ชั่วโมงอัตโนมัติ")
        self_consumed  = np.minimum(df_y['Adjusted_Load_kWh'], df_y['PV_Generation_kW']).sum()
        exported_kwh   = (df_y['PV_Generation_kW'] - df_y['Adjusted_Load_kWh']).clip(lower=0).sum()
        sc_ratio = self_consumed / total_pv_yr * 100
        ss_ratio = self_consumed / total_load_yr * 100
        st.metric("Self-Consumption Ratio", f"{sc_ratio:.1f}%",
                  help="สัดส่วนของไฟ PV ที่ใช้ในอาคารเอง (ไม่ Export)")
        st.metric("Self-Sufficiency Ratio", f"{ss_ratio:.1f}%",
                  help="สัดส่วนของความต้องการไฟที่ PV ครอบคลุมได้")
        st.metric("Export to Grid", f"{exported_kwh:,.0f} kWh/ปี")

    st.markdown("---")

    # ── Core Calculations ──
    opex_annual = total_capex * opex_pct

    # Annual savings & cash flows
    cashflows   = [-total_capex]
    pv_gen_t    = total_pv_yr
    for yr in range(1, project_life + 1):
        elec_t    = elec_tariff   * (1 + elec_escalation) ** (yr - 1)
        fit_t     = fit_tariff    * (1 + elec_escalation) ** (yr - 1)
        sc_t      = self_consumed * (1 - degradation) ** (yr - 1)
        exp_t     = exported_kwh  * (1 - degradation) ** (yr - 1)
        savings_t = sc_t * elec_t + exp_t * fit_t - opex_annual
        cashflows.append(savings_t)

    # Simple Payback
    annual_savings_yr1 = cashflows[1]
    simple_payback = total_capex / annual_savings_yr1 if annual_savings_yr1 > 0 else float('inf')

    # NPV
    npv = sum(cf / (1 + discount_rate) ** t for t, cf in enumerate(cashflows))

    # IRR (Newton's method)
    def calc_irr(cfs):
        rate = 0.1
        for _ in range(1000):
            f  = sum(cf / (1 + rate) ** t for t, cf in enumerate(cfs))
            df = sum(-t * cf / (1 + rate) ** (t + 1) for t, cf in enumerate(cfs))
            if abs(df) < 1e-12: break
            rate -= f / df
            if rate <= -1: return None
        return rate
    irr = calc_irr(cashflows)

    # LCOE = (CAPEX + sum discounted OPEX) / sum discounted PV generation
    disc_opex   = sum(opex_annual / (1 + discount_rate) ** t for t in range(1, project_life + 1))
    disc_gen    = sum((total_pv_yr * (1 - degradation) ** (t - 1)) / (1 + discount_rate) ** t
                      for t in range(1, project_life + 1))
    lcoe = (total_capex + disc_opex) / disc_gen if disc_gen > 0 else 0

    # ── KPI Cards ──
    st.markdown("### 📊 ผลลัพธ์การวิเคราะห์")
    k1, k2, k3, k4 = st.columns(4)
    pb_color = "#10b981" if simple_payback < 10 else "#f59e0b" if simple_payback < 15 else "#ef4444"
    npv_color = "#10b981" if npv > 0 else "#ef4444"

    k1.markdown(f"""
    <div class="econ-card" style="border-top: 4px solid {pb_color}">
        <div class="lbl">Simple Payback</div>
        <div class="val">{simple_payback:.1f} ปี</div>
        <div class="sub">{'✅ คุ้มค่า' if simple_payback < project_life else '⚠️ เกินอายุโครงการ'}</div>
    </div>""", unsafe_allow_html=True)
    k2.markdown(f"""
    <div class="econ-card" style="border-top: 4px solid {npv_color}">
        <div class="lbl">NPV</div>
        <div class="val">฿{npv/1e6:.2f}M</div>
        <div class="sub">{'✅ โครงการให้ผลตอบแทน' if npv > 0 else '❌ ขาดทุน'}</div>
    </div>""", unsafe_allow_html=True)
    irr_str = f"{irr*100:.1f}%" if irr is not None else "N/A"
    irr_vs   = f"vs WACC {discount_rate*100:.1f}%" if irr else ""
    k3.markdown(f"""
    <div class="econ-card" style="border-top: 4px solid #6366f1">
        <div class="lbl">IRR</div>
        <div class="val">{irr_str}</div>
        <div class="sub">{irr_vs}</div>
    </div>""", unsafe_allow_html=True)
    k4.markdown(f"""
    <div class="econ-card" style="border-top: 4px solid #0ea5e9">
        <div class="lbl">LCOE</div>
        <div class="val">฿{lcoe:.2f}/kWh</div>
        <div class="sub">vs ค่าไฟ ฿{elec_tariff:.2f}/kWh</div>
    </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Cumulative Cash Flow Chart ──
    cumulative = np.cumsum(cashflows)
    years_axis = list(range(project_life + 1))
    colors      = ['#10b981' if v >= 0 else '#ef4444' for v in cumulative]

    fig_cf = go.Figure()
    fig_cf.add_trace(go.Bar(
        x=years_axis, y=cashflows,
        name='Cash Flow รายปี',
        marker_color=['#ef4444'] + ['#6366f1'] * project_life,
        opacity=0.7
    ))
    fig_cf.add_trace(go.Scatter(
        x=years_axis, y=cumulative,
        name='Cumulative Cash Flow', mode='lines+markers',
        line=dict(color='#f59e0b', width=2.5),
        marker=dict(color=colors, size=7)
    ))
    fig_cf.add_hline(y=0, line_dash='dash', line_color='white', opacity=0.4)
    fig_cf.update_layout(
        title='กระแสเงินสดสะสมตลอดอายุโครงการ',
        xaxis_title='ปีที่', yaxis_title='บาท',
        height=420, hovermode='x unified',
        plot_bgcolor='#0e1117', paper_bgcolor='#0e1117',
        font=dict(color='white'), xaxis_gridcolor='#2d2d2d', yaxis_gridcolor='#2d2d2d',
        legend=dict(orientation='h', y=-0.2),
        yaxis_tickformat=',.0f'
    )
    st.plotly_chart(fig_cf, use_container_width=True)

    # ── Self-Consumption Donut ──
    sc2, sc3 = st.columns(2)
    with sc2:
        fig_sc = go.Figure(go.Pie(
            labels=['Self-Consumed', 'Export to Grid'],
            values=[self_consumed, exported_kwh],
            hole=0.55,
            marker_colors=['#10b981', '#6366f1'],
            textinfo='label+percent'
        ))
        fig_sc.update_layout(
            title='การใช้ไฟ PV: Self-Consumed vs Export',
            height=340, paper_bgcolor='#0e1117', font=dict(color='white')
        )
        st.plotly_chart(fig_sc, use_container_width=True)

    with sc3:
        st.markdown("**📋 สรุปตัวเลขสำคัญ**")
        st.dataframe(pd.DataFrame({
            'รายการ': [
                'มูลค่าลงทุน (CAPEX)',
                'ค่าบำรุงรักษาต่อปี (OPEX)',
                'ประหยัดได้ปีที่ 1',
                'Simple Payback',
                'NPV',
                'IRR',
                'LCOE',
                'Self-Consumption',
                'Self-Sufficiency',
                'PV ผลิตได้ต่อปี',
            ],
            'ค่า': [
                f'฿{total_capex:,.0f}',
                f'฿{opex_annual:,.0f}/ปี',
                f'฿{annual_savings_yr1:,.0f}/ปี',
                f'{simple_payback:.1f} ปี',
                f'฿{npv:,.0f}',
                irr_str,
                f'฿{lcoe:.3f}/kWh',
                f'{sc_ratio:.1f}%',
                f'{ss_ratio:.1f}%',
                f'{total_pv_yr:,.0f} kWh',
            ]
        }), hide_index=True, use_container_width=True, height=380)
