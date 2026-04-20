import streamlit as st
import pandas as pd
import plotly.express as px

# --- PAGE CONFIG ---
st.set_page_config(page_title="Grey CS Intelligence", layout="wide", page_icon="📈")

# Custom Styling
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #eee; }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 Grey Customer Success Intelligence")

def process_data(file):
    if file is None: return None
    
    # 1. Read the file into a dataframe
    # We read the whole thing and then find the header row
    try:
        raw_df = pd.read_csv(file, header=None)
    except Exception as e:
        st.error(f"Error reading file: {e}")
        return None

    # 2. Find the row that contains 'Teammate'
    header_row_index = None
    for i, row in raw_df.iterrows():
        if row.astype(str).str.contains('Teammate', case=False).any():
            header_row_index = i
            break
            
    if header_row_index is None:
        st.error("Could not find 'Teammate' column in the file.")
        return None

    # 3. Re-read the file from that header row
    file.seek(0)
    df = pd.read_csv(file, skiprows=header_row_index)
    
    # 4. CLEAN COLUMN NAMES (The most important part)
    # This removes extra spaces, quotes, and makes everything lowercase for easy matching
    df.columns = df.columns.str.strip().str.replace('"', '').str.replace("'", "")
    
    # 5. Map Columns Dynamically (Look for keywords rather than exact names)
    def find_col(keywords):
        for col in df.columns:
            if any(k.lower() in col.lower() for k in keywords):
                return col
        return None

    col_map = {
        'teammate': find_col(['Teammate']),
        'assigned': find_col(['Conversations assigned']),
        'replied': find_col(['Conversations replied to']),
        'closed': find_col(['Closed conversations']),
        'csat': find_col(['CSAT score']),
        'frt': find_col(['First response time']),
        'efficiency': find_col(['closed per active hour'])
    }

    # Verify we found the main ones
    if not col_map['teammate'] or not col_map['assigned']:
        st.error(f"Missing critical columns. Found: {list(df.columns)}")
        return None

    # 6. Filter out the Summary row and empty rows
    df = df[df[col_map['teammate']].notna()]
    df = df[~df[col_map['teammate']].str.contains('Summary|Total', na=False, case=False)]

    # 7. Convert Numeric data
    numeric_cols = [col_map['assigned'], col_map['replied'], col_map['closed'], col_map['frt']]
    for col in numeric_cols:
        if col:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.replace('"', ''), errors='coerce').fillna(0)

    # 8. Clean CSAT
    if col_map['csat']:
        df['CSAT_Numeric'] = df[col_map['csat']].astype(str).str.extract(r'(\d+\.?\d*)').astype(float).fillna(0)
    
    # Return cleaned df and the mapping
    return df, col_map

# --- APP LOGIC ---
current_file = st.sidebar.file_uploader("Upload Current CSV", type="csv")
previous_file = st.sidebar.file_uploader("Upload Previous CSV", type="csv")

if current_file:
    result = process_data(current_file)
    if result:
        df, cmap = result
        
        # --- CALCULATIONS ---
        total_tickets = df[cmap['assigned']].sum()
        avg_csat = df['CSAT_Numeric'][df['CSAT_Numeric'] > 0].mean()
        med_frt = df[cmap['frt']].median()

        # --- METRICS ---
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Assigned", f"{int(total_tickets):,}")
        m2.metric("Avg CSAT", f"{avg_csat:.1f}%")
        m3.metric("Med. Response", f"{int(med_frt)}s")
        m4.metric("Team Size", len(df))

        # --- GAP ANALYSIS ---
        if previous_file:
            prev_result = process_data(previous_file)
            if prev_result:
                pdf, pcmap = prev_result
                st.subheader("📉 Performance Gap Analysis")
                
                prev_total = pdf[pcmap['assigned']].sum()
                vol_delta = total_tickets - prev_total
                
                g1, g2 = st.columns(2)
                g1.metric("Volume vs Last Upload", f"{int(total_tickets)}", delta=int(vol_delta), delta_color="inverse")
                
                prev_csat = pdf['CSAT_Numeric'][pdf['CSAT_Numeric'] > 0].mean()
                csat_delta = avg_csat - prev_csat
                g2.metric("CSAT vs Last Upload", f"{avg_csat:.1f}%", delta=f"{csat_delta:.1f}%")

        # --- CHARTS ---
        st.divider()
        c1, c2 = st.columns(2)
        
        with c1:
            st.write("### 🏆 CSAT Ranking")
            fig = px.bar(df.sort_values('CSAT_Numeric'), x='CSAT_Numeric', y=cmap['teammate'], 
                         orientation='h', color='CSAT_Numeric', color_continuous_scale='RdYlGn')
            st.plotly_chart(fig, use_container_width=True)
            
        with c2:
            st.write("### ⚡ Workload Efficiency")
            fig2 = px.scatter(df, x=cmap['assigned'], y=cmap['frt'], 
                              size=cmap['closed'], hover_name=cmap['teammate'],
                              title="Bubble Size = Tickets Closed")
            st.plotly_chart(fig2, use_container_width=True)

        # --- TEAM DRILLDOWN ---
        with st.expander("🔍 View Detailed Teammate Breakdown"):
            st.table(df[[cmap['teammate'], cmap['assigned'], 'CSAT_Numeric', cmap['frt']]])
