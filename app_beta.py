import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
from datetime import datetime

# 1. Setup & Connection
st.set_page_config(page_title="B&G Enterprise ERP v2.0", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)

# --- HUB SELECTION (Main Interface) ---
if 'hub' not in st.session_state:
    st.session_state.hub = "Machining Hub"

st.write("### 🏢 Department Selection")
c1, c2 = st.columns(2)
if c1.button("⚙️ MACHINING HUB", use_container_width=True, type="primary" if st.session_state.hub == "Machining Hub" else "secondary"):
    st.session_state.hub = "Machining Hub"
    st.rerun()
if c2.button("✨ BUFFING & POLISHING", use_container_width=True, type="primary" if st.session_state.hub == "Buffing & Polishing" else "secondary"):
    st.session_state.hub = "Buffing & Polishing"
    st.rerun()

# --- DYNAMIC CONFIGURATION ---
if st.session_state.hub == "Machining Hub":
    DB_TABLE, RES_MASTER, RES_LABEL, RES_COL = "beta_machining_logs", "beta_machine_master", "Machine", "machine_name"
    ACTIVITY_LIST = ["Turning", "Drilling", "Milling", "Keyway", "Tapping", "Boring", "Facing"]
else:
    DB_TABLE, RES_MASTER, RES_LABEL, RES_COL = "beta_buffing_logs", "beta_buffing_station_master", "Buffing Station", "station_name"
    ACTIVITY_LIST = ["Rough Buffing", "Mirror Polishing", "Satin Finish", "RA Value Check", "Ultrasonic Cleaning"]

st.divider()

# 2. Robust Global Data Fetching
def fetch_all_data():
    try:
        logs = conn.table(DB_TABLE).select("*").order("created_at", desc=True).execute().data or []
        res = conn.table(RES_MASTER).select(RES_COL).execute().data or []
        ops = conn.table("beta_operator_master").select("operator_name").execute().data or []
        vends = conn.table("beta_vendor_master").select("vendor_name").execute().data or []
        return logs, [r[RES_COL] for r in res], [o['operator_name'] for o in ops], [v['vendor_name'] for v in vends]
    except Exception as e:
        st.error(f"Sync Error: {e}")
        return [], [], [], []

all_logs, resource_list, operator_list, vendor_list = fetch_all_data()

# 3. Application Tabs
t_prod, t_inch, t_exec, t_masters = st.tabs([
    "📝 Request & Live Status", "👨‍💻 Incharge Desk", "📋 Executive Analysis", "🛠️ Master Settings"
])

