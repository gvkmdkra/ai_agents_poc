import logging
import streamlit as st

from ui.sidebar import render_sidebar
from chat import render_chat_history, handle_user_query
from campaigns.sms import render_sms_campaign
from campaigns.email import render_email_campaign
from campaigns.calls import render_call_campaign
from ui.monitor import render_monitor

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Note: Secrets are loaded via core.secrets which handles both Streamlit secrets and .env

# ---------------------- CONFIG --------------------------
st.set_page_config(
    page_title="ChurnGuard AI Agent", 
    page_icon="🛡️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------- CUSTOM CSS --------------------------
def load_custom_css():
    st.markdown("""
    <style>
        /* Databricks-Inspired Color Scheme - Red/Orange Theme */
        :root {
            --primary-gradient: linear-gradient(135deg, #FF3621 0%, #FF6B35 100%);
            --primary-color: #FF3621;
            --secondary-color: #FF6B35;
            --accent-color: #FF8C42;
            --dark-bg: #1C1C1C;
            --background-light: #F7F7F7;
            --background-white: #FFFFFF;
            --text-primary: #1A1A1A;
            --text-secondary: #6B6B6B;
            --text-muted: #999999;
            --border-color: #E0E0E0;
            --success-color: #00A972;
            --warning-color: #FF9500;
            --error-color: #FF3621;
            --shadow-sm: 0 1px 3px rgba(0,0,0,0.1);
            --shadow-md: 0 4px 8px rgba(0,0,0,0.12);
            --shadow-lg: 0 10px 20px rgba(0,0,0,0.15);
        }
        
        /* Global Resets & Base Styles */
        * {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', sans-serif;
        }
        
        /* Hide default streamlit elements */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Main container styling */
        .main {
            background-color: var(--background-light);
        }
        
        .main .block-container {
            padding: 2rem 3rem 3rem 3rem;
            max-width: 100%;
        }
        
        /* Header styling - Databricks Style */
        .main-header {
            background: linear-gradient(135deg, #FF3621 0%, #FF6B35 100%);
            padding: 2.5rem 2.5rem;
            border-radius: 16px;
            margin-bottom: 2.5rem;
            box-shadow: var(--shadow-lg), 0 0 40px rgba(255, 54, 33, 0.3);
            position: relative;
            overflow: hidden;
        }
        
        .main-header::before {
            content: '';
            position: absolute;
            top: 0;
            right: 0;
            width: 300px;
            height: 300px;
            background: radial-gradient(circle, rgba(255,255,255,0.15) 0%, transparent 70%);
            border-radius: 50%;
            transform: translate(30%, -30%);
        }
        
        .main-header h1 {
            color: white !important;
            font-weight: 800 !important;
            font-size: 2.5rem !important;
            margin: 0 !important;
            letter-spacing: -0.5px;
        }
        
        .main-header p {
            color: rgba(255,255,255,0.95) !important;
            font-size: 1.05rem !important;
            margin: 0 !important;
            font-weight: 400;
        }
        
        /* Metric cards - Professional Design */
        [data-testid="stMetric"] {
            background: white;
            padding: 1.5rem;
            border-radius: 12px;
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--border-color);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        [data-testid="stMetric"]:hover {
            box-shadow: var(--shadow-md);
            transform: translateY(-2px);
            border-color: rgba(255, 54, 33, 0.5);
        }
        
        [data-testid="stMetricValue"] {
            font-size: 2.25rem !important;
            font-weight: 700 !important;
            color: var(--text-primary) !important;
            line-height: 1 !important;
        }
        
        [data-testid="stMetricLabel"] {
            font-size: 0.875rem !important;
            font-weight: 600 !important;
            color: var(--text-secondary) !important;
            text-transform: uppercase !important;
            letter-spacing: 0.05em !important;
            margin-bottom: 0.5rem !important;
        }
        
        [data-testid="stMetricDelta"] {
            font-size: 0.875rem !important;
            font-weight: 500 !important;
        }
        
        /* Custom card styling */
        .metric-card {
            background: white;
            padding: 2rem;
            border-radius: 16px;
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--border-color);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            height: 100%;
        }
        
        .metric-card:hover {
            box-shadow: var(--shadow-md);
            transform: translateY(-3px);
            border-color: rgba(255, 54, 33, 0.3);
        }
        
        .metric-card h3 {
            color: var(--text-primary);
            font-size: 1.25rem;
            font-weight: 700;
            margin-bottom: 0.75rem;
        }
        
        .metric-card p {
            color: var(--text-secondary);
            font-size: 0.95rem;
            line-height: 1.6;
        }
        
        /* Tabs styling - Modern Design */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            background-color: white;
            padding: 0.75rem;
            border-radius: 12px;
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--border-color);
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 54px;
            background-color: transparent;
            border-radius: 10px;
            color: var(--text-secondary);
            font-weight: 600;
            font-size: 0.95rem;
            padding: 0 2rem;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            border: 2px solid transparent;
        }
        
        .stTabs [data-baseweb="tab"]:hover {
            background-color: rgba(255, 54, 33, 0.08);
            color: var(--primary-color);
        }
        
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #FF3621 0%, #FF6B35 100%) !important;
            color: white !important;
            box-shadow: 0 4px 12px rgba(255, 54, 33, 0.4);
            border-color: transparent;
        }
        
        /* Buttons - Enhanced Design */
        .stButton > button {
            border-radius: 10px;
            font-weight: 600;
            font-size: 0.95rem;
            padding: 0.65rem 2rem;
            border: 2px solid transparent;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: var(--shadow-sm);
            letter-spacing: 0.025em;
        }
        
        .stButton > button:hover {
            box-shadow: var(--shadow-md);
            transform: translateY(-2px);
        }
        
        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #FF3621 0%, #FF6B35 100%);
            color: white;
            border: none;
        }
        
        .stButton > button[kind="primary"]:hover {
            box-shadow: 0 6px 16px rgba(255, 54, 33, 0.4);
            transform: translateY(-2px);
        }
        
        .stButton > button[kind="secondary"] {
            background: white;
            color: var(--primary-color);
            border-color: var(--border-color);
        }
        
        .stButton > button[kind="secondary"]:hover {
            border-color: var(--primary-color);
            background: rgba(255, 54, 33, 0.05);
        }
        
        /* Input fields - Modern Design */
        .stTextInput > div > div > input,
        .stTextArea textarea {
            border-radius: 10px;
            border: 2px solid var(--border-color);
            padding: 0.75rem 1rem;
            font-size: 0.95rem;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            background: white;
        }
        
        .stTextInput > div > div > input:focus,
        .stTextArea textarea:focus {
            border-color: var(--primary-color);
            box-shadow: 0 0 0 4px rgba(255, 54, 33, 0.1);
            outline: none;
        }
        
        /* Sidebar styling - Databricks Dark Theme */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #1C1C1C 0%, #2A2A2A 100%);
            box-shadow: 4px 0 24px rgba(0,0,0,0.2);
        }
        
        [data-testid="stSidebar"] > div:first-child {
            padding: 1.5rem 1.5rem 2rem 1.5rem;
        }
        
        [data-testid="stSidebar"] h1, 
        [data-testid="stSidebar"] h2, 
        [data-testid="stSidebar"] h3 {
            color: white !important;
        }
        
        [data-testid="stSidebar"] h3 {
            font-size: 1.1rem !important;
            font-weight: 700 !important;
            margin-bottom: 1rem !important;
        }
        
        [data-testid="stSidebar"] p, 
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] .stMarkdown {
            color: rgba(255,255,255,0.9) !important;
        }
        
        [data-testid="stSidebar"] hr {
            border-color: rgba(255,255,255,0.15) !important;
            margin: 1.5rem 0 !important;
        }
        
        /* Dataframe styling - Clean and Modern */
        [data-testid="stDataFrame"] {
            border-radius: 12px;
            overflow: hidden;
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--border-color);
        }
        
        [data-testid="stDataFrame"] > div {
            border-radius: 12px;
        }
        
        /* Chat input - Professional styling */
        .stChatInput > div {
            border-radius: 12px;
            border: 2px solid var(--border-color);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        .stChatInput > div:focus-within {
            border-color: var(--primary-color);
            box-shadow: 0 0 0 4px rgba(255, 54, 33, 0.1);
        }
        
        /* Chat messages styling */
        [data-testid="stChatMessage"] {
            border-radius: 12px;
            padding: 1rem 1.5rem;
            margin-bottom: 1rem;
            box-shadow: var(--shadow-sm);
        }
        
        [data-testid="stChatMessage"][data-testid*="user"] {
            background: linear-gradient(135deg, rgba(255, 54, 33, 0.08) 0%, rgba(255, 107, 53, 0.08) 100%);
        }
        
        [data-testid="stChatMessage"][data-testid*="assistant"] {
            background: white;
            border: 1px solid var(--border-color);
        }
        
        /* Expander styling - Enhanced */
        .streamlit-expanderHeader {
            background-color: white;
            border: 1px solid var(--border-color);
            border-radius: 10px;
            font-weight: 600;
            padding: 1rem 1.5rem;
            transition: all 0.3s ease;
        }
        
        .streamlit-expanderHeader:hover {
            background-color: rgba(255, 54, 33, 0.05);
            border-color: var(--primary-color);
        }
        
        /* Info/Warning/Error boxes - Professional */
        .stAlert {
            border-radius: 12px;
            border-left: 4px solid;
            padding: 1.25rem 1.5rem;
            font-weight: 500;
            box-shadow: var(--shadow-sm);
        }
        
        /* Radio buttons - Modern */
        .stRadio > div {
            background-color: white;
            padding: 1.25rem;
            border-radius: 12px;
            border: 1px solid var(--border-color);
            box-shadow: var(--shadow-sm);
        }
        
        /* Selectbox - Enhanced */
        .stSelectbox > div > div {
            border-radius: 10px;
            border: 2px solid var(--border-color);
            transition: all 0.3s ease;
        }
        
        .stSelectbox > div > div:focus-within {
            border-color: var(--primary-color);
            box-shadow: 0 0 0 4px rgba(255, 54, 33, 0.1);
        }
        
        /* File uploader - Sidebar specific */
        [data-testid="stSidebar"] [data-testid="stFileUploader"] {
            background-color: rgba(255,255,255,0.08);
            border-radius: 12px;
            padding: 1.5rem;
            border: 2px dashed rgba(255,255,255,0.3);
            transition: all 0.3s ease;
        }
        
        [data-testid="stSidebar"] [data-testid="stFileUploader"]:hover {
            border-color: rgba(255, 54, 33, 0.6);
            background-color: rgba(255,255,255,0.12);
        }
        
        /* Progress bars - Databricks Gradient */
        .stProgress > div > div > div {
            background: linear-gradient(90deg, #FF3621 0%, #FF6B35 100%);
            border-radius: 10px;
        }
        
        /* Download button */
        .stDownloadButton > button {
            background: var(--success-color);
            color: white;
            border: none;
        }
        
        .stDownloadButton > button:hover {
            background: #38a169;
            box-shadow: 0 4px 12px rgba(72, 187, 120, 0.4);
        }
        
        /* Dividers - Subtle */
        hr {
            margin: 2.5rem 0;
            border: none;
            height: 1px;
            background: linear-gradient(90deg, transparent 0%, var(--border-color) 50%, transparent 100%);
        }
        
        /* Section headers */
        h3 {
            color: var(--text-primary);
            font-weight: 700;
            font-size: 1.5rem;
            margin-bottom: 1rem;
        }
        
        h4 {
            color: var(--text-primary);
            font-weight: 700;
            font-size: 1.25rem;
        }
        
        h5 {
            color: var(--text-secondary);
            font-weight: 600;
            font-size: 1rem;
        }
        
        /* Improved spacing */
        .element-container {
            margin-bottom: 0.5rem;
        }
        
        /* Floating Chat Button - Professional Design */
        .floating-chat-btn {
            width: 64px;
            height: 64px;
            border-radius: 50%;
            background: linear-gradient(135deg, #FF3621 0%, #FF6B35 100%);
            color: white;
            border: none;
            box-shadow: 0 6px 20px rgba(255, 54, 33, 0.4);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.8rem;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            animation: pulse-chat 2s infinite;
            position: relative;
        }
        
        @keyframes pulse-chat {
            0%, 100% {
                box-shadow: 0 6px 20px rgba(255, 54, 33, 0.4);
                transform: scale(1);
            }
            50% {
                box-shadow: 0 8px 30px rgba(255, 54, 33, 0.6);
                transform: scale(1.02);
            }
        }
        
        .floating-chat-btn:hover {
            transform: scale(1.1) rotate(5deg) !important;
            box-shadow: 0 10px 35px rgba(255, 54, 33, 0.7) !important;
            animation: none;
        }
        
        .floating-chat-btn::after {
            content: '';
            position: absolute;
            width: 14px;
            height: 14px;
            background: #00D9FF;
            border-radius: 50%;
            top: 6px;
            right: 6px;
            border: 3px solid white;
            animation: blink 1.5s infinite;
        }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        
        /* File uploader styling - Main upload */
        [data-testid="stFileUploader"] {
            background-color: white;
            border-radius: 16px;
            padding: 2rem;
            border: 3px dashed var(--border-color);
            transition: all 0.3s ease;
        }
        
        [data-testid="stFileUploader"]:hover {
            border-color: var(--primary-color);
            background-color: rgba(255, 54, 33, 0.02);
        }
    </style>
    """, unsafe_allow_html=True)

load_custom_css()


def render_campaigns():
    """Render campaign sections in main page"""
    # Check if data and model are available
    if "df" not in st.session_state or "model" not in st.session_state:
        st.error("⚠️ Data or model not available. Please upload data and configure API.")
        return
    
    st.markdown("### 🚀 Campaign Management")
    st.markdown("Create and launch targeted retention campaigns across multiple channels")
    
    st.markdown("<br>", unsafe_allow_html=True)

    df = st.session_state.df
    model = st.session_state.model

    # Modern campaign type selector
    st.markdown("#### Select Campaign Channel")
    campaign_type = st.radio(
        "Campaign Type",
        ["📱 SMS Campaign", "📧 Email Campaign", "📞 Call Campaign"],
        horizontal=True,
        key="campaign_type",
        label_visibility="collapsed"
    )
    
    st.markdown("<br>", unsafe_allow_html=True)

    if campaign_type == "📱 SMS Campaign":
        render_sms_campaign(df, model)
    elif campaign_type == "📧 Email Campaign":
        render_email_campaign(df, model)
    elif campaign_type == "📞 Call Campaign":
        render_call_campaign(df, model)


# ---------------------- MAIN APP --------------------------
def main():
    # Professional header with logo and branding
    st.markdown("""
    <div class="main-header">
        <div style="display: flex; align-items: center; gap: 1.5rem;">
            <div style="font-size: 3.5rem;">🛡️</div>
            <div>
                <h1 style="margin: 0; line-height: 1.2;">ChurnGuard AI</h1>
                <p style="margin: 0; opacity: 0.95; font-size: 1rem;">Intelligent Customer Retention Platform</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    model = render_sidebar()
    
    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "show_chat" not in st.session_state:
        st.session_state.show_chat = False
    
    # Check API and data status
    has_api = model is not None
    has_data = "df" in st.session_state and st.session_state.df is not None
    df = st.session_state.df if has_data else None
    
    # Modern metrics dashboard - Always visible
    st.markdown("### 📈 Dashboard Overview")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if has_data:
            st.metric("Total Records", f"{len(df):,}", delta="Active")
        else:
            st.metric("Total Records", "—", delta="No Data" if has_api else "Setup Required", delta_color="off")
    with col2:
        if has_data:
            st.metric("Data Columns", len(df.columns), delta="Features")
        else:
            st.metric("Data Columns", "—", delta="Awaiting Data", delta_color="off")
    with col3:
        campaigns = len(st.session_state.get("campaign_logs", []))
        st.metric("Campaigns Launched", campaigns if campaigns > 0 else "—", delta=f"+{campaigns}" if campaigns > 0 else "Ready")
    with col4:
        if "campaign_logs" in st.session_state and st.session_state.campaign_logs:
            total_sent = sum(log["sent"] for log in st.session_state.campaign_logs)
            st.metric("Messages Delivered", f"{total_sent:,}", delta="Success")
        else:
            st.metric("Messages Delivered", "—", delta="Pending", delta_color="off")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Status banner if needed
    if not has_api:
        st.warning("⚠️ **API Configuration Required** — Please configure your API key in the sidebar to enable AI features")
    elif not has_data:
        st.info("📂 **Upload Data to Begin** — Upload your CSV file from the sidebar to start analyzing and launching campaigns")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Main tabs - ALWAYS visible regardless of API or data status
    tab1, tab2, tab3, tab4 = st.tabs(["📂 Data", "🚀 Campaigns", "📊 Analytics & Monitor", "⚙️ Settings"])

    with tab1:
        # Data Upload and Management tab
        st.markdown("### 📂 Data Management")
        st.markdown("Upload and manage your customer churn data")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if not has_api:
            st.error("🔑 **API Configuration Required**")
            st.info("Please configure your Gemini API key in the sidebar to enable all features")
        
        # Large, prominent upload section
        st.markdown("#### Upload Your Dataset")
        
        uploaded_file = st.file_uploader(
            "Choose a CSV file",
            type=["csv"],
            help="Upload your customer churn data in CSV format (max 200MB)",
            key="main_upload"
        )
        
        if uploaded_file and has_api:
            with st.spinner("🔄 Processing your data..."):
                from ui.sidebar import preprocess_csv, extract_table_name_from_filename
                df_new = preprocess_csv(uploaded_file)
                st.session_state.df = df_new
                st.session_state.model = model
                
                st.success(f"✅ Successfully loaded {len(df_new):,} rows with {len(df_new.columns)} columns")
                
                # Handle Turso sync
                try:
                    filename = getattr(uploaded_file, 'name', '') or ''
                except Exception:
                    filename = ''
                source_sig = f"{filename}:{len(df_new)}:{','.join(list(df_new.columns))}"
                
                new_source = st.session_state.get("turso_source_sig") != source_sig
                if new_source:
                    table_name = extract_table_name_from_filename(filename)
                    st.session_state.turso_table = table_name
                    st.session_state.turso_source_sig = source_sig
                    st.session_state.turso_synced = False
                
                # Show preview
                st.markdown("#### 📊 Data Preview")
                st.dataframe(df_new.head(20), use_container_width=True)
                
                # Show column info
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Rows", f"{len(df_new):,}")
                with col2:
                    st.metric("Total Columns", len(df_new.columns))
                with col3:
                    st.metric("Memory", f"{df_new.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
                
                st.rerun()
        
        elif has_data:
            # Show current dataset info
            st.success("✅ Dataset Currently Loaded")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Rows", f"{len(df):,}")
            with col2:
                st.metric("Columns", len(df.columns))
            with col3:
                st.metric("Memory", f"{df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
            with col4:
                st.metric("Table", st.session_state.get('turso_table', 'N/A'))
            
            st.markdown("#### 📊 Data Preview")
            st.dataframe(df.head(20), use_container_width=True)
            
            # Column information
            with st.expander("📋 Column Details"):
                col_info = []
                for col in df.columns:
                    col_info.append({
                        "Column": col,
                        "Type": str(df[col].dtype),
                        "Non-Null": df[col].count(),
                        "Null": df[col].isna().sum(),
                        "Unique": df[col].nunique()
                    })
                st.dataframe(col_info, use_container_width=True)
            
            # Option to upload new data
            if st.button("🔄 Upload New Dataset", use_container_width=True):
                st.session_state.df = None
                st.rerun()
        else:
            # Empty state with instructions
            st.markdown("""
            <div class="metric-card" style="margin-top: 2rem;">
                <h3>📤 Ready to Upload</h3>
                <p><strong>Upload your customer churn data to get started.</strong></p>
                <p>Your CSV file should include columns such as:</p>
                <ul>
                    <li><strong>Customer Information:</strong> Name, Email, Age, Location</li>
                    <li><strong>Subscription Data:</strong> Type, Duration, Charges</li>
                    <li><strong>Engagement Metrics:</strong> Login frequency, Support tickets</li>
                    <li><strong>Churn Indicator:</strong> Yes/No or 1/0</li>
                </ul>
                <p style="color: #FF3621; font-weight: 600;">Maximum file size: 200MB</p>
            </div>
            """, unsafe_allow_html=True)

    with tab2:
        # Campaigns tab
        st.markdown("### 🚀 Campaign Management")
        
        if not has_api:
            st.error("🔑 **API Key Required** — Configure API in sidebar to enable campaign features")
        elif not has_data:
            st.info("📂 **Upload Data Required** — Upload CSV to launch targeted campaigns")
        
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            <div class="metric-card">
                <h3>📱 SMS Campaigns</h3>
                <p>Send personalized SMS messages to targeted customer segments with high churn probability</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class="metric-card">
                <h3>📧 Email Campaigns</h3>
                <p>Deliver retention emails with special offers and personalized content to at-risk customers</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div class="metric-card">
                <h3>📞 Voice Campaigns</h3>
                <p>Automated voice calls to remind customers about special offers and loyalty benefits</p>
            </div>
            """, unsafe_allow_html=True)
        
        if has_api and has_data:
            st.markdown("<br>", unsafe_allow_html=True)
        render_campaigns()

    with tab3:
        # Monitor tab - always accessible
        render_monitor()
    
    with tab4:
        # Settings tab
        st.markdown("### ⚙️ System Configuration")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 📊 Dataset Information")
            if has_data:
                st.write(f"**Rows:** {len(df):,}")
                st.write(f"**Columns:** {len(df.columns)}")
                st.write(f"**Memory Usage:** {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
                st.write(f"**Table:** `{st.session_state.get('turso_table', 'N/A')}`")
            else:
                st.write("**Status:** ⚠️ No data loaded")
                st.write("**Action:** Upload CSV from sidebar")
        
        with col2:
            st.markdown("#### 🔧 System Status")
            st.write(f"**AI Model:** Gemini 2.5 Flash")
            if has_api:
                st.write(f"**API Status:** ✅ Connected")
            else:
                st.write(f"**API Status:** ❌ Not Configured")
            st.write(f"**Chat Messages:** {len(st.session_state.get('messages', []))}")
            st.write(f"**Campaign Logs:** {len(st.session_state.get('campaign_logs', []))}")
        
        st.divider()
        
        st.markdown("#### 🗑️ Data Management")
        col1, col2 = st.columns(2)
        with col1:
            if st.session_state.get('messages'):
                if st.button("Clear Chat History", use_container_width=True):
                    st.session_state.messages = []
                    st.success("✅ Chat history cleared")
                    st.rerun()
            else:
                st.button("Clear Chat History", disabled=True, use_container_width=True)
        with col2:
            if st.session_state.get('campaign_logs'):
                if st.button("Clear Campaign Logs", use_container_width=True):
                    st.session_state.campaign_logs = []
                    st.success("✅ Campaign logs cleared")
                    st.rerun()
            else:
                st.button("Clear Campaign Logs", disabled=True, use_container_width=True)
    
    # Floating Chat Button at bottom right
    if "show_chat_modal" not in st.session_state:
        st.session_state.show_chat_modal = False
    
    # Chat modal
    if st.session_state.show_chat_modal:
        st.markdown("---")
        st.markdown("### 💬 AI Chat Assistant")
        st.markdown("Ask questions about your data in natural language")
        
        if has_data and has_api:
            render_chat_history()
            if prompt := st.chat_input("Ask about your data...", key="floating_chat_input"):
                handle_user_query(prompt, model)
            
            if st.button("✖ Close Chat", key="close_floating_chat"):
                st.session_state.show_chat_modal = False
                st.rerun()
        elif not has_data:
            st.info("📂 Upload data in the Data tab to start chatting with AI")
        elif not has_api:
            st.error("🔑 Configure API key in sidebar to enable chat")
    
    # Floating button HTML and trigger
    st.markdown("""
    <div style="position: fixed; bottom: 2rem; right: 2rem; z-index: 9999;">
        <div class="floating-chat-btn" title="AI Chat Assistant">
            💬
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Invisible button to trigger chat (positioned over the floating button area)
    col_spacer1, col_spacer2, col_button = st.columns([20, 1, 1])
    with col_button:
        if st.button("🤖", key="trigger_chat_modal", help="Open AI Chat"):
            st.session_state.show_chat_modal = not st.session_state.show_chat_modal
            st.rerun()


if __name__ == "__main__":
    main()
