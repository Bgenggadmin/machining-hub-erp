import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd

# 1. Page Configuration
st.set_page_config(page_title="B&G Integrated Beta Hub", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)

# 2. Sidebar: Hub Integration Toggle
st.sidebar.title("🏢 Department Switcher")
hub_mode = st.sidebar.radio("Switch Hub:", ["Machining Hub", "Buffing & Polishing"])

# 3. Integration Logic: Dynamic Table & Label Mapping
if hub_mode == "Machining Hub":
    DB_TABLE = "beta_machining_logs"
    RES_MASTER = "beta_machine_master"
    RES_LABEL = "Machine"
    RES_COL = "machine_name"
    ACTIVITY_OPTS = ["Turning", "Drilling", "Milling", "Keyway", "Dishbending"]
else:
    # Buffing Integration
    DB_TABLE = "beta_buffing_logs"
    RES_MASTER = "beta_buffing_station_master"
    RES_LABEL = "Buffing Station"
    RES_COL = "station_name"
    ACTIVITY_OPTS = ["Rough Buffing", "Mirror Polishing", "Satin Finish", "RA Value Check"]

st.title(f"🧪 {hub_mode}: Sandbox Environment")

# 4. Fetch Master Data (Integrated)
def get_beta_masters():
    try:
        res = conn.table(RES_MASTER).select(RES_COL).execute().data or []
        ops = conn.table("beta_operator_master").select("operator_name").execute().data or []
        vends = conn.table("beta_vendor_master").select("vendor_name").execute().data or []
        return ([r[RES_COL] for r in res], [o['operator_name'] for o in ops], [v['vendor_name'] for v in vends])
    except: return ([], [], [])

resource_list, operator_list, vendor_list = get_beta_masters()

# 5. Application Tabs
tab_request, tab_allocation, tab_logs = st.tabs(["📝 New Job Request", "👨‍💻 Incharge Desk", "📋 Beta Logbook"])

# --- TAB 1: NEW REQUEST (Handles Both Hubs) ---
with tab_request:
    st.subheader(f"Create {hub_mode} Request")
    with st.form("request_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        u_no = c1.selectbox("Unit No", [1, 2, 3])
        j_code = c1.text_input("Job Code")
        part = c2.text_input("Part Name")
        act = c2.selectbox("Process/Activity", ACTIVITY_OPTS)
        priority = c3.selectbox("Priority", ["Low", "Medium", "High", "URGENT"])
        
        if st.form_submit_button("Submit to Incharge"):
            if j_code and part:
                conn.table(DB_TABLE).insert({
                    "unit_no": u_no, "job_code": j_code, "part_name": part,
                    "activity_type": act, "priority": priority, "status": "Pending"
                }).execute()
                st.success(f"Request for {j_code} registered in {hub_mode}.")
                st.rerun()

# --- TAB 2: INCHARGE DESK (Integrated Allocation) ---
with tab_allocation:
    st.subheader("In-House Work Allotment")
    auth = st.text_input("Enter Incharge PIN", type="password")
    
    if auth == "1234":
        # Fetch only unfinished jobs for the CURRENTLY SELECTED Hub
        jobs = conn.table(DB_TABLE).select("*").neq("status", "Finished").execute().data or []
        
        for job in jobs:
            p_color = {"URGENT": "🔴", "High": "🟠", "Medium": "🟡", "Low": "⚪"}.get(job['priority'], "⚪")
            with st.expander(f"{p_color} {job['priority']} | Job: {job['job_code']} - {job['part_name']}"):
                
                if job['status'] == "Pending":
                    # Allocation Choice: Own vs Contractor
                    mode = st.radio("Manpower Source", ["Own Team", "Contractor (Outsourced)"], 
                                    key=f"mode_{job['id']}", horizontal=True)
                    
                    ca, cb = st.columns(2)
                    res_val = ca.selectbox(f"Select {RES_LABEL}", resource_list, key=f"res_{job['id']}")
                    
                    if "Own Team" in mode:
                        worker = cb.selectbox("Assign Operator", operator_list, key=f"op_{job['id']}")
                        status_update = "In-House"
                    else:
                        worker = cb.selectbox("Assign Vendor Agency", vendor_list, key=f"vn_{job['id']}")
                        status_update = "Outsourced"
                    
                    if st.button("🚀 Confirm & Start", key=f"start_{job['id']}", use_container_width=True):
                        conn.table(DB_TABLE).update({
                            "status": status_update,
                            "machine_id": res_val,
                            "operator_id": worker if status_update == "In-House" else None,
                            "vendor_id": worker if status_update == "Outsourced" else None
                        }).eq("id", job['id']).execute()
                        st.rerun()
                
                else:
                    st.success(f"Running at {job['machine_id']} by {job.get('operator_id') or job.get('vendor_id')}")
                    if st.button("🏁 Mark as Finished", key=f"fin_{job['id']}", use_container_width=True):
                        conn.table(DB_TABLE).update({"status": "Finished"}).eq("id", job['id']).execute()
                        st.rerun()

# --- TAB 3: LOGBOOK ---
with tab_logs:
    st.subheader(f"Records for {hub_mode}")
    all_data = conn.table(DB_TABLE).select("*").order("created_at", desc=True).execute().data
    if all_data:
        st.dataframe(pd.DataFrame(all_data), use_container_width=True)
