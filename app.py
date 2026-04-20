import streamlit as st
import pandas as pd
import plotly.express as px
import io

# --- 1. BRANDING & UI CONFIG ---
st.set_page_config(page_title="Grey | Customer Intelligence", layout="wide", page_icon="🔘")

# Custom Grey.co Style UI
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #F8F9FB; }
    .metric-card { background: white; padding: 20px; border-radius: 12px; border: 1px solid #EEF0F2; }
    .insight-card { background: #000000; color: white; padding: 20px; border-radius: 12px; margin-bottom: 20px; }
    .stMetric { background: white; padding: 15px; border-radius: 10px; border: 1px solid #EEF0F2; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. THE DATA BRAIN ---
def process_data(file):
    if file is None: return None
    try:
        bytes_data = file.getvalue()
        text_data = bytes_data.decode("utf-8").splitlines()
        header_idx = None
        for i, line in enumerate(text_data):
            clean_line = line.replace('"', '').strip()
            if clean_line.startswith("Teammate") and "Conversations" in clean_line:
                header_idx = i
                break
        if header_idx is None: return None
        
        df = pd.read_csv(io.StringIO("\n".join(text_data[header_idx:])))
        df.columns = df.columns.str.strip().str.replace('"', '').str.replace("'", "")
        
        # Robust Mapping
        def find_col(keys):
            return next((c for c in df.columns if any(k.lower() in c.lower() for k in keys)), None)

        cols = {
            't': find_col(['Teammate']),
            'a': find_col(['Conversations assigned']),
            'cl': find_col(['Closed conversations']),
            'cs': find_col(['CSAT score']),
            'fr': find_col(['First response time']),
            'eff': find_col(['closed per active hour']) # Efficiency metric
        }

        df = df[df[cols['t']].notna() & ~df[cols['t']].str.contains('Summary|Total', case=False, na=False)]
        df[cols['t']] = df[cols['t']].str.strip()
        
        # Numeric Clean
        for c in [cols['a'], cols['cl'], cols['fr'], cols['eff']]:
            if c: df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        df['CSAT_Numeric'] = df[cols['cs']].astype(str).str.extract(r'(\d+\.?\d*)').astype(float).fillna(0)
        
        return df, cols
    except: return None

# --- 3. SIDEBAR ---
with st.sidebar:
    st.image("https://images.squarespace-cdn.com/content/v1/6149a46f2541810d72023d60/8604314e-6e2c-473d-8e8e-d965e6480928/Grey_Logo_Black.png", width=120)
    st.title("Data Intelligence")
    curr_file = st.file_uploader("Current Period (April)", type="csv")
    prev_file = st.file_uploader("Previous Period (March)", type="csv")
    st.divider()
    st.caption("Grey Customer Success Tool v2.0")

# --- 4. MAIN DASHBOARD ---
if curr_file:
    curr_res = process_data(curr_file)
    if curr_res:
        df, m = curr_res
        
        # --- NARRATIVE INTELLIGENCE SECTION ---
        st.markdown('<div class="insight-card">', unsafe_allow_html=True)
        st.subheader("💡 Strategic Intelligence")
        
        # Logic for automated insights
        top_perf = df.loc[df['CSAT_Numeric'].idxmax(), m['t']]
        slowest_resp = df.loc[df[m['fr']].idxmax(), m['t']]
        efficiency_avg = df[m['eff']].mean()
        
        col_ins1, col_ins2 = st.columns(2)
        with col_ins1:
            st.write(f"**Quality Lead:** {top_perf} is currently setting the team benchmark for quality.")
            st.write(f"**Efficiency Benchmark:** The team is closing an average of {efficiency_avg:.1f} tickets per active hour.")
        
        if prev_file:
            prev_res = process_data(prev_file)
            if prev_res:
                pdf, pm = prev_res
                # Quick trend logic
                curr_vol = df[m['a']].sum()
                prev_vol = pdf[pm['a']].sum()
                vol_change = ((curr_vol - prev_vol) / prev_vol) * 100
                with col_ins2:
                    trend_text = "up" if vol_change > 0 else "down"
                    st.write(f"**Capacity Note:** Ticket volume is {trend_text} by {abs(vol_change):.1f}% compared to last period.")
                    if vol_change > 10 and df[m['fr']].median() > pdf[pm['fr']].median():
                        st.write("⚠️ **Alert:** Response times are increasing alongside volume. Capacity limit reached.")
        st.markdown('</div>', unsafe_allow_html=True)

        # --- KPI ROW ---
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Tickets Assigned", f"{int(df[m['a']].sum()):,}")
        k2.metric("Avg Team CSAT", f"{df['CSAT_Numeric'][df['CSAT_Numeric']>0].mean():.1f}%")
        k3.metric("Response Time (Med)", f"{int(df[m['fr']].median())}s")
        k4.metric("Efficiency (Tkt/Hr)", f"{efficiency_avg:.1f}")

        # --- GAP ANALYSIS ---
        if prev_file and prev_res:
            st.divider()
            st.header("📉 Performance Gap Analysis")
            pdf, pm = prev_res
            gap_df = pd.merge(df[[m['t'], 'CSAT_Numeric', m['a']]], 
                              pdf[[pm['t'], 'CSAT_Numeric', pm['a']]], 
                              on=m['t'], suffixes=('_curr', '_prev'))
            
            gap_df['CSAT_Delta'] = gap_df['CSAT_Numeric_curr'] - gap_df['CSAT_Numeric_prev']
            
            g1, g2 = st.columns(2)
            with g1:
                st.subheader("🚀 CSAT Gains")
                fig_g = px.bar(gap_df.sort_values('CSAT_Delta', ascending=False).head(5), 
                               x='CSAT_Delta', y=m['t'], orientation='h', color_discrete_sequence=['#00D1FF'])
                st.plotly_chart(fig_g, use_container_width=True)
            with g2:
                st.subheader("🔻 CSAT Drops")
                fig_d = px.bar(gap_df.sort_values('CSAT_Delta').head(5), 
                               x='CSAT_Delta', y=m['t'], orientation='h', color_discrete_sequence=['#FF4B4B'])
                st.plotly_chart(fig_d, use_container_width=True)

        # --- THE INTELLIGENCE QUADRANT ---
        st.divider()
        st.header("🎯 Coaching & Capacity Quadrant")
        fig_q = px.scatter(df, x=m['eff'], y='CSAT_Numeric', text=m['t'], size=m['a'], color='CSAT_Numeric',
                          color_continuous_scale='Viridis', labels={m['eff']: 'Tickets per Hour', 'CSAT_Numeric': 'Quality (CSAT %)'},
                          height=600)
        # Quadrant lines based on medians
        fig_q.add_hline(y=df['CSAT_Numeric'].median(), line_dash="dot", annotation_text="Quality Median")
        fig_q.add_vline(x=df[m['eff']].median(), line_dash="dot", annotation_text="Efficiency Median")
        
        st.plotly_chart(fig_q, use_container_width=True)
        
        with st.expander("Reading the Intelligence Quadrant"):
            st.write("""
            - **Top Right (High Speed, High Quality):** Future Leads / Top Performers.
            - **Top Left (Low Speed, High Quality):** Meticulous workers. Good for complex tickets.
            - **Bottom Right (High Speed, Low Quality):** BURN-OUT RISK. Moving too fast, making errors.
            - **Bottom Left (Low Speed, Low Quality):** Training required.
            """)

        # --- DATA TABLE ---
        with st.expander("Full Intelligence Table"):
            st.dataframe(df.sort_values('CSAT_Numeric', ascending=False), use_container_width=True)
else:
    st.header("Grey Customer Intelligence")
    st.info("Upload your Intercom exports to begin generating strategic insights.")
