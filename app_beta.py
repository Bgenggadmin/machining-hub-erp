import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd

# 1. Page Configuration
st.set_page_config(page_title="B&G Integrated Hub", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)

# 2. Session State Initialization (To remember which Hub is selected)
if 'current_hub' not in st.session_state:
    st.session_state.current_hub = "Machining Hub"

# --- DEPARTMENT SELECTION BUTTONS (Main Page) ---
st.write("### 🏢 Select Department")
col_m, col_b = st.columns(2)

if col_m.button("⚙️ MACHINING HUB", use_container_width=True, 
                type="primary" if st.session_state.current_hub == "Machining Hub" else "secondary"):
    st.session_state.current_hub = "Machining Hub"
    st.rerun()

if col_b.button("✨ BUFFING & POLISHING", use_container_width=True, 
                type="primary" if st.session_state.current_hub == "Buffing & Polishing" else "secondary"):
    st.session_state.current_hub = "Buffing & Polishing"
    st.rerun()

st.divider()

# 3. Dynamic Logic based on Button Selection
hub_mode = st.session_state.current_hub

if hub_mode == "Machining Hub":
    DB_TABLE = "beta_machining_logs"
    RES_MASTER = "beta_machine_master"
    RES_LABEL = "Machine"
    RES_COL = "machine_name"
    ACTIVITY_OPTS = ["Turning", "Drilling", "Milling", "Keyway", "Dishbending"]
else:
    DB_TABLE = "beta_buffing_logs"
    RES_MASTER = "beta_buffing_station_master"
    RES_LABEL = "Buffing Station"
    RES_COL = "station_name"
    ACTIVITY_OPTS = ["Rough Buffing", "Mirror Polishing", "Satin Finish", "RA Value Check", "Cleaning"]

st.title(f"{hub_mode} - Sandbox")

# 4. Fetch Master Data
def get_masters():
    try:
        res = conn.table(RES_MASTER).select(RES_COL).execute().data or []
        ops = conn.table("beta_operator_master").select("operator_name").execute().data or []
        vends = conn.table("beta_vendor_master").select("vendor_name").execute().data or []
        return ([r[RES_COL] for r in res], [o['operator_name'] for o in ops], [v['vendor_name'] for v in vends])
    except: return ([], [], [])

resource_list, operator_list, vendor_list = get_masters()

# 5. Application Tabs
tab_prod, tab_incharge, tab_log = st.tabs(["📝 Request Form", "👨‍💻 Incharge Desk", "📋 Logbook"])

# --- TAB 1: PRODUCTION REQUEST ---
with tab_prod:
    st.subheader(f"Create New {hub_mode} Request")
    with st.form("main_request_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        u_no = c1.selectbox("Unit No", [1, 2, 3])
        j_code = c1.text_input("Job Code")
        part = c2.text_input("Part Name")
        
        # This list now correctly changes based on the button clicked above
        act = c2.selectbox("Activity/Process", ACTIVITY_OPTS)
        
        priority = c3.selectbox("Priority", ["Low", "Medium", "High", "URGENT"])
        
        if st.form_submit_button("Submit Request"):
            if j_code and part:
                conn.table(DB_TABLE).insert({
                    "unit_no": u_no, "job_code": j_code, "part_name": part,
                    "activity_type": act, "priority": priority, "status": "Pending"
                }).execute()
                st.success(f"Sent to {hub_mode} Incharge!")
                st.rerun()

# --- TAB 2: INCHARGE DESK (Simplified In-House) ---
with tab_incharge:
    st.subheader(f"Allocation: {hub_mode}")
    pin = st.text_input("Incharge PIN", type="password")
    if pin == "1234":
        jobs = conn.table(DB_TABLE).select("*").neq("status", "Finished").execute().data or []
        for job in jobs:
            with st.expander(f"Job: {job['job_code']} | {job['priority']}"):
                mode = st.radio("Who is working?", ["Own Team", "Contractor"], key=f"m_{job['id']}")
                ca, cb = st.columns(2)
                m_st = ca.selectbox(f"Select {RES_LABEL}", resource_list, key=f"s_{job['id']}")
                
                if mode == "Own Team":
                    worker = cb.selectbox("Assign Operator", operator_list, key=f"o_{job['id']}")
                else:
                    worker = cb.selectbox("Assign Vendor", vendor_list, key=f"v_{job['id']}")
                
                if st.button("Start Work", key=f"btn_{job['id']}"):
                    conn.table(DB_TABLE).update({
                        "status": "In-House" if mode == "Own Team" else "Outsourced",
                        "machine_id": m_st,
                        "operator_id": worker if mode == "Own Team" else None,
                        "vendor_id": worker if mode == "Contractor" else None
                    }).eq("id", job['id']).execute()
                    st.rerun()

# --- TAB 3: LOGBOOK ---
with tab_log:
    st.subheader(f"Records for {hub_mode}")
    all_data = conn.table(DB_TABLE).select("*").order("created_at", desc=True).execute().data
    if all_data:
        st.dataframe(pd.DataFrame(all_data), use_container_width=True)
