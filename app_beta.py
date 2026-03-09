import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import plotly.express as px

# 1. Setup & Connection
st.set_page_config(page_title="B&G Enterprise Hub", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)

# --- HUB SELECTION (TOP LEVEL) ---
if 'hub' not in st.session_state:
    st.session_state.hub = "Machining Hub"

st.write("### 🏢 Select Department")
c1, c2 = st.columns(2)

if c1.button("⚙️ MACHINING HUB", use_container_width=True, 
             type="primary" if st.session_state.hub == "Machining Hub" else "secondary"):
    st.session_state.hub = "Machining Hub"
    st.rerun()

if c2.button("✨ BUFFING & POLISHING", use_container_width=True, 
             type="primary" if st.session_state.hub == "Buffing & Polishing" else "secondary"):
    st.session_state.hub = "Buffing & Polishing"
    st.rerun()

# --- DYNAMIC CONFIGURATION ---
if st.session_state.hub == "Machining Hub":
    DB_TABLE = "beta_machining_logs"
    RES_MASTER = "beta_machine_master"
    RES_LABEL = "Machine"
    RES_COL = "machine_name"
    ACTIVITY_LIST = ["Turning", "Drilling", "Milling", "Keyway", "Dishbending"]
else:
    DB_TABLE = "beta_buffing_logs"
    RES_MASTER = "beta_buffing_station_master"
    RES_LABEL = "Buffing Station"
    RES_COL = "station_name"
    ACTIVITY_LIST = ["Rough Buffing", "Mirror Polishing", "Satin Finish", "RA Value Check"]

st.divider()

# 2. Global Data Fetching
def fetch_data():
    logs = conn.table(DB_TABLE).select("*").order("created_at", desc=True).execute().data or []
    res = conn.table(RES_MASTER).select(RES_COL).execute().data or []
    ops = conn.table("beta_operator_master").select("operator_name").execute().data or []
    vends = conn.table("beta_vendor_master").select("vendor_name").execute().data or []
    return logs, [r[RES_COL] for r in res], [o['operator_name'] for o in ops], [v['vendor_name'] for v in vends]

all_logs, resource_list, operator_list, vendor_list = fetch_data()

# 3. Application Tabs
t_prod, t_inch, t_exec, t_masters = st.tabs([
    "📝 Request & Live", "👨‍💻 Incharge Desk", "📊 Executive Analysis", "🛠️ Masters"
])

# --- TAB 1: PRODUCTION REQUEST & STATUS ---
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
                st.success("Request Sent!")
                st.rerun()

    st.subheader(f"🚦 Live {st.session_state.hub} Status")
    if all_logs:
        df = pd.DataFrame(all_logs)
        active_df = df[df['status'] != "Finished"]
        st.dataframe(active_df[['unit_no', 'job_code', 'part_name', 'status', 'priority']], use_container_width=True)

# --- TAB 2: INCHARGE DESK (ALLOCATION) ---
with t_inch:
    pin = st.text_input("Incharge PIN", type="password")
    if pin == "1234":
        pending_jobs = [j for j in all_logs if j['status'] not in ["Finished"]]
        for job in pending_jobs:
            with st.expander(f"Unit {job['unit_no']} | Job: {job['job_code']} ({job['status']})"):
                mode = st.radio("Allot To:", ["Own Team", "Contractor"], key=f"m_{job['id']}", horizontal=True)
                ca, cb = st.columns(2)
                m_st = ca.selectbox(f"Assign {RES_LABEL}", resource_list, key=f"s_{job['id']}")
                person = cb.selectbox("Assign Person/Agency", operator_list if mode=="Own Team" else vendor_list, key=f"p_{job['id']}")
                
                c_act1, c_act2 = st.columns(2)
                if c_act1.button("🚀 Start Work", key=f"go_{job['id']}"):
                    status_val = "In-House" if mode == "Own Team" else "Outsourced"
                    update_data = {"status": status_val, "machine_id": m_st}
                    if mode == "Own Team": update_data["operator_id"] = person
                    else: update_data["vendor_id"] = person
                    conn.table(DB_TABLE).update(update_data).eq("id", job['id']).execute()
                    st.rerun()
                
                if job['status'] in ["In-House", "Outsourced"]:
                    if c_act2.button("🏁 Mark Finished", key=f"fin_{job['id']}"):
                        conn.table(DB_TABLE).update({"status": "Finished"}).eq("id", job['id']).execute()
                        st.rerun()

# --- TAB 3: EXECUTIVE ANALYSIS ---
with t_exec:
    st.subheader(f"📈 {st.session_state.hub} Insights")
    if all_logs:
        df_exec = pd.DataFrame(all_logs)
        c1, c2 = st.columns(2)
        
        # Chart 1: Status Distribution
        fig_status = px.pie(df_exec, names='status', title='Overall Job Status', hole=0.4)
        c1.plotly_chart(fig_status, use_container_width=True)
        
        # Chart 2: Priority Load
        fig_pri = px.bar(df_exec, x='priority', color='status', title='Jobs by Priority')
        c2.plotly_chart(fig_pri, use_container_width=True)

# --- TAB 4: MASTER MANAGEMENT ---
with t_masters:
    st.subheader(f"🛠️ Manage {st.session_state.hub} Resources")
    m_col1, m_col2 = st.columns(2)
    
    with m_col1:
        st.write(f"#### Add {RES_LABEL}")
        new_res = st.text_input(f"New {RES_LABEL} Name")
        if st.button(f"Save {RES_LABEL}"):
            conn.table(RES_MASTER).insert({RES_COL: new_res}).execute()
            st.rerun()
            
    with m_col2:
        st.write("#### Add Manpower")
        m_type = st.selectbox("Type", ["Own Operator", "Contractor Agency"])
        m_name = st.text_input("Name")
        if st.button("Save Person"):
            target_table = "beta_operator_master" if m_type == "Own Operator" else "beta_vendor_master"
            col_name = "operator_name" if m_type == "Own Operator" else "vendor_name"
            conn.table(target_table).insert({col_name: m_name}).execute()
            st.rerun()
