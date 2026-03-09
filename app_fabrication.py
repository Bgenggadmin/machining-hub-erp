import streamlit as st
from st_supabase_connection import SupabaseConnection

st.set_page_config(page_title="Fabrication ERP", layout="wide")

# --- 1. HUB SELECTION ---
if 'hub' not in st.session_state:
    st.session_state.hub = "Welding Hub"

st.sidebar.title("🏭 Fabrication Control")
st.session_state.hub = st.sidebar.radio("Select Department", ["Welding Hub", "CNC Cutting Hub"])

# --- 2. CONFIGURATION ---
if st.session_state.hub == "Welding Hub":
    DB_TABLE, MASTER_TABLE, MASTER_COL, RES_LABEL = "welding_logs", "welding_bay_master", "bay_name", "Welding Bay"
    ACTIVITIES = ["Arc Welding", "TIG", "MIG", "Grinding"]
else:
    DB_TABLE, MASTER_TABLE, MASTER_COL, RES_LABEL = "cnc_logs", "cnc_machine_master", "machine_name", "CNC Machine"
    ACTIVITIES = ["Laser Cutting", "Plasma", "Oxygen Cutting", "Waterjet"]

# --- 3. DATABASE CONNECTION ---
conn = st.connection("supabase", type=SupabaseConnection)

def get_data():
    logs = conn.table(DB_TABLE).select("*").order("id", desc=True).execute()
    masters = conn.table(MASTER_TABLE).select("*").execute()
    return logs.data, [m[MASTER_COL] for m in masters.data]

df_data, resource_list = get_data()

# --- 4. APP TABS ---
tabs = st.tabs(["📝 Production Request", "👨‍🏭 Incharge Desk", "📊 Analytics", "⚙️ Masters"])

# --- TAB 1: PRODUCTION REQUEST ---
with tabs[0]:
    st.header(f"New {st.session_state.hub} Request")
    with st.form("request_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        j_code = c1.text_input("Job Code (Required)")
        part = c2.text_input("Part Name")
        u_no = c3.number_input("Unit No", min_value=1, step=1)
        
        act = st.selectbox("Activity Type", ACTIVITIES)
        
        if st.form_submit_button("Submit to Shop Floor"):
            if j_code:
                conn.table(DB_TABLE).insert({
                    "job_code": j_code, "part_name": part, "unit_no": u_no, 
                    "activity_type": act, "status": "Pending"
                }).execute()
                st.success("Request sent!"); st.rerun()
            else:
                st.error("Job Code is mandatory.")

# --- TAB 2: INCHARGE DESK ---
with tabs[1]:
    active_jobs = [j for j in df_data if j['status'] != "Finished"]
    if not active_jobs: st.info("No pending work.")
    
    for job in active_jobs:
        with st.expander(f"📌 {job['job_code']} | {job['part_name']} ({job['status']})"):
            if job['status'] == "Pending":
                c1, c2 = st.columns(2)
                res = c1.selectbox(f"Assign {RES_LABEL}", resource_list, key=f"res_{job['id']}")
                worker = c2.text_input("Worker Name (Temp/Regular)", key=f"w_{job['id']}")
                if st.button("Start Job", key=f"st_{job['id']}", use_container_width=True):
                    if worker:
                        conn.table(DB_TABLE).update({"status": "In-Progress", "machine_id": res, "operator_name": worker}).eq("id", job['id']).execute(); st.rerun()
                    else: st.warning("Enter worker name.")
            else:
                st.write(f"Working at **{job['machine_id']}** by **{job['operator_name']}**")
                dr = st.text_input("Delay Reason (Optional)", value=job['delay_reason'] or "", key=f"dr_{job['id']}")
                if st.button("Complete Job", key=f"f_{job['id']}", use_container_width=True):
                    conn.table(DB_TABLE).update({"status": "Finished", "delay_reason": dr}).eq("id", job['id']).execute(); st.rerun()

# --- TAB 3: ANALYTICS ---
with tabs[2]:
    import pandas as pd
    if df_data:
        df = pd.DataFrame(df_data)
        st.subheader("Live Status Overview")
        c1, c2, c3 = st.columns(3)
        c1.metric("Pending", len(df[df['status'] == "Pending"]))
        c2.metric("In-Progress", len(df[df['status'] == "In-Progress"]))
        c3.metric("Finished Today", len(df[df['status'] == "Finished"]))
        st.dataframe(df[["job_code", "part_name", "status", "machine_id", "operator_name", "delay_reason"]], use_container_width=True)

# --- TAB 4: MASTERS ---
with tabs[3]:
    st.header(f"Manage {RES_LABEL}s")
    new_res = st.text_input(f"Add New {RES_LABEL}")
    if st.button(f"Save {RES_LABEL}"):
        conn.table(MASTER_TABLE).insert({MASTER_COL: new_res}).execute(); st.rerun()
    st.write("Current List:", resource_list)
