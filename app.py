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
        
        # Clean Rows: Remove Summary and whitespace
        df = df[df[t_col].notna()]
        df = df[~df[t_col].str.contains('Summary|Total', case=False, na=False)]
        df[t_col] = df[t_col].str.strip()
        
        # Numeric clean
        for col in [a_col, cl_col, fr_col]:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        df['CSAT_Numeric'] = df[cs_col].astype(str).str.extract(r'(\d+\.?\d*)').astype(float).fillna(0)
        
        return df, {'t': t_col, 'a': a_col, 'cl': cl_col, 'fr': fr_col, 'cs': cs_col}
    except Exception as e:
        st.error(f"Error processing: {e}")
        return None

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("Settings")
    current_file = st.file_uploader("Step 1: Upload Current CSV", type="csv")
    previous_file = st.file_uploader("Step 2: Upload Previous CSV (Optional)", type="csv")
    st.divider()
    st.info("Upload your Intercom Teammate Performance exports here.")

# --- 4. MAIN DASHBOARD ---
if current_file:
    curr_data = process_data(current_file)
    if curr_data:
        df, m = curr_data
        
        st.title("📊 Teammate Intelligence")
        
        # Top KPIs
        avg_csat = df['CSAT_Numeric'][df['CSAT_Numeric']>0].mean() if not df[df['CSAT_Numeric']>0].empty else 0
        total_a = df[m['a']].sum()
        med_frt = df[m['fr']].median()

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Tickets", f"{int(total_a):,}")
        k2.metric("Avg CSAT", f"{avg_csat:.1f}%")
        k3.metric("Med. Response", f"{int(med_frt)}s")
        k4.metric("Team Size", len(df))

        # --- GAP ANALYSIS ---
        st.divider()
        st.header("📉 Gap Analysis")
        if previous_file:
            prev_data = process_data(previous_file)
            if prev_data:
                pdf, pm = prev_data
                
                # Merge current and previous on Teammate Name
                gap_df = pd.merge(
                    df[[m['t'], 'CSAT_Numeric', m['a']]], 
                    pdf[[pm['t'], 'CSAT_Numeric', pm['a']]], 
                    on=m['t'], 
                    suffixes=('_curr', '_prev')
                )
                
                if not gap_df.empty:
                    gap_df['CSAT_Delta'] = gap_df['CSAT_Numeric_curr'] - gap_df['CSAT_Numeric_prev']
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        st.subheader("🚀 Top CSAT Improvers")
                        imp = gap_df.sort_values('CSAT_Delta', ascending=False).head(5)
                        st.plotly_chart(px.bar(imp, x='CSAT_Delta', y=m['t'], orientation='h', color_discrete_sequence=['#2ECC71']), use_container_width=True)
                    
                    with c2:
                        st.subheader("⚠️ Performance Declines")
                        dec = gap_df.sort_values('CSAT_Delta', ascending=True).head(5)
                        st.plotly_chart(px.bar(dec, x='CSAT_Delta', y=m['t'], orientation='h', color_discrete_sequence=['#E74C3C']), use_container_width=True)
                else:
                    st.warning("Could not match teammates between the two files. Ensure teammate names are identical.")
        else:
            st.info("💡 Tip: Upload a 'Previous Period' CSV in the sidebar to see performance shifts and teammate growth.")

        # --- COACHING QUADRANT ---
        st.divider()
        st.header("🎯 Coaching Strategy")
        
        fig_quad = px.scatter(df, x=m['a'], y='CSAT_Numeric', 
                             text=m['t'], size=m['cl'], color='CSAT_Numeric',
                             color_continuous_scale='RdYlGn',
                             labels={m['a']: 'Volume (Tickets)', 'CSAT_Numeric': 'Quality (CSAT %)'},
                             height=600)
        
        # Add Median Lines
        fig_quad.add_hline(y=df['CSAT_Numeric'].median(), line_dash="dot", annotation_text="Avg Quality")
        fig_quad.add_vline(x=df[m['a']].median(), line_dash="dot", annotation_text="Avg Volume")
        
        st.plotly_chart(fig_quad, use_container_width=True)

        # --- DATA TABLE ---
        with st.expander("Detailed Teammate View"):
            st.dataframe(df[[m['t'], m['a'], m['cl'], 'CSAT_Numeric', m['fr']]].sort_values(m['a'], ascending=False), use_container_width=True)
else:
    st.header("Welcome, Zeek!")
    st.markdown("To begin, please upload your **Teammate Performance CSV** in the sidebar.")
    st.image("https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM2I1dm96M3R0N2F1cnR4YmZ4bmZ4bmZ4bmZ4bmZ4bmZ4bmZ4bmZ4JmVwPXYxX2ludGVybmFsX2dpZl9ieV9pZCZjdD1n/3o7TKSjPZT9KBRp_lS/giphy.gif")
