import streamlit as st
import pandas as pd
import plotly.express as px
import io

# --- PAGE CONFIG ---
st.set_page_config(page_title="Grey CS Intelligence", layout="wide", page_icon="📈")

# Custom CSS for Grey Branding
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 Grey Customer Success Intelligence")

# --- ROBUST DATA PROCESSING ---
def process_data(file):
    if file is None: return None
    
    # Read the file as raw text first to find the header row
    content = file.getvalue().decode("utf-8").splitlines()
    header_idx = 0
    for i, line in enumerate(content):
        if "Teammate" in line and "Conversations assigned" in line:
            header_idx = i
            break
    
    # Reload the dataframe starting from the correct header row
    file.seek(0)
    df = pd.read_csv(file, skiprows=header_idx)
    
    # Remove any completely empty columns or rows
    df = df.dropna(how='all', axis=1).dropna(how='all', axis=0)

    # Clean Numeric Columns (Remove commas and convert to numbers)
    cols_to_clean = [
        'Conversations assigned', 'Conversations replied to', 'Replies sent', 
        'Closed conversations by teammates', 'Median First response time',
        'Median Teammate handling time', 'Conversations closed per active hour'
    ]
    
    for col in cols_to_clean:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    # Clean CSAT (Extract the percentage number)
    if 'Teammate CSAT score' in df.columns:
        # This handles formats like "79.8% (2,057/2,578)" or "89.6%"
        df['CSAT_Val'] = df['Teammate CSAT score'].astype(str).str.extract(r'(\d+\.?\d*)').astype(float)
    
    return df

# --- SIDEBAR UPLOAD ---
st.sidebar.header("Data Source")
current_file = st.sidebar.file_uploader("Upload CURRENT Period CSV", type="csv")
previous_file = st.sidebar.file_uploader("Upload PREVIOUS Period CSV (Optional)", type="csv")

if current_file:
    try:
        curr_df_raw = process_data(current_file)
        
        # Validation: Check if 'Teammate' column exists after processing
        if 'Teammate' not in curr_df_raw.columns:
            st.error("Could not find the 'Teammate' column. Please check your CSV format.")
            st.stop()

        # Separate Summary from Teammates
        summary_mask = curr_df_raw['Teammate'].str.strip() == 'Summary'
        summary_data = curr_df_raw[summary_mask].iloc[0]
        df = curr_df_raw[~summary_mask].copy()

        # --- TOP METRICS ---
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Tickets", f"{int(summary_data['Conversations assigned']):,}")
        
        # Safe CSAT display
        csat_display = str(summary_data['Teammate CSAT score']).split('%')[0]
        m2.metric("Avg CSAT", f"{csat_display}%")
        
        m3.metric("Median Response", f"{int(summary_data['Median First response time'])}s")
        m4.metric("Active Teammates", len(df))

        # --- GAP ANALYSIS ---
        if previous_file:
            prev_df_raw = process_data(previous_file)
            prev_summary = prev_df_raw[prev_df_raw['Teammate'].str.strip() == 'Summary'].iloc[0]
            
            st.subheader("📉 Gap Analysis (vs Last Period)")
            
            vol_delta = summary_data['Conversations assigned'] - prev_summary['Conversations assigned']
            
            # CSAT Delta calculation
            csat_curr = float(str(summary_data['Teammate CSAT score']).split('%')[0])
            csat_prev = float(str(prev_summary['Teammate CSAT score']).split('%')[0])
            csat_delta = csat_curr - csat_prev
            
            g1, g2 = st.columns(2)
            g1.metric("Volume Change", f"{int(vol_delta)} Tickets", delta=int(vol_delta), delta_color="inverse")
            g2.metric("CSAT Shift", f"{csat_curr}%", delta=f"{csat_delta:.1f}%")

        # --- VISUALS ---
        st.divider()
        col_a, col_b = st.columns(2)

        with col_a:
            st.write("### 🏆 Teammate CSAT Rankings")
            fig_csat = px.bar(df.sort_values('CSAT_Val'), x='CSAT_Val', y='Teammate', 
                              orientation='h', color='CSAT_Val', 
                              color_continuous_scale='RdYlGn', text_auto='.1f')
            st.plotly_chart(fig_csat, use_container_width=True)

        with col_b:
            st.write("### ⚡ Workload vs. Speed")
            fig_scatter = px.scatter(df, x='Conversations assigned', y='Median First response time',
                                     size='Closed conversations by teammates', hover_name='Teammate',
                                     color='CSAT_Val', title="Bigger bubble = More closures")
            st.plotly_chart(fig_scatter, use_container_width=True)

        # --- AI INSIGHTS ---
        st.subheader("💡 Automated Intelligence")
        
        # Calculate Team Median for Comparison
        team_avg_speed = df['Median First response time'].median()
        
        top_perf = df.loc[df['Conversations closed per active hour'].idxmax()]
        slowest = df.loc[df['Median First response time'].idxmax()]
        
        c1, c2 = st.columns(2)
        c1.info(f"✅ **Efficiency Hero:** **{top_perf['Teammate']}** is the fastest closer at {top_perf['Conversations closed per active hour']} tickets/hr.")
        c2.warning(f"⚠️ **Response Alert:** **{slowest['Teammate']}** response time ({slowest['Median First response time']}s) is above the team median ({team_avg_speed}s).")

    except Exception as e:
        st.error(f"An error occurred while processing the file: {e}")
        st.info("Double check that you are uploading the 'Teammate Performance' export from Intercom.")

else:
    st.info("👋 Welcome Zeek! Please upload the CSV export from April to begin.")
