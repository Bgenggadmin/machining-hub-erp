import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd

# 1. Setup & Connection
st.set_page_config(page_title="B&G Enterprise ERP (Beta)", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)

# --- HUB SELECTION ---
if 'hub' not in st.session_state:
    st.session_state.hub = "Machining Hub"

st.write("### 🏢 Department Selection")
c1, c2 = st.columns(2)

if c1.button("⚙️ MACHINING HUB", use_container_width=True, 
             type="primary" if st.session_state.hub == "Machining Hub" else "secondary"):
    st.session_state.hub = "Machining Hub"
    st.rerun()

if c2.button("✨ BUFFING & POLISHING", use_container_width=True, 
             type="primary" if st.session_state.hub == "Buffing & Polishing" else "secondary"):
    st.session_state.hub = "Buffing & Polishing"
    st.rerun()

# --- DYNAMIC CONFIGURATION (Matches your Original SQL Structure) ---
if st.session_state.hub == "Machining Hub":
    DB_TABLE = "beta_machining_logs"
    RES_MASTER = "beta_machine_master"
    RES_LABEL = "Machine"
    RES_COL = "machine_name"
    ACTIVITY_LIST = ["Turning", "Drilling", "Milling", "Keyway", "Dishbending", "Tapping"]
else:
    DB_TABLE = "beta_buffing_logs"
    RES_MASTER = "beta_buffing_station_master"
    RES_LABEL = "Buffing Station"
    RES_COL = "station_name"
    ACTIVITY_LIST = ["Rough Buffing", "Mirror Polishing", "Satin Finish", "RA Value Check", "Final Cleaning"]

st.divider()

# 2. Robust Data Fetching (Restored Logic)
def fetch_full_data():
    try:
        logs = conn.table(DB_TABLE).select("*").order("created_at", desc=True).execute().data or []
        res = conn.table(RES_MASTER).select(RES_COL).execute().data or []
        ops = conn.table("beta_operator_master").select("operator_name").execute().data or []
        vends = conn.table("beta_vendor_master").select("vendor_name").execute().data or []
        return logs, [r[RES_COL] for r in res], [o['operator_name'] for o in ops], [v['vendor_name'] for v in vends]
    except Exception as e:
        st.error(f"Database Sync Error: {e}")
        return [], [], [], []

all_logs, resource_list, operator_list, vendor_list = fetch_full_data()

# 3. Application Tabs
t_prod, t_inch, t_exec, t_masters = st.tabs([
    "📝 Request & Live", "👨‍💻 Incharge Desk", "📋 Executive Analysis", "🛠️ Masters"
])

