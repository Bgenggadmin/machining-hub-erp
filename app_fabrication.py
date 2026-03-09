import streamlit as st
from st_supabase_connection import SupabaseConnection
import datetime
import pandas as pd

st.set_page_config(page_title="Welding & Cutting Hub", layout="wide")

# --- 1. HUB SELECTION (Sidebar) ---
st.sidebar.title("🎯 Department Select")
hub_choice = st.sidebar.radio("Go to Hub:", ["Cutting Hub", "Welding Hub"])

# --- 2. DYNAMIC CONFIGURATION ---
DB_TABLE = "fabrication_logs" 
if hub_choice == "Cutting Hub":
    MASTER_TABLE = "cnc_machine_master"
    MASTER_COL = "machine_name"
    RES_LABEL = "Cutting Machine"
    OP_LABEL = "Operator"
    ACTIVITIES = ["Laser Cutting", "Plasma Cutting", "Oxygen Cutting", "Waterjet"]
else:
    MASTER_TABLE = "welding_bay_master"
    MASTER_COL = "bay_name"
    RES_LABEL = "Welding Bay"
    OP_LABEL = "Welder"
    ACTIVITIES = ["TIG Welding", "MIG Welding", "ARC Welding", "Grinding"]

# --- 3. DATABASE CONNECTION ---
conn = st.connection("supabase", type=SupabaseConnection)

def get_all_data():
    # Fetch logs
    logs = conn.table(DB_TABLE).select("*").order("id", desc=True).execute()
    # Fetch masters
    res_m = conn.table(MASTER_TABLE).select("*").execute()
    op_m = conn.table("fab_operator_master").select("*").execute()
    
    # Convert logs to DataFrame
    df = pd.DataFrame(logs.data) if logs.data else pd.DataFrame()
    
    # FILTER logic: Only show rows belonging to the selected Hub
    if not df.empty and 'hub_name' in df.columns:
        df_filtered = df[df['hub_name'] == hub_choice]
    else:
        df_filtered = df

    return (
        df_filtered,
        [r[MASTER_COL] for r in res_m.data],
        [o['op_name'] for o in op_m.data]
    )

df_main, resource_list, operator_list = get_all_data()

# --- 4. HEADER & TABS ---
st.title(f"🛠️ {hub_choice.upper()}")
tabs = st.tabs(["📝 Production Request", "👨‍🏭 Incharge Desk", "📊 Live Summary", "⚙️ Master Registry"])

# --- TAB 1: PRODUCTION REQUEST ---
with tabs[0]:
    st.subheader(f"New {hub_choice} Request")
    
    # Form for submission
    with st.form("fab_request", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        u_no = col1.selectbox("Unit No", ["Unit 1", "Unit 2", "Unit 3"])
        part = col2.text_input("Part Name")
        req_d = col3.date_input("Required Date")
        
        col4, col5, col6 = st.columns(3)
        j_code = col4.text_input("Job Code (Required)")
        act = col5.selectbox("Activity Requested", ACTIVITIES)
        prio = col6.selectbox("Priority", ["Normal", "Urgent", "Critical"])
        
        sub_by = st.text_input("Submitted By")
        notes = st.text_area("Special Notes")
        
        if st.form_submit_button("Submit Request"):
            if j_code:
                conn.table(DB_TABLE).insert({
                    "hub_name": hub_choice, 
                    "unit_no": u_no, 
                    "part_name": part, 
                    "required_date": str(req_d), 
                    "job_code": j_code, 
                    "activity_type": act, 
                    "priority": prio, 
                    "submitted_by": sub_by, 
                    "special_notes": notes, 
                    "status": "Pending", 
                    "request_date": str(datetime.date.today())
                }).execute()
                st.success(f"Job {j_code} submitted!"); st.rerun()
            else:
                st.error("Job Code is mandatory.")
    
    # --- ADDED: MINI SUMMARY TABLE INSIDE TAB 1 ---
    st.divider()
    st.subheader(f"Recent {hub_choice} Submissions")
    if not df_main.empty:
        # Show last 5 entries specifically for the person requesting
        st.table(df_main[["job_code", "part_name", "status", "request_date"]].head(5))
    else:
        st.info("No recent requests found.")

# --- TAB 2: INCHARGE DESK ---
with tabs[1]:
    active_jobs = df_main[df_main['status'] != "Finished"].to_dict('records') if not df_main.empty else []
    if not active_jobs: st.info(f"No pending work in {hub_choice}.")

    for job in active_jobs:
        with st.expander(f"📋 {job['job_code']} | Activity: {job['activity_type']} | {job['unit_no']}"):
            if job['status'] == "Pending":
                c1, c2, c3 = st.columns(3)
                m_id = c1.selectbox(f"Assign {RES_LABEL}", resource_list, key=f"m_{job['id']}")
                l_type = c2.radio("Labor Type", ["Regular", "Temporary"], key=f"lt_{job['id']}", horizontal=True)
                
                if l_type == "Regular":
                    o_name = c3.selectbox(f"Select {OP_LABEL}", operator_list, key=f"op_{job['id']}")
                else:
                    o_name = c3.text_input(f"Enter Temp {OP_LABEL} Name", key=f"opt_{job['id']}")
                
                if st.button(f"🚀 Start {hub_choice.split()[0]}", key=f"btn_{job['id']}", use_container_width=True):
                    if o_name:
                        conn.table(DB_TABLE).update({"status": "In-Progress", "machine_id": m_id, "operator_name": o_name}).eq("id", job['id']).execute(); st.rerun()
            
            elif job['status'] == "In-Progress":
                st.warning(f"Ongoing: {job['machine_id']} | {OP_LABEL}: {job['operator_name']}")
                if st.button("🏁 Mark Finished", key=f"f_{job['id']}", use_container_width=True):
                    conn.table(DB_TABLE).update({"status": "Finished"}).eq("id", job['id']).execute(); st.rerun()

# --- TAB 3: LIVE SUMMARY TABLE (MAIN VIEW) ---
with tabs[2]:
    st.subheader(f"📊 {hub_choice} Full Status Board")
    if not df_main.empty:
        display_cols = ["job_code", "unit_no", "part_name", "activity_type", "status", "machine_id", "operator_name", "priority", "required_date"]
        st.dataframe(df_main[display_cols], use_container_width=True, hide_index=True)
    else:
        st.warning("Data is not loading. Check if SQL table 'fabrication_logs' has data.")

# --- TAB 4: MASTER REGISTRY ---
with tabs[3]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader(f"Manage {RES_LABEL}s")
        new_res = st.text_input(f"Add New {RES_LABEL}")
        if st.button(f"Save {RES_LABEL}"):
            conn.table(MASTER_TABLE).insert({MASTER_COL: new_res}).execute(); st.rerun()
        st.write(resource_list)
    with c2:
        st.subheader(f"Manage {OP_LABEL}s")
        new_op = st.text_input(f"Add Regular {OP_LABEL}")
        if st.button(f"Save {OP_LABEL}"):
            conn.table("fab_operator_master").insert({"op_name": new_op}).execute(); st.rerun()
        st.write(operator_list)
