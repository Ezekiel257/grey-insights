import streamlit as st
import pandas as pd
import plotly.express as px
import io

# --- PAGE CONFIG ---
st.set_page_config(page_title="Grey CS Intelligence", layout="wide", page_icon="📈")

st.title("📊 Grey Customer Success Intelligence")

def process_data(file):
    if file is None: return None
    
    try:
        # 1. Read raw text
        bytes_data = file.getvalue()
        text_data = bytes_data.decode("utf-8").splitlines()
        
        # 2. Find the header row
        header_row_index = None
        for i, line in enumerate(text_data):
            if "Teammate" in line and "Conversations" in line:
                header_row_index = i
                break
        
        if header_row_index is None:
            st.error("Could not find the data table. Please ensure you are uploading an Intercom Teammate Performance CSV.")
            return None

        # 3. Load CSV
        clean_text = "\n".join(text_data[header_row_index:])
        df = pd.read_csv(io.StringIO(clean_text))
        
        # 4. Clean column names
        df.columns = df.columns.str.strip().str.replace('"', '').str.replace("'", "")
        
        # 5. DYNAMIC COLUMN MAPPING
        def find_col(keywords):
            for col in df.columns:
                if any(k.lower() in col.lower() for k in keywords):
                    return col
            return None

        # Map columns or use a dummy name if not found
        t_col = find_col(['Teammate']) or 'Teammate'
        a_col = find_col(['Conversations assigned']) or 'Assigned'
        cl_col = find_col(['Closed conversations']) or 'Closed'
        cs_col = find_col(['CSAT', 'Rating', 'Score']) or 'CSAT'
        fr_col = find_col(['First response', 'FRT']) or 'FRT'

        # 6. FORCE CREATE COLUMNS (This prevents the KeyError)
        if t_col not in df.columns: df[t_col] = "Unknown"
        if a_col not in df.columns: df[a_col] = 0
        if cl_col not in df.columns: df[cl_col] = 0
        if fr_col not in df.columns: df[fr_col] = 0
        
        # 7. CLEAN & FILTER
        # Filter out Summary/Totals
        df = df[df[t_col].notna()]
        df = df[~df[t_col].str.contains('Summary|Total', na=False, case=False)]

        # Numeric Conversion
        for c in [a_col, cl_col, fr_col]:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', '').str.replace('"', ''), errors='coerce').fillna(0)

        # SPECIAL HANDLING FOR CSAT_Numeric
        if cs_col in df.columns:
            df['CSAT_Numeric'] = df[cs_col].astype(str).str.extract(r'(\d+\.?\d*)').astype(float).fillna(0)
        else:
            df['CSAT_Numeric'] = 0.0

        # Create a standardized map to return
        final_map = {
            'teammate': t_col,
            'assigned': a_col,
            'closed': cl_col,
            'frt': fr_col
        }

        return df, final_map

    except Exception as e:
        st.error(f"Error processing file: {e}")
        return None

# --- UI ---
current_file = st.sidebar.file_uploader("Upload Current CSV", type="csv")
previous_file = st.sidebar.file_uploader("Upload Previous CSV", type="csv")

if current_file:
    result = process_data(current_file)
    if result:
        df, cmap = result
        
        # CALCULATIONS (With safeties)
        total_assigned = df[cmap['assigned']].sum()
        avg_csat = df['CSAT_Numeric'][df['CSAT_Numeric'] > 0].mean() if not df[df['CSAT_Numeric'] > 0].empty else 0
        med_frt = df[cmap['frt']].median()

        # METRICS
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Tickets", f"{int(total_assigned):,}")
        m2.metric("Avg Team CSAT", f"{avg_csat:.1f}%")
        m3.metric("Median Response", f"{int(med_frt)}s")
        m4.metric("Teammates", len(df))

        # GAP ANALYSIS
        if previous_file:
            p_result = process_data(previous_file)
            if p_result:
                pdf, pcmap = p_result
                st.subheader("📉 Gap Analysis")
                
                p_total = pdf[pcmap['assigned']].sum()
                v_delta = total_assigned - p_total
                
                p_csat = pdf['CSAT_Numeric'][pdf['CSAT_Numeric'] > 0].mean() if not pdf[pdf['CSAT_Numeric'] > 0].empty else 0
                c_delta = avg_csat - p_csat
                
                g1, g2 = st.columns(2)
                g1.metric("Volume Change", f"{int(total_assigned):,}", delta=f"{int(v_delta)} tickets", delta_color="inverse")
                g2.metric("CSAT Change", f"{avg_csat:.1f}%", delta=f"{c_delta:.1f}%")

        # CHARTS
        st.divider()
        l, r = st.columns(2)
        with l:
            st.write("### CSAT by Teammate")
            fig = px.bar(df.sort_values('CSAT_Numeric'), x='CSAT_Numeric', y=cmap['teammate'], orientation='h', color='CSAT_Numeric', color_continuous_scale='RdYlGn')
            st.plotly_chart(fig, use_container_width=True)
        with r:
            st.write("### Workload vs Speed")
            fig2 = px.scatter(df, x=cmap['assigned'], y=cmap['frt'], size=cmap['closed'], hover_name=cmap['teammate'], color='CSAT_Numeric')
            st.plotly_chart(fig2, use_container_width=True)

        with st.expander("Raw Data Table"):
            st.dataframe(df)
