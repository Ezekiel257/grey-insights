import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io

# --- 1. BRANDING & STYLE ---
st.set_page_config(page_title="Grey | Customer Intelligence", layout="wide", page_icon="🔘")

# Grey.co inspired styling
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background-color: #F8F9FB; }
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #EDEFEF; box-shadow: 0 4px 6px rgba(0,0,0,0.02); }
    div[data-testid="stExpander"] { background-color: #ffffff; border-radius: 12px; }
    .status-card { background: white; padding: 20px; border-radius: 12px; border-left: 5px solid #000000; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA ENGINE ---
def process_data(file):
    if file is None: return None
    try:
        bytes_data = file.getvalue()
        text_data = bytes_data.decode("utf-8").splitlines()
        header_idx = next((i for i, line in enumerate(text_data) if "Teammate" in line and "Conversations" in line), None)
        if header_idx is None: return None
        
        df = pd.read_csv(io.StringIO("\n".join(text_data[header_idx:])))
        df.columns = df.columns.str.strip().str.replace('"', '').str.replace("'", "")
        
        # Mapping
        t_col = next((c for c in df.columns if 'Teammate' in c), 'Teammate')
        a_col = next((c for c in df.columns if 'assigned' in c.lower()), 'Assigned')
        cl_col = next((c for c in df.columns if 'closed' in c.lower() and 'hour' not in c.lower()), 'Closed')
        cs_col = next((c for c in df.columns if 'CSAT' in c), 'CSAT')
        fr_col = next((c for c in df.columns if 'First response' in c), 'FRT')
        
        # Clean & Filter
        df = df[df[t_col].notna() & ~df[t_col].str.contains('Summary|Total', case=False, na=False)]
        
        # Numeric clean
        for col in [a_col, cl_col, fr_col]:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        df['CSAT_Numeric'] = df[cs_col].astype(str).str.extract(r'(\d+\.?\d*)').astype(float).fillna(0)
        
        return df, {'t': t_col, 'a': a_col, 'cl': cl_col, 'fr': fr_col, 'cs': cs_col}
    except: return None

# --- 3. SIDEBAR ---
with st.sidebar:
    st.image("https://images.squarespace-cdn.com/content/v1/6149a46f2541810d72023d60/8604314e-6e2c-473d-8e8e-d965e6480928/Grey_Logo_Black.png", width=150)
    st.title("Settings")
    current_file = st.file_uploader("Upload Current Period", type="csv")
    previous_file = st.file_uploader("Upload Comparison Period", type="csv")
    st.divider()
    target_csat = st.slider("CSAT Target %", 0, 100, 85)

# --- 4. MAIN DASHBOARD ---
if current_file:
    curr_data = process_data(current_file)
    if curr_data:
        df, m = curr_data
        
        # Header
        st.title("Dashboard Overview")
        st.markdown(f"Analysis for **{len(df)} Teammates**")

        # Top KPIs
        avg_csat = df['CSAT_Numeric'][df['CSAT_Numeric']>0].mean()
        total_a = df[m['a']].sum()
        med_frt = df[m['fr']].median()

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Tickets", f"{int(total_assigned := total_a):,}")
        k2.metric("Avg CSAT", f"{avg_csat:.1f}%")
        k3.metric("Med. Response", f"{int(med_frt)}s")
        k4.metric("Resolution Rate", f"{(df[m['cl']].sum()/total_a*100):.1f}%")

        # --- GAP ANALYSIS SECTION ---
        if previous_file:
            st.divider()
            st.subheader("📉 The Performance Gap")
            prev_data = process_data(previous_file)
            if prev_data:
                pdf, pm = prev_data
                
                # Merge data to compare teammates
                gap_df = pd.merge(
                    df[[m['t'], 'CSAT_Numeric', m['a']]], 
                    pdf[[pm['t'], 'CSAT_Numeric', pm['a']]], 
                    left_on=m['t'], right_on=pm['t'], 
                    suffixes=('_curr', '_prev')
                )
                gap_df['CSAT_Delta'] = gap_df['CSAT_Numeric_curr'] - gap_df['CSAT_Numeric_prev']
                
                # Visualizing the Movers
                col_left, col_right = st.columns(2)
                with col_left:
                    st.write("### 🚀 Top CSAT Improvers")
                    improvers = gap_df.sort_values('CSAT_Delta', ascending=False).head(5)
                    fig_imp = px.bar(improvers, x='CSAT_Delta', y=m['t']+'_curr', orientation='h', 
                                     color_discrete_sequence=['#2ECC71'])
                    st.plotly_chart(fig_imp, use_container_width=True)
                
                with col_right:
                    st.write("### ⚠️ Performance Declines")
                    decliners = gap_df.sort_values('CSAT_Delta', ascending=True).head(5)
                    fig_dec = px.bar(decliners, x='CSAT_Delta', y=m['t']+'_curr', orientation='h', 
                                     color_discrete_sequence=['#E74C3C'])
                    st.plotly_chart(fig_dec, use_container_width=True)

        # --- COACHING QUADRANT ---
        st.divider()
        st.subheader("🎯 Coaching Strategy Quadrant")
        
        # Calculate Medians for Quadrant Lines
        med_vol = df[m['a']].median()
        med_csat = df['CSAT_Numeric'].median()
        
        fig_quad = px.scatter(df, x=m['a'], y='CSAT_Numeric', 
                             text=m['t'], size=m['cl'], color='CSAT_Numeric',
                             color_continuous_scale='RdYlGn',
                             labels={m['a']: 'Volume (Tickets)', 'CSAT_Numeric': 'Quality (CSAT %)'})
        
        # Add Quadrant lines
        fig_quad.add_hline(y=med_csat, line_dash="dot", annotation_text="Quality Median")
        fig_quad.add_vline(x=med_vol, line_dash="dot", annotation_text="Volume Median")
        
        st.plotly_chart(fig_quad, use_container_width=True)
        
        with st.expander("How to read this chart?"):
            st.write("""
            - **Top Right (High Volume, High CSAT):** Your Rockstars.
            - **Top Left (Low Volume, High CSAT):** Quality focused, can take more tickets.
            - **Bottom Right (High Volume, Low CSAT):** Burnout risk! Moving fast but losing quality.
            - **Bottom Left (Low Volume, Low CSAT):** Needs urgent coaching or training.
            """)

        # --- DATA TABLE ---
        st.divider()
        st.subheader("📋 Raw Intelligence Feed")
        st.dataframe(df[[m['t'], m['a'], m['cl'], 'CSAT_Numeric', m['fr']]].style.background_gradient(subset=['CSAT_Numeric'], cmap='RdYlGn'))

else:
    # Landing Page
    st.info("👋 Hello Zeek! Please upload the April CSV data in the sidebar to generate the Grey Intelligence Report.")
    st.image("https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHJueGZ4bmZ4bmZ4bmZ4bmZ4bmZ4bmZ4bmZ4bmZ4bmZ4bmZ4bmZ4JmVwPXYxX2ludGVybmFsX2dpZl9ieV9pZCZjdD1n/3o7TKMGpxV90dcI012/giphy.gif")
