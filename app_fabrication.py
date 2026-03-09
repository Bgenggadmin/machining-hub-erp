import streamlit as st
from st_supabase_connection import SupabaseConnection
import datetime
import pandas as pd

st.set_page_config(page_title="Fabrication ERP", layout="wide")

# --- 1. DATABASE CONNECTION ---
conn = st.connection("supabase", type=SupabaseConnection)

def get_all_data():
    # Fetch Logs
    logs = conn.table("fabrication_logs").select("*").order("id", desc=True).execute()
    # Fetch Masters
    res_m = conn.table("fab_resource_master").select("*").execute()
    op_m = conn.table("fab_operator_master").select("*").execute()
    
    return (
        pd.DataFrame(logs.data) if logs.data else pd.DataFrame(),
        [r['res_name'] for r in res_m.data],
        [o['op_name'] for o in op_m.data]
    )

df_main, resource_list, operator_list = get_all_data()

# --- 2. HEADER & TABS ---
st.title("👨‍🏭 Fabrication Production Hub")
tabs = st.tabs(["📝 Production Request", "👨‍🏭 Incharge Desk", "📊 Live Summary", "⚙️ Master Registry"])

# --- TAB 1: PRODUCTION REQUEST ---
with tabs[0]:
    st.subheader("Create New Request")
    with st.form("fab_request", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        u_no = col1.number_input("Unit No", min_value=1, step=1)
        part = col2.text_input("Part Name")
        req_d = col3.date_input("Required Date")
        
        col4, col5, col6 = st.columns(3)
        j_code = col4.text_input("Job Code (Required)")
        act = col5.selectbox("Activity", ["TIG Welding", "MIG Welding", "ARC Welding", "Grinding", "CNC Laser", "CNC Plasma"])
        prio = col6.selectbox("Priority", ["Normal", "Urgent", "Critical"])
        
        sub_by = st.text_input("Submitted By (Your Name)")
        notes = st.text_area("Special Notes")
        
        if st.form_submit_button("Submit Request"):
            if j_code:
                conn.table("fabrication_logs").insert({
                    "unit_no": u_no, "part_name": part, "required_date": str(req_d),
                    "job_code": j_code, "activity_type": act, "priority": prio,
                    "submitted_by": sub_by, "special_notes": notes, "status": "Pending",
                    "request_date": str(datetime.date.today())
                }).execute()
                st.success(f"Job {j_code} submitted!"); st.rerun()
            else:
                st.error("Job Code is mandatory.")

# --- TAB 2: INCHARGE DESK (Allotment) ---
with tabs[1]:
    active_jobs = df_main[df_main['status'] != "Finished"].to_dict('records') if not df_main.empty else []
    if not active_jobs: st.info("No pending work orders.")

    for job in active_jobs:
        with st.expander(f"📌 {job['job_code']} | {job['part_name']} (Unit {job['unit_no']})"):
            st.write(f"**Activity:** {job['activity_type']} | **Req Date:** {job['required_date']} | **By:** {job['submitted_by']}")
            
            if job['status'] == "Pending":
                c1, c2, c3 = st.columns([1, 1, 1])
                m_id = c1.selectbox("Select Machine/Bay", resource_list, key=f"m_{job['id']}")
                l_type = c2.radio("Labor Type", ["Regular", "Temporary"], key=f"lt_{job['id']}")
                
                if l_type == "Regular":
                    o_name = c3.selectbox("Select Operator", operator_list, key=f"op_{job['id']}")
                else:
                    o_name = c3.text_input("Enter Temp Name", key=f"opt_{job['id']}")
                
                if st.button("🚀 Start Production", key=f"btn_{job['id']}", use_container_width=True):
                    if o_name:
                        conn.table("fabrication_logs").update({
                            "status": "In-Progress", "machine_id": m_id, "operator_name": o_name
                        }).eq("id", job['id']).execute(); st.rerun()
            
            elif job['status'] == "In-Progress":
                st.warning(f"Working at: {job['machine_id']} | Assigned to: {job['operator_name']}")
                dr = st.text_input("Delay Reason (Optional)", value=job['delay_reason'] or "", key=f"dr_{job['id']}")
                if st.button("🏁 Mark Finished", key=f"f_{job['id']}", use_container_width=True):
                    conn.table("fabrication_logs").update({"status": "Finished", "delay_reason": dr}).eq("id", job['id']).execute(); st.rerun()

# --- TAB 3: LIVE SUMMARY TABLE ---
with tabs[2]:
    if not df_main.empty:
        st.subheader("Current Production Status")
        # Showing only the requested columns
        display_cols = ["job_code", "unit_no", "part_name", "activity_type", "status", "machine_id", "operator_name", "request_date", "required_date", "priority"]
        st.dataframe(df_main[display_cols], use_container_width=True, hide_index=True)
    else:
        st.info("No records found.")

# --- TAB 4: MASTER REGISTRY ---
with tabs[3]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Add Machine/Bay")
        new_res = st.text_input("Bay Name")
        if st.button("Save Bay"):
            conn.table("fab_resource_master").insert({"res_name": new_res}).execute(); st.rerun()
        st.write(resource_list)
    with c2:
        st.subheader("Add Regular Operator")
        new_op = st.text_input("Operator Name")
        if st.button("Save Operator"):
            conn.table("fab_operator_master").insert({"op_name": new_op}).execute(); st.rerun()
        st.write(operator_list)
