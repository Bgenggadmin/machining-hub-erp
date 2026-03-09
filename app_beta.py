import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd

# 1. Page Configuration
st.set_page_config(page_title="B&G Integrated Hub", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)

# --- HUB SELECTION LOGIC (TOP BUTTONS) ---
if 'hub' not in st.session_state:
    st.session_state.hub = "Machining Hub"

st.write("### 🏢 Select Department")
c_mach, c_buff = st.columns(2)

# Machining Button
if c_mach.button("⚙️ MACHINING HUB", use_container_width=True, 
                 type="primary" if st.session_state.hub == "Machining Hub" else "secondary"):
    st.session_state.hub = "Machining Hub"
    st.rerun()

# Buffing Button
if c_buff.button("✨ BUFFING & POLISHING", use_container_width=True, 
                 type="primary" if st.session_state.hub == "Buffing & Polishing" else "secondary"):
    st.session_state.hub = "Buffing & Polishing"
    st.rerun()

# --- DYNAMIC CONFIGURATION (Updated instantly by buttons) ---
if st.session_state.hub == "Machining Hub":
    DB_TABLE = "beta_machining_logs"
    RES_MASTER = "beta_machine_master"
    RES_LABEL = "Machine"
    RES_COL = "machine_name"
    # Activities specific to Machining
    ACTIVITY_LIST = ["Turning", "Drilling", "Milling", "Keyway", "Dishbending"]
else:
    DB_TABLE = "beta_buffing_logs"
    RES_MASTER = "beta_buffing_station_master"
    RES_LABEL = "Buffing Station"
    RES_COL = "station_name"
    # Activities specific to Buffing
    ACTIVITY_LIST = ["Rough Buffing", "Mirror Polishing", "Satin Finish", "RA Value Check", "Cleaning"]

st.divider()
st.title(f"Selected: {st.session_state.hub}")

# 2. Fetch Master Data from Beta Tables
def get_beta_masters():
    try:
        res = conn.table(RES_MASTER).select(RES_COL).execute().data or []
        ops = conn.table("beta_operator_master").select("operator_name").execute().data or []
        vends = conn.table("beta_vendor_master").select("vendor_name").execute().data or []
        return (
            [r[RES_COL] for r in res], 
            [o['operator_name'] for o in ops], 
            [v['vendor_name'] for v in vends]
        )
    except:
        return [], [], []

resource_list, operator_list, vendor_list = get_beta_masters()

# 3. Application Tabs
tab_prod, tab_incharge, tab_log = st.tabs(["📝 Request Form", "👨‍💻 Incharge Desk", "📋 Logbook"])

# --- TAB 1: PRODUCTION REQUEST ---
with tab_prod:
    st.subheader(f"New Request for {st.session_state.hub}")
    with st.form("request_form_integrated", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        u_no = col1.selectbox("Unit No", [1, 2, 3])
        j_code = col1.text_input("Job Code")
        part = col2.text_input("Part Name")
        
        # This dropdown WILL change now because it uses ACTIVITY_LIST
        act = col2.selectbox("Select Activity", ACTIVITY_LIST)
        
        priority = col3.selectbox("Priority", ["Low", "Medium", "High", "URGENT"])
        
        if st.form_submit_button("Submit Request"):
            if j_code and part:
                conn.table(DB_TABLE).insert({
                    "unit_no": u_no, "job_code": j_code, "part_name": part,
                    "activity_type": act, "priority": priority, "status": "Pending"
                }).execute()
                st.success(f"Job {j_code} submitted to {st.session_state.hub}!")
                st.rerun()

# --- TAB 2: INCHARGE ALLOCATION (INTERNAL ONLY) ---
with tab_incharge:
    st.subheader(f"Allotment Desk: {st.session_state.hub}")
    pin = st.text_input("Incharge PIN", type="password", key="pin_input")
    
    if pin == "1234":
        # Only fetch jobs for the currently active hub
        jobs = conn.table(DB_TABLE).select("*").neq("status", "Finished").execute().data or []
        
        for job in jobs:
            with st.expander(f"Job: {job['job_code']} | Part: {job['part_name']}"):
                mode = st.radio("Manpower Source", ["Own Team", "Contractor (In-house)"], key=f"mode_{job['id']}")
                
                c_a, c_b = st.columns(2)
                m_st = c_a.selectbox(f"Select {RES_LABEL}", resource_list, key=f"res_{job['id']}")
                
                if mode == "Own Team":
                    worker = c_b.selectbox("Operator", operator_list, key=f"op_{job['id']}")
                else:
                    worker = c_b.selectbox("Contractor", vendor_list, key=f"vn_{job['id']}")
                
                if st.button("🚀 Start Work", key=f"go_{job['id']}", use_container_width=True):
                    status_val = "In-House" if mode == "Own Team" else "Outsourced"
                    conn.table(DB_TABLE).update({
                        "status": status_val,
                        "machine_id": m_st,
                        "operator_id": worker if mode == "Own Team" else None,
                        "vendor_id": worker if mode == "Contractor (In-house)" else None
                    }).eq("id", job['id']).execute()
                    st.rerun()

                if job['status'] in ["In-House", "Outsourced"]:
                    if st.button("🏁 Finish Job", key=f"fin_{job['id']}", use_container_width=True):
                        conn.table(DB_TABLE).update({"status": "Finished"}).eq("id", job['id']).execute()
                        st.rerun()

# --- TAB 3: LOGBOOK ---
with tab_log:
    st.subheader(f"Logbook: {st.session_state.hub}")
    data = conn.table(DB_TABLE).select("*").order("created_at", desc=True).execute().data
    if data:
        st.dataframe(pd.DataFrame(data), use_container_width=True)
