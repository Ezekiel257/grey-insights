import streamlit as st
import pandas as pd
import plotly.express as px

# --- PAGE CONFIG ---
st.set_page_config(page_title="Grey CS Intelligence", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #eee; }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 Grey Customer Success Intelligence")

def process_data(file):
    if file is None: return None
    
    # 1. Find the header row dynamically
    content = file.getvalue().decode("utf-8").splitlines()
    header_idx = None
    for i, line in enumerate(content):
        if "Teammate" in line and "Conversations assigned" in line:
            header_idx = i
            break
    
    if header_idx is None:
        return None

    # 2. Load Data
    file.seek(0)
    df = pd.read_csv(file, skiprows=header_idx)
    df = df.dropna(how='all', axis=1).dropna(how='all', axis=0)

    # 3. Clean names and remove the "Summary" row if it exists to avoid double counting
    df = df[~df['Teammate'].str.contains('Summary|Total', na=False, case=False)]

    # 4. Clean Numeric Columns
    cols_to_clean = [
        'Conversations assigned', 'Conversations replied to', 'Replies sent', 
        'Closed conversations by teammates', 'Median First response time',
        'Median Teammate handling time', 'Conversations closed per active hour'
    ]
    
    for col in cols_to_clean:
        if col in df.columns:
            # Remove commas and convert to float
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    # 5. Extract CSAT Numeric
    if 'Teammate CSAT score' in df.columns:
        df['CSAT_Val'] = df['Teammate CSAT score'].astype(str).str.extract(r'(\d+\.?\d*)').astype(float).fillna(0)
    
    return df

# --- SIDEBAR ---
st.sidebar.header("Upload Center")
current_file = st.sidebar.file_uploader("Upload Current CSV", type="csv")
previous_file = st.sidebar.file_uploader("Upload Previous CSV (Optional)", type="csv")

if current_file:
    df = process_data(current_file)
    
    if df is None or df.empty:
        st.error("Could not find teammate data in this file. Please check the export format.")
    else:
        # --- CALCULATE TOTALS MANUALLY (More reliable than looking for a 'Summary' row) ---
        total_tickets = df['Conversations assigned'].sum()
        avg_csat = df['CSAT_Val'][df['CSAT_Val'] > 0].mean() # Avg of teammates who have a score
        med_response = df['Median First response time'].median()

        # --- TOP METRICS ---
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Tickets", f"{int(total_tickets):,}")
        m2.metric("Avg Team CSAT", f"{avg_csat:.1f}%")
        m3.metric("Median Response", f"{int(med_response)}s")
        m4.metric("Active Teammates", len(df))

        # --- GAP ANALYSIS ---
        if previous_file:
            prev_df = process_data(previous_file)
            if prev_df is not None:
                st.subheader("📉 Gap Analysis")
                prev_total = prev_df['Conversations assigned'].sum()
                prev_csat = prev_df['CSAT_Val'][prev_df['CSAT_Val'] > 0].mean()
                
                vol_delta = total_tickets - prev_total
                csat_delta = avg_csat - prev_csat
                
                g1, g2 = st.columns(2)
                g1.metric("Volume Change", f"{int(vol_delta)} Tickets", delta=int(vol_delta), delta_color="inverse")
                g2.metric("CSAT Shift", f"{avg_csat:.1f}%", delta=f"{csat_delta:.1f}%")

        # --- VISUALS ---
        st.divider()
        col_a, col_b = st.columns(2)

        with col_a:
            st.write("### 🏆 Teammate CSAT Rankings")
            # Filter out people with 0 CSAT for the chart
            chart_df = df[df['CSAT_Val'] > 0].sort_values('CSAT_Val')
            fig_csat = px.bar(chart_df, x='CSAT_Val', y='Teammate', 
                              orientation='h', color='CSAT_Val', 
                              color_continuous_scale='RdYlGn', text_auto='.1f')
            st.plotly_chart(fig_csat, use_container_width=True)

        with col_b:
            st.write("### ⚡ Workload vs. Speed")
            fig_scatter = px.scatter(df, x='Conversations assigned', y='Median First response time',
                                     size='Closed conversations by teammates', hover_name='Teammate',
                                     color='CSAT_Val', title="Bigger bubble = More closures")
            st.plotly_chart(fig_scatter, use_container_width=True)

        # --- INTELLIGENCE ---
        st.subheader("💡 Automated Intelligence")
        
        top_perf = df.loc[df['Conversations closed per active hour'].idxmax()]
        slowest = df.loc[df['Median First response time'].idxmax()]
        
        c1, c2 = st.columns(2)
        c1.info(f"✅ **Efficiency Hero:** **{top_perf['Teammate']}** is the fastest closer ({top_perf['Conversations closed per active hour']} tkt/hr).")
        c2.warning(f"⚠️ **Response Alert:** **{slowest['Teammate']}** has the highest wait time at {int(slowest['Median First response time'])}s.")

        with st.expander("View Cleaned Data Table"):
            st.dataframe(df)
else:
    st.info("Please upload your CSV to start.")
