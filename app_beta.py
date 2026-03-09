import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import datetime
import io

# 1. Initialize Connection & Page Config
st.set_page_config(page_title="B&G ERP BETA", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)

# --- CORRECTED CSS FOR ROUND PILL BUTTONS ---
st.markdown("""
    <style>
    /* Main Hub Selection Buttons */
    div.stButton > button {
        border-radius: 50px;
        padding-left: 30px;
        padding-right: 30px;
        border: 2px solid #e0e0e0;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    div.stButton > button:hover {
        border-color: #007bff;
        color: #007bff;
        background-color: #f0f7ff;
    }
    </style>
""", unsafe_allow_html=True) # FIXED: Changed unsafe_allow_index to unsafe_allow_html

if 'hub' not in st.session_state:
    st.session_state.hub = "Machining Hub"

# --- ROUND BUTTON BAR SELECTION ---
st.write("### 🏢 Department Selection")
c1, c2, _ = st.columns([1, 1, 2])
with c1:
    if st.button("⚙️ MACHINING", use_container_width=True, type="primary" if st.session_state.hub == "Machining Hub" else "secondary"):
        st.session_state.hub = "Machining Hub"
        st.rerun()
with c2:
    if st.button("✨ BUFFING", use_container_width=True, type="primary" if st.session_state.hub == "Buffing Hub" else "secondary"):
        st.session_state.hub = "Buffing Hub"
        st.rerun()

st.divider()
st.title(f"📍 {st.session_state.hub} Dashboard")

# --- DYNAMIC CONFIGURATION ---
if st.session_state.hub == "Machining Hub":
    DB_TABLE, MASTER_TABLE, MASTER_COL, RES_LABEL = "beta_machining_logs", "beta_machine_master", "machine_name", "Machine"
    ACTIVITIES = ["Turning", "Drilling", "Milling", "Keyway", "Dishbending"]
else:
    DB_TABLE, MASTER_TABLE, MASTER_COL, RES_LABEL = "beta_buffing_logs", "beta_buffing_station_master", "station_name", "Buffing Station"
    ACTIVITIES = ["Rough Buffing", "Mirror Polishing", "Satin Finish", "RA Value Check"]

# 2. Data Fetching
def get_master_data():
    try:
        res = conn.table(MASTER_TABLE).select(MASTER_COL).execute().data or []
        ops = conn.table("beta_operator_master").select("operator_name").execute().data or []
        vnds = conn.table("beta_vendor_master").select("vendor_name").execute().data or []
        vhs = conn.table("beta_vehicle_master").select("vehicle_number").execute().data or []
        return ([r[MASTER_COL] for r in res], [o['operator_name'] for o in ops], 
                [v['vendor_name'] for v in vnds], [vh['vehicle_number'] for vh in vhs])
    except: return ([], [], [], [])

resource_list, operator_list, vendor_list, vehicle_list = get_master_data()

all_logs_query = conn.table(DB_TABLE).select("*").order("created_at", desc=True).execute()
all_data = all_logs_query.data or []

tab_prod, tab_incharge, tab_analytics, tab_log, tab_masters = st.tabs([
    "📝 Request & Live", "👨‍💻 Incharge Desk", "📊 Executive Analytics", "📋 Full Logbook", "🛠️ Masters"
])

# --- TAB 1: PRODUCTION & LIVE STATUS ---
with tab_prod:
    with st.form("prod_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        u_no, j_code = c1.selectbox("Unit No", [1, 2, 3]), c1.text_input("Job Code")
        part, act = c2.text_input("Part Name"), c2.selectbox("Process", ACTIVITIES)
        req_date, prio = c3.date_input("Required Date"), c3.selectbox("Priority", ["Low", "Medium", "High", "URGENT"])
        notes = st.text_area("🗒️ Special Production Notes")
        if st.form_submit_button("Submit Request"):
            if j_code and part:
                conn.table(DB_TABLE).insert({
                    "unit_no": u_no, "job_code": j_code, "part_name": part, 
                    "activity_type": act, "required_date": str(req_date), 
                    "request_date": str(datetime.date.today()), 
                    "priority": prio, "status": "Pending", "special_notes": notes
                }).execute()
                st.rerun()

    st.subheader("🚦 Live Shop Floor Status")
    if all_data:
        df_status = pd.DataFrame(all_data)
        # Robust Date Handling to prevent TypeErrors
        df_status['required_date'] = pd.to_datetime(df_status['required_date'], errors='coerce')
        today = pd.Timestamp(datetime.date.today())
        df_status['Days Left'] = (df_status['required_date'] - today).dt.days
        
        unit_sel = st.radio("View Unit", [1, 2, 3], horizontal=True)
        unit_view = df_status[df_status['unit_no'] == unit_sel].copy()
        
        disp_cols = ['job_code', 'part_name', 'status', 'priority', 'request_date', 'required_date', 'Days Left', 'special_notes']
        st.dataframe(unit_view[disp_cols], use_container_width=True, hide_index=True)
