import streamlit as st
import pandas as pd
import plotly.express as px
import io

# --- PAGE CONFIG ---
st.set_page_config(page_title="Grey CS Intelligence", layout="wide", page_icon="📈")

# Custom CSS to make it look like Grey's branding
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 Grey Customer Success Intelligence")
st.markdown("Upload your Intercom/Ticket exports to generate instant gap analysis and performance insights.")

# --- HELPER FUNCTIONS ---
def process_data(file):
    if file is None: return None
    # Intercom exports often have metadata in the first 6 rows
    df = pd.read_csv(file, skiprows=6)
    
    # Clean Numeric Columns
    cols_to_clean = [
        'Conversations assigned', 'Conversations replied to', 'Replies sent', 
        'Closed conversations by teammates', 'Median First response time',
        'Median Teammate handling time'
    ]
    
    for col in cols_to_clean:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    # Clean CSAT (Extract the percentage)
    if 'Teammate CSAT score' in df.columns:
        df['CSAT_Val'] = df['Teammate CSAT score'].str.extract(r'(\d+\.?\d*)').astype(float)
    
    return df

# --- SIDEBAR UPLOAD ---
st.sidebar.header("Data Source")
current_file = st.sidebar.file_uploader("Upload CURRENT Period CSV", type="csv")
previous_file = st.sidebar.file_uploader("Upload PREVIOUS Period CSV (Optional)", type="csv")

if current_file:
    curr_df_raw = process_data(current_file)
    
    # Separate Summary from Teammates
    summary_data = curr_df_raw[curr_df_raw['Teammate'] == 'Summary'].iloc[0]
    df = curr_df_raw[curr_df_raw['Teammate'] != 'Summary'].copy()

    # --- TOP METRICS ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Tickets", f"{int(summary_data['Conversations assigned']):,}")
    m2.metric("Avg CSAT", f"{summary_data['Teammate CSAT score'].split('%')[0]}%")
    m3.metric("Median Response", f"{int(summary_data['Median First response time'])}s")
    m4.metric("Team Size", len(df))

    # --- GAP ANALYSIS LOGIC ---
    if previous_file:
        prev_df_raw = process_data(previous_file)
        prev_summary = prev_df_raw[prev_df_raw['Teammate'] == 'Summary'].iloc[0]
        
        st.subheader("📉 Gap Analysis (Performance vs Last Period)")
        
        # Calculate Delta
        vol_delta = summary_data['Conversations assigned'] - prev_summary['Conversations assigned']
        csat_curr = float(summary_data['Teammate CSAT score'].split('%')[0])
        csat_prev = float(prev_summary['Teammate CSAT score'].split('%')[0])
        csat_delta = csat_curr - csat_prev
        
        g1, g2 = st.columns(2)
        g1.metric("Volume Change", f"{int(vol_delta)} Tickets", delta=int(vol_delta), delta_color="inverse")
        g2.metric("CSAT Shift", f"{csat_curr}%", delta=f"{csat_delta:.1f}%")

    # --- VISUAL INSIGHTS ---
    st.divider()
    col_a, col_b = st.columns(2)

    with col_a:
        st.write("### 🏆 Teammate CSAT Rankings")
        fig_csat = px.bar(df.sort_values('CSAT_Val'), x='CSAT_Val', y='Teammate', 
                          orientation='h', color='CSAT_Val', color_continuous_scale='RdYlGn',
                          text_auto=True)
        st.plotly_chart(fig_csat, use_container_width=True)

    with col_b:
        st.write("### ⚡ Response Time vs. Workload")
        fig_scatter = px.scatter(df, x='Conversations assigned', y='Median First response time',
                                 size='Closed conversations by teammates', hover_name='Teammate',
                                 color='CSAT_Val', title="Bigger bubble = More closures")
        st.plotly_chart(fig_scatter, use_container_width=True)

    # --- AI-STYLE INSIGHTS ---
    st.subheader("💡 Automated Intelligence Insights")
    
    insights = []
    # Efficiency Insight
    top_efficiency = df.loc[df['Conversations closed per active hour'].idxmax()]
    insights.append(f"✅ **Efficiency Hero:** **{top_efficiency['Teammate']}** is closing **{top_efficiency['Conversations closed per active hour']}** tickets per hour (Highest in team).")
    
    # Bottleneck Insight
    bottleneck = df.loc[df['Median First response time'].idxmax()]
    insights.append(f"⚠️ **Bottleneck Alert:** **{bottleneck['Teammate']}** has the highest median response time ({bottleneck['Median First response time']}s).")
    
    # Quality Insight
    low_csat = df[df['CSAT_Val'] < 70]
    if not low_csat.empty:
        insights.append(f"🚨 **Quality Risk:** {len(low_csat)} teammates are currently trending below 70% CSAT.")

    for insight in insights:
        st.info(insight)

    # --- FULL DATA TABLE ---
    with st.expander("View Raw Processed Table"):
        st.dataframe(df)

else:
    st.warning("Please upload the April CSV export to see the dashboard.")