# --- TAB 1: PRODUCTION REQUEST & LIVE STATUS ---
with t_prod:
    st.subheader(f"New {st.session_state.hub} Job Request")
    with st.form(key=f"form_{st.session_state.hub}", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        u_no = col1.selectbox("Unit No", [1, 2, 3])
        j_code = col1.text_input("Job Code (Required)")
        part = col2.text_input("Part Name")
        act = col2.selectbox("Process/Activity", ACTIVITY_LIST)
        req_date = col3.date_input("Required Delivery Date")
        priority = col3.selectbox("Priority", ["Low", "Medium", "High", "URGENT"])
        
        if st.form_submit_button("🚀 Submit to Shop Floor"):
            if j_code and part:
                conn.table(DB_TABLE).insert({
                    "unit_no": u_no, "job_code": j_code, "part_name": part,
                    "activity_type": act, "priority": priority, "status": "Pending",
                    "request_date": str(datetime.now().date()),
                    "required_date": str(req_date)
                }).execute()
                st.success(f"Job {j_code} added to {st.session_state.hub} queue.")
                st.rerun()
            else:
                st.warning("Please fill Job Code and Part Name.")

    st.divider()
    st.subheader(f"🚦 Current {st.session_state.hub} Floor Status")
    if all_logs:
        df = pd.DataFrame(all_logs)
        active_df = df[df['status'] != "Finished"].copy()
        if not active_df.empty:
            # PPC Calculation: Days Lagging
            active_df['required_date'] = pd.to_datetime(active_df['required_date'])
            today = pd.Timestamp(datetime.now().date())
            active_df['Days Left'] = (active_df['required_date'] - today).dt.days
            
            # Formatting for the Floor
            st.dataframe(
                active_df[['unit_no', 'job_code', 'part_name', 'activity_type', 'status', 'Days Left', 'priority']], 
                use_container_width=True, hide_index=True
            )
        else:
            st.info("No active jobs. Shop floor is clear.")

# --- TAB 2: INCHARGE DESK (ALLOCATION & TRACKING) ---
with t_inch:
    st.subheader(f"🎯 Resource Allocation - {st.session_state.hub}")
    pending_jobs = [j for j in all_logs if j['status'] != "Finished"]
    
    if not pending_jobs:
        st.success("All jobs have been processed!")
    
    for job in pending_jobs:
        with st.expander(f"UNIT {job['unit_no']} | JOB: {job['job_code']} | Priority: {job['priority']}"):
            c_mode = st.radio("Manpower:", ["Own Team", "In-house Contractor"], key=f"mode_{job['id']}", horizontal=True)
            ca, cb = st.columns(2)
            res_choice = ca.selectbox(f"Select {RES_LABEL}", resource_list, key=f"res_{job['id']}")
            worker = cb.selectbox("Assign To", operator_list if c_mode == "Own Team" else vendor_list, key=f"work_{job['id']}")
            
            btn_col1, btn_col2 = st.columns(2)
            if btn_col1.button("🚀 Start Production", key=f"start_{job['id']}", use_container_width=True):
                stat = "In-House" if c_mode == "Own Team" else "Outsourced"
                upd = {"status": stat, "machine_id": res_choice}
                if c_mode == "Own Team": upd["operator_id"] = worker
                else: upd["vendor_id"] = worker
                conn.table(DB_TABLE).update(upd).eq("id", job['id']).execute()
                st.rerun()
            
            if job['status'] in ["In-House", "Outsourced"]:
                if btn_col2.button("🏁 Mark as Finished", key=f"fin_{job['id']}", use_container_width=True):
                    conn.table(DB_TABLE).update({"status": "Finished"}).eq("id", job['id']).execute()
                    st.rerun()

# --- TAB 3: EXECUTIVE ANALYSIS (PPC & LAGGING) ---
with t_exec:
    st.subheader(f"🧐 PPC Analysis & Performance: {st.session_state.hub}")
    if all_logs:
        df_exec = pd.DataFrame(all_logs)
        df_exec['required_date'] = pd.to_datetime(df_exec['required_date'])
        today = pd.Timestamp(datetime.now().date())
        
        # 1. Scorecards
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Total Load", len(df_exec))
        s2.metric("WIP Jobs", len(df_exec[df_exec['status'].isin(['In-House', 'Outsourced'])]))
        s3.metric("Pending Allotment", len(df_exec[df_exec['status'] == 'Pending']))
        s4.metric("Completed", len(df_exec[df_exec['status'] == 'Finished']))
        
        # 2. Lagging Action List
        st.markdown("#### 🚨 Delayed Jobs (Lagging Report)")
        df_exec['Lag'] = (today - df_exec['required_date']).dt.days
        delayed = df_exec[(df_exec['Lag'] > 0) & (df_exec['status'] != 'Finished')]
        
        if not delayed.empty:
            st.warning(f"Attention: {len(delayed)} jobs are past their required date!")
            st.dataframe(delayed[['job_code', 'part_name', 'required_date', 'Lag', 'priority', 'unit_no']], use_container_width=True, hide_index=True)
        else:
            st.success("Excellent! No jobs are currently lagging.")

        # 3. Vendor Tracker
        st.markdown("#### 🤝 Contractor Load Tracker")
        v_load = df_exec[df_exec['status'] == 'Outsourced']
        if not v_load.empty:
            v_sum = v_load.groupby('vendor_id').size().reset_index(name='Active Jobs')
            st.table(v_sum)

        # 4. Data Export
        csv = df_exec.to_csv(index=False).encode('utf-8')
        st.download_button(f"📥 Export {st.session_state.hub} Audit Log", csv, f"{st.session_state.hub}_audit.csv", "text/csv")
    else:
        st.info("No data to analyze.")

# --- TAB 4: MASTER MANAGEMENT (NO DELETE) ---
with t_masters:
    st.subheader(f"🛠️ Master Resources for {st.session_state.hub}")
    m1, m2 = st.columns(2)
    with m1:
        st.write(f"#### Add {RES_LABEL}")
        new_r = st.text_input(f"New {RES_LABEL} Name")
        if st.button(f"Save {RES_LABEL}"):
            conn.table(RES_MASTER).insert({RES_COL: new_r}).execute()
            st.rerun()
    with m2:
        st.write("#### Add Staff/Contractor")
        st_type = st.selectbox("Category", ["Operator (Internal)", "Contractor (External Agency)"])
        st_name = st.text_input("Name")
        if st.button("Save Entry"):
            tbl = "beta_operator_master" if "Internal" in st_type else "beta_vendor_master"
            cl = "operator_name" if "Internal" in st_type else "vendor_name"
            conn.table(tbl).insert({cl: st_name}).execute()
            st.rerun()