# --- TAB 1: PRODUCTION REQUEST & LIVE VIEW ---
with t_prod:
    st.subheader(f"New {st.session_state.hub} Request")
    with st.form(key=f"prod_{st.session_state.hub}", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        u_no = col1.selectbox("Unit No", [1, 2, 3])
        j_code = col1.text_input("Job Code")
        part = col2.text_input("Part Name")
        act = col2.selectbox("Process", ACTIVITY_LIST)
        priority = col3.selectbox("Priority", ["Low", "Medium", "High", "URGENT"])
        
        if st.form_submit_button("Submit Request"):
            if j_code and part:
                conn.table(DB_TABLE).insert({
                    "unit_no": u_no, "job_code": j_code, "part_name": part,
                    "activity_type": act, "priority": priority, "status": "Pending"
                }).execute()
                st.success("Request Registered!")
                st.rerun()

    st.subheader(f"🚦 Live {st.session_state.hub} Shop Floor")
    if all_logs:
        df = pd.DataFrame(all_logs)
        active_df = df[df['status'] != "Finished"]
        if not active_df.empty:
            # Added Machine ID and Operator to live view so Incharge can see who is working
            st.dataframe(active_df[['unit_no', 'job_code', 'part_name', 'status', 'machine_id', 'priority']], 
                         use_container_width=True, hide_index=True)
        else:
            st.info("Floor is currently clear.")

# --- TAB 2: INCHARGE DESK (ALLOCATION) ---
with t_inch:
    st.subheader(f"🎯 Internal Allotment: {st.session_state.hub}")
    pending_jobs = [j for j in all_logs if j['status'] not in ["Finished"]]
    
    for job in pending_jobs:
        with st.expander(f"UNIT {job['unit_no']} | JOB: {job['job_code']} - {job['part_name']} ({job['status']})"):
            mode = st.radio("Resource Type:", ["Own Team", "Contractor"], key=f"m_{job['id']}", horizontal=True)
            ca, cb = st.columns(2)
            m_st = ca.selectbox(f"Select {RES_LABEL}", resource_list, key=f"s_{job['id']}")
            person = cb.selectbox("Assign To", operator_list if mode=="Own Team" else vendor_list, key=f"p_{job['id']}")
            
            c_act1, c_act2 = st.columns(2)
            if c_act1.button("🚀 Confirm & Start", key=f"go_{job['id']}", use_container_width=True):
                status_val = "In-House" if mode == "Own Team" else "Outsourced"
                update_payload = {"status": status_val, "machine_id": m_st}
                if mode == "Own Team": update_payload["operator_id"] = person
                else: update_payload["vendor_id"] = person
                conn.table(DB_TABLE).update(update_payload).eq("id", job['id']).execute()
                st.rerun()
            
            if job['status'] in ["In-House", "Outsourced"]:
                if c_act2.button("🏁 Work Complete", key=f"fin_{job['id']}", use_container_width=True):
                    conn.table(DB_TABLE).update({"status": "Finished"}).eq("id", job['id']).execute()
                    st.rerun()

# --- TAB 3: EXECUTIVE ANALYSIS (RESTORED MAIN LOGIC) ---
with t_exec:
    st.subheader(f"📊 {st.session_state.hub} Performance Summary")
    if all_logs:
        df_exec = pd.DataFrame(all_logs)
        
        # RESTORED: Summary Scorecards
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Requests", len(df_exec))
        m2.metric("Active Jobs", len(df_exec[df_exec['status'] != 'Finished']))
        m3.metric("Completed", len(df_exec[df_exec['status'] == 'Finished']))
        
        st.divider()

        # 1. Action List (High Priority)
        st.markdown("#### 🚨 Critical Action List (Urgent/High)")
        urgent_df = df_exec[(df_exec['priority'].isin(['URGENT', 'High'])) & (df_exec['status'] != 'Finished')]
        st.dataframe(urgent_df[['job_code', 'part_name', 'priority', 'status', 'activity_type']], use_container_width=True, hide_index=True)
        
        # 2. Contractor Performance Tracker
        st.markdown("#### 🤝 Vendor Tracker (Active Load)")
        vendor_df = df_exec[df_exec['status'] == 'Outsourced']
        if not vendor_df.empty:
            v_sum = vendor_df.groupby('vendor_id').size().reset_index(name='Jobs Handled')
            st.table(v_sum)
        
        # 3. Full Audit Log (Restored All Columns)
        st.markdown("#### 📋 Full Department Log")
        st.dataframe(df_exec, use_container_width=True)

        # 4. CSV Export
        csv = df_exec.to_csv(index=False).encode('utf-8')
        st.download_button("📂 Download Department Data", csv, f"{st.session_state.hub}_log.csv", "text/csv")
    else:
        st.write("No historical data found.")

# --- TAB 4: MASTER MANAGEMENT ---
with t_masters:
    st.subheader(f"⚙️ Master Settings: {st.session_state.hub}")
    m_col1, m_col2 = st.columns(2)
    with m_col1:
        st.write(f"#### Add {RES_LABEL}")
        new_res = st.text_input(f"New {RES_LABEL} Name")
        if st.button(f"Save {RES_LABEL}"):
            conn.table(RES_MASTER).insert({RES_COL: new_res}).execute()
            st.rerun()
    with m_col2:
        st.write("#### Add Manpower")
        m_type = st.selectbox("Category", ["Operator (Own)", "Contractor (Vendor)"])
        m_name = st.text_input("Full Name / Agency Name")
        if st.button("Save Personnel"):
            target = "beta_operator_master" if "Own" in m_type else "beta_vendor_master"
            col = "operator_name" if "Own" in m_type else "vendor_name"
            conn.table(target).insert({col: m_name}).execute()
            st.rerun()
