import streamlit as st
import pandas as pd
import plotly.express as px
import io

# --- 1. BRANDING & STYLE ---
st.set_page_config(page_title="Grey | Customer Intelligence", layout="wide", page_icon="🔘")

st.markdown("""
    <style>
    .main { background-color: #F8F9FB; }
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #EDEFEF; }
    h1, h2, h3 { color: #1A1A1A; font-family: 'Inter', sans-serif; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA ENGINE ---
def process_data(file):
    if file is None: return None
    try:
        bytes_data = file.getvalue()
        text_data = bytes_data.decode("utf-8").splitlines()
        
        # --- NEW STRICT HEADER SEARCH ---
        header_idx = None
        for i, line in enumerate(text_data):
            clean_line = line.replace('"', '').strip()
            # The real header row starts with 'Teammate' and has many columns
            if clean_line.startswith("Teammate") and "Conversations assigned" in clean_line:
                header_idx = i
                break
        
        if header_idx is None:
            st.error("Could not find the data table. Please check your CSV format.")
            return None
        
        # Read the CSV starting from the correct row
        df = pd.read_csv(io.StringIO("\n".join(text_data[header_idx:])))
        
        # Standardize column names
        df.columns = df.columns.str.strip().str.replace('"', '').str.replace("'", "")
        
        # --- COLUMN MAPPING ---
        def find_actual_col(targets):
            for col in df.columns:
                if any(t.lower() == col.lower() or t.lower() in col.lower() for t in targets):
                    return col
            return None

        t_col = find_actual_col(['Teammate'])
        a_col = find_actual_col(['Conversations assigned'])
        cl_col = find_actual_col(['Closed conversations by teammates', 'Closed conversations'])
        cs_col = find_actual_col(['Teammate CSAT score', 'CSAT score'])
        fr_col = find_actual_col(['Median First response time', 'First response'])
        
        if not all([t_col, a_col, cl_col]):
            st.error(f"Critical columns missing! Found: {list(df.columns)}")
            return None

        # Clean Rows: Remove Summary row
        df = df[df[t_col].notna()]
        df = df[~df[t_col].str.contains('Summary|Total', case=False, na=False)]
        df[t_col] = df[t_col].str.strip()
        
        # Numeric clean
        for col in [a_col, cl_col, fr_col]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        # CSAT clean
        if cs_col:
            df['CSAT_Numeric'] = df[cs_col].astype(str).str.extract(r'(\d+\.?\d*)').astype(float).fillna(0)
        else:
            df['CSAT_Numeric'] = 0.0
            
        return df, {'t': t_col, 'a': a_col, 'cl': cl_col, 'fr': fr_col, 'cs': cs_col}
    except Exception as e:
        st.error(f"Error in data processing: {e}")
        return None

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("Settings")
    current_file = st.file_uploader("Upload Current CSV", type="csv")
    previous_file = st.file_uploader("Upload Previous CSV", type="csv")
    st.divider()
    st.info("Upload Intercom 'Teammate Performance' exports.")

# --- 4. MAIN DASHBOARD ---
if current_file:
    result = process_data(current_file)
    if result:
        df, m = result
        
        st.title("📊 Teammate Intelligence")
        
        # Top KPIs
        avg_csat = df['CSAT_Numeric'][df['CSAT_Numeric']>0].mean() if not df[df['CSAT_Numeric']>0].empty else 0
        total_a = df[m['a']].sum()
        med_frt = df[m['fr']].median()

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Tickets", f"{int(total_a):,}")
        k2.metric("Avg CSAT", f"{avg_csat:.1f}%")
        k3.metric("Med. Response", f"{int(med_frt)}s")
        k4.metric("Active Team", len(df))

        # --- GAP ANALYSIS ---
        if previous_file:
            st.divider()
            st.header("📉 Gap Analysis")
            p_result = process_data(previous_file)
            if p_result:
                pdf, pm = p_result
                gap_df = pd.merge(df[[m['t'], 'CSAT_Numeric', m['a']]], 
                                  pdf[[pm['t'], 'CSAT_Numeric', pm['a']]], 
                                  on=m['t'], suffixes=('_curr', '_prev'))
                
                if not gap_df.empty:
                    gap_df['CSAT_Delta'] = gap_df['CSAT_Numeric_curr'] - gap_df['CSAT_Numeric_prev']
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        st.subheader("🚀 CSAT Improvers")
                        imp = gap_df.sort_values('CSAT_Delta', ascending=False).head(5)
                        st.plotly_chart(px.bar(imp, x='CSAT_Delta', y=m['t'], orientation='h', color_discrete_sequence=['#2ECC71']), use_container_width=True)
                    with c2:
                        st.subheader("⚠️ CSAT Declines")
                        dec = gap_df.sort_values('CSAT_Delta', ascending=True).head(5)
                        st.plotly_chart(px.bar(dec, x='CSAT_Delta', y=m['t'], orientation='h', color_discrete_sequence=['#E74C3C']), use_container_width=True)

        # --- COACHING QUADRANT ---
        st.divider()
        st.header("🎯 Coaching Strategy")
        fig_quad = px.scatter(df, x=m['a'], y='CSAT_Numeric', text=m['t'], size=m['cl'], color='CSAT_Numeric',
                             color_continuous_scale='RdYlGn', labels={m['a']: 'Volume', 'CSAT_Numeric': 'CSAT %'}, height=600)
        fig_quad.add_hline(y=df['CSAT_Numeric'].median(), line_dash="dot")
        fig_quad.add_vline(x=df[m['a']].median(), line_dash="dot")
        st.plotly_chart(fig_quad, use_container_width=True)

        with st.expander("Raw Data View"):
            st.dataframe(df)
else:
    st.header("Welcome, Zeek!")
    st.info("Upload your CSV files in the sidebar to begin.")
