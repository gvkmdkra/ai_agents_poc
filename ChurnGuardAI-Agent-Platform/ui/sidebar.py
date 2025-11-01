import os
import re
import streamlit as st
import pandas as pd
import google.generativeai as genai
from core.secrets import get_secret, validate_secrets


def extract_table_name_from_filename(filename: str) -> str:
    """
    Extract table name from filename by removing date stamps.
    
    Examples:
    - {org1}_churn_data_src_2025_11_01.csv -> org1_churn_data_src_tbl
    - {org1}_churn_data_src_2025_11_02.csv -> org1_churn_data_src_tbl
    - {org2}_churn_data_src_2025_11_01.csv -> org2_churn_data_src_tbl
    
    Pattern: Remove date patterns (_YYYY_MM_DD or _YYYYMMDD) and add _tbl suffix
    """
    if not filename:
        return "uploaded_data_tbl"
    
    # Remove file extension
    base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
    
    # Remove date patterns at the end:
    # Pattern 1: _YYYY_MM_DD (e.g., _2025_11_01)
    # Pattern 2: _YYYYMMDD (e.g., _20251101)
    # Pattern 3: _YYYY-MM-DD (e.g., _2025-11-01)
    # Match dates that look like years (1900-2100)
    date_patterns = [
        r'_\d{4}_\d{2}_\d{2}$',  # _YYYY_MM_DD
        r'_\d{4}-\d{2}-\d{2}$',  # _YYYY-MM-DD
        r'_\d{8}$',                # _YYYYMMDD
    ]
    
    for pattern in date_patterns:
        base_name = re.sub(pattern, '', base_name)
    
    # Sanitize: remove curly braces first, then keep only alphanumeric and underscores
    base_name = base_name.replace('{', '').replace('}', '')
    table_name = re.sub(r"[^A-Za-z0-9_]+", "_", base_name)
    # Collapse multiple underscores into single underscore
    table_name = re.sub(r"_+", "_", table_name)
    # Remove leading/trailing underscores
    table_name = table_name.strip('_')
    
    # Add _tbl suffix if not present
    if not table_name.endswith('_tbl'):
        table_name = f"{table_name}_tbl"
    
    # Ensure it's not empty
    if not table_name or table_name == '_tbl':
        return "uploaded_data_tbl"
    
    return table_name


@st.cache_data
def preprocess_csv(uploaded_file) -> pd.DataFrame:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip()

    # Try numeric conversion safely without deprecated errors="ignore"
    for col in df.columns:
        if df[col].dtype == "object":
            try:
                df[col] = pd.to_numeric(df[col])
            except Exception:
                # keep as object if conversion fails
                pass

    # Fill missing numeric values without chained assignment
    for col in df.select_dtypes(include=["number"]).columns:
        if df[col].isna().any():
            df[col] = df[col].fillna(df[col].median())

    # Fill missing object values without chained assignment
    for col in df.select_dtypes(include=["object"]).columns:
        if df[col].isna().any():
            df[col] = df[col].fillna("")

    return df


def render_sidebar():
    with st.sidebar:
        # Professional sidebar header with Databricks-style logo
        st.markdown("""
        <div style="text-align: center; padding: 1.5rem 0 1rem 0;">
            <div style="
                width: 85px; 
                height: 85px; 
                margin: 0 auto 1rem auto;
                background: linear-gradient(135deg, #FF3621 0%, #FF6B35 100%);
                border-radius: 20px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 2.8rem;
                box-shadow: 0 8px 20px rgba(255, 54, 33, 0.4);
            ">
                🛡️
            </div>
            <h2 style="color: white; margin: 0; font-weight: 700; font-size: 1.5rem;">ChurnGuard AI</h2>
            <p style="color: rgba(255,255,255,0.75); font-size: 0.85rem; margin: 0.3rem 0 0 0; letter-spacing: 0.5px;">RETENTION PLATFORM</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # API Configuration Section
        st.markdown("### ⚙️ Configuration")
        
        api_key = get_secret("GEMINI_API_KEY")
        if not api_key:
            st.error("❌ API Key Missing")
            st.info("💡 Configure your API key below")
            with st.expander("📋 Setup Instructions", expanded=True):
                st.markdown("""
                **Streamlit Cloud:**
                1. Go to app settings
                2. Open "Secrets" section
                3. Add `GEMINI_API_KEY` with your key
                
                **Local Development:**
                - Add to `.env` file or `.streamlit/secrets.toml`
                """)
            return None
        
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.5-flash")
            st.success("✅ API Connected")
            st.caption("Model: Gemini 2.5 Flash")
        except Exception as e:
            st.error(f"❌ Connection Failed")
            st.caption(f"Error: {str(e)[:50]}...")
            return None

        st.markdown("---")
        
        # Data Status Section
        st.markdown("### 📊 Data Status")
        
        if "df" in st.session_state and st.session_state.df is not None:
            df = st.session_state.df
            
            # Display upload success with metrics
            st.success("✅ Dataset Loaded")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Rows", f"{len(df):,}", delta=None, delta_color="off")
            with col2:
                st.metric("Cols", len(df.columns), delta=None, delta_color="off")
            
            st.caption(f"📦 Table: `{st.session_state.get('turso_table', 'N/A')}`")
            
            if st.session_state.get("turso_synced"):
                st.caption("✅ Synced to database")
            else:
                st.caption("⏳ Syncing...")
        else:
            st.info("📂 No data loaded")
            st.caption("Upload CSV in the Data tab")

        st.markdown("---")
        
        # Actions Section
        st.markdown("### 🔧 Quick Actions")
        if "messages" in st.session_state and st.session_state.messages:
            if st.button("🗑️ Clear Chat History", use_container_width=True):
                st.session_state.messages = []
                st.rerun()
        
        if "campaign_logs" in st.session_state and st.session_state.campaign_logs:
            st.caption(f"📊 {len(st.session_state.campaign_logs)} campaigns logged")
        
        return st.session_state.get("model", None)