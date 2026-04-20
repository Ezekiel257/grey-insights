import streamlit as st
import pandas as pd
import plotly.express as px
import io

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
    
    try:
        # 1. Read the file as raw text to skip the 'junk' rows at the top
        bytes_data = file.getvalue()
        text_data = bytes_data.decode("utf-8").splitlines()
        
        # 2. Find the index where the actual table starts
        header_row_index = None
        for i, line in enumerate(text_data):
            # We look for the line that contains 'Teammate' AND 'Conversations assigned'
            if "Teammate" in line and "Conversations assigned" in line:
                header_row_index = i
                break
        
        if header_row_index is None:
            st.error("Could not find the data table in this file. Are you sure this is a 'Teammate Performance' export?")
            return None

        # 3. Read the CSV starting exactly from that row
        # We use io.StringIO to turn our filtered text back into a 'file' for pandas
        clean_text = "\n".join(text_data[header_row_index:])
        df = pd.read_csv(io.StringIO(clean_text))
        
        # 4. Clean column names (strip quotes and spaces)
        df.columns = df.columns.str.strip().str.replace('"', '').str.replace("'", "")
        
        # 5. Define critical columns by keyword to handle variations
        def find_col(keywords):
            for col in df.columns:
                if any(k.lower() in col.lower() for k in keywords):
                    return col
            return None

        col_map = {
            'teammate': find_col(['Teammate']),
            'assigned': find_col(['Conversations assigned']),
            'closed': find_col(['Closed conversations']),
            'csat': find_col(['CSAT score']),
            'frt': find_col(['First response time']),
            'efficiency': find_col(['closed per active hour'])
        }

        # 6. Filter out 'Summary' and 'Total' rows
        df = df[df[col_map['teammate']].notna()]
        df = df[~df[col_map['teammate']].str.contains('Summary|Total', na=False, case=False)]

        # 7. Convert numeric columns
        for key in ['assigned', 'closed', 'frt']:
            c = col_map[key]
            if c:
                df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', '').str.replace('"', ''), errors='coerce').fillna(0)

        # 8. Extract CSAT
        if col_map['csat']:
            df['CSAT_Numeric'] = df[col_map['csat']].astype(str).str.extract(r'(\d+\.?\d*)').astype(float).fillna(0)

        return df, col_map

    except Exception as e:
        st.error(f"Error processing file: {e}")
        return None

# --- APP LAYOUT ---
st.sidebar.header("Upload Center")
current_file = st.sidebar.file_uploader("Upload Current CSV", type="csv")
previous_file = st.sidebar.file_uploader("Upload Previous CSV (for Gap Analysis)", type="csv")

if current_file:
    result = process_data(current_file)
    if result:
        df, cmap = result
        
        # --- CALCULATIONS ---
        total_tickets = df[cmap['assigned']].sum()
        avg_csat = df['CSAT_Numeric'][df['CSAT_Numeric'] > 0].mean()
        med_frt = df[cmap['frt']].median()

        # --- TOP METRICS ---
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Assigned", f"{int(total_tickets):,}")
        m2.metric("Avg Team CSAT", f"{avg_csat:.1f}%")
        m3.metric("Med. Response", f"{int(med_frt)}s")
        m4.metric("Team Size", len(df))

        # --- GAP ANALYSIS ---
        if previous_file:
            prev_result = process_data(previous_file)
            if prev_result:
                pdf, pcmap = prev_result
                st.subheader("📉 Performance Gap Analysis")
                
                # Volume Change
                prev_total = pdf[pcmap['assigned']].sum()
                vol_delta = total_tickets - prev_total
                
                # CSAT Change
                prev_csat = pdf['CSAT_Numeric'][pdf['CSAT_Numeric'] > 0].mean()
                csat_delta = avg_csat - prev_csat
                
                g1, g2 = st.columns(2)
                g1.metric("Volume vs Previous Upload", f"{int(total_tickets):,}", delta=f"{int(vol_delta)} tickets", delta_color="inverse")
                g2.metric("CSAT vs Previous Upload", f"{avg_csat:.1f}%", delta=f"{csat_delta:.1f}%")

        # --- CHARTS ---
        st.divider()
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.write("### 🏆 CSAT Ranking")
            fig = px.bar(df.sort_values('CSAT_Numeric'), x='CSAT_Numeric', y=cmap['teammate'], 
                         orientation='h', color='CSAT_Numeric', color_continuous_scale='RdYlGn',
                         template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)
            
        with col_right:
            st.write("### ⚡ Response Time vs Volume")
            fig2 = px.scatter(df, x=cmap['assigned'], y=cmap['frt'], 
                              size=cmap['closed'], hover_name=cmap['teammate'],
                              color='CSAT_Numeric', color_continuous_scale='Viridis',
                              template="plotly_white")
            st.plotly_chart(fig2, use_container_width=True)

        # --- DATA TABLE ---
        with st.expander("🔍 View All Teammate Data"):
            st.dataframe(df[[cmap['teammate'], cmap['assigned'], cmap['closed'], 'CSAT_Numeric', cmap['frt']]])
else:
    st.info("👋 Ready for analysis! Please upload the April CSV export to begin.")
