import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import datetime

# 1. Page Configuration
st.set_page_config(page_title="B&G Integrated Sandbox", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)

# --- SIDEBAR: HUB SELECTOR (THE ENGINE) ---
st.sidebar.title("🏢 Department Selector")
hub_mode = st.sidebar.radio("Switch Hub", ["Machining Hub", "Buffing & Polishing"])

# Dynamic Configuration Mapping for Sandbox
# These point to the 'beta_' tables you created in SQL
if hub_mode == "Machining Hub":
    DB_TABLE = "beta_machining_logs"
    RES_MASTER = "beta_machine_master"
    RES_LABEL = "Machine"
    RES_COL = "machine_name"
    ACTIVITY_OPTS = ["Turning", "Drilling", "Milling", "Keyway", "Dishbending"]
    RES_ICON = "⚙️"
else:
    DB_TABLE = "beta_buffing_logs"
    RES_MASTER = "beta_buffing_station_master"
    RES_LABEL = "Buffing Station"
    RES_COL = "station_name"
    ACTIVITY_OPTS = ["Rough Buffing", "Mirror Polishing", "Satin Finish", "RA Value Check", "Cleaning"]
    RES_ICON = "✨"

st.title(f"{RES_ICON} B&G {hub_mode}: Sandbox Beta")

# 2. Fetch Master Data from Beta Tables
def get_beta_masters():
    try:
        # Fetching from the beta_ prefixed tables we created
        res = conn.table(RES_MASTER).select(RES_COL).execute().data or []
        ops = conn.table("beta_operator_master").select("operator_name").execute().data or []
        vends = conn.table("beta_vendor_master").select("vendor_name").execute().data or []
        return (
            [r[RES_COL] for r in res], 
            [o['operator_name'] for o in ops], 
            [v['vendor_name'] for v in vends]
        )
    except Exception as e:
        st.error(f"Error fetching beta masters: {e}")
        return [], [], []

resource_list, operator_list, vendor_list = get_beta_masters()

# 3. Application Tabs
tab_prod, tab_incharge, tab_log = st.tabs([
    "📝 Request & Live Status", "👨‍💻 Incharge Desk", "📋 Beta Logbook"
])

# --- TAB 1: PRODUCTION REQUEST ---
with tab_prod:
    st.subheader(f"📋 New {hub_mode} Request")
    with st.form("prod_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        u_no = c1.selectbox("Unit No", [1, 2, 3])
        j_code = c1.text_input("Job Code")
        part = c2.text_input("Part Name")
        
        # This dropdown automatically changes based on the Sidebar Hub Selection
        act = c2.selectbox("Activity/Process", ACTIVITY_OPTS)
        
        req_date = c3.date_input("Required Date")
        priority = c3.selectbox("Priority", ["Low", "Medium", "High", "URGENT"])
        
        if st.form_submit_button("Send to Incharge"):
            if j_code and part:
                conn.table(DB_TABLE).insert({
                    "unit_no": u_no, "job_code": j_code, "part_name": part,
                    "activity_type": act, "required_date": str(req_date), 
                    "priority": priority, "status": "Pending"
                }).execute()
                st.success(f"Request {j_code} sent to {hub_mode} Incharge!")
                st.rerun()

    st.divider()
    st.subheader(f"🚦 {hub_mode} Live Status")
    all_logs = conn.table(DB_TABLE).select("*").order("created_at", desc=True).execute().data or []
    if all_logs:
        df_status = pd.DataFrame(all_logs)
        st.dataframe(df_status[['job_code', 'part_name', 'status', 'priority', 'required_date']].head(10), 
                     use_container_width=True, hide_index=True)

# --- TAB 2: INCHARGE DESK (PIN: 1234) ---
with tab_incharge:
    st.subheader(f"🎯 Internal Allocation ({hub_mode})")
    auth_code = st.text_input("Incharge Pin", type="password", key="incharge_pin")
    
    if auth_code == "1234":
        active_jobs = [j for j in all_logs if j['status'] != "Finished"]
        
        if not active_jobs:
            st.info(f"No pending jobs in {hub_mode}.")
        
        for job in active_jobs:
            p_color = {"URGENT": "🔴", "High": "🟠", "Medium": "🟡", "Low": "⚪"}.get(job['priority'], "⚪")
            with st.expander(f"{p_color} {job['priority']} | Unit {job['unit_no']} | Job: {job['job_code']}"):
                
                # Internal Remark fields
                c1, c2 = st.columns(2)
                d_reason = c1.text_input("Delay/Remark", value=job.get('delay_reason') or '', key=f"d_{job['id']}")
                i_note = c2.text_area("Incharge Note", value=job.get('intervention_note') or '', key=f"n_{job['id']}")
                
                if job['status'] == "Pending":
                    # ALLOCATION: Own Team vs Contractor (Both are In-house)
                    mode = st.radio("Allocation Mode", ["In-House (Own Team)", "Outsourced (Contractor)"], 
                                    key=f"m_{job['id']}", horizontal=True)
                    
                    ca, cb = st.columns(2)
                    m = ca.selectbox(f"Select {RES_LABEL}", resource_list, key=f"res_{job['id']}")
                    
                    if "In-House" in mode:
                        o = cb.selectbox("Assign Operator", operator_list, key=f"op_{job['id']}")
                        if st.button(f"🚀 Allot to Own Team", key=f"btn_in_{job['id']}", use_container_width=True):
                            conn.table(DB_TABLE).update({
                                "status": "In-House", "machine_id": m, "operator_id": o,
                                "delay_reason": d_reason, "intervention_note": i_note
                            }).eq("id", job['id']).execute()
                            st.rerun()
                    else:
                        v = cb.selectbox("Assign Contractor Agency", vendor_list, key=f"v_{job['id']}")
                        if st.button("🛠️ Allot to Contractor", key=f"btn_out_{job['id']}", use_container_width=True):
                            conn.table(DB_TABLE).update({
                                "status": "Outsourced", "machine_id": m, "vendor_id": v,
                                "delay_reason": d_reason, "intervention_note": i_note
                            }).eq("id", job['id']).execute()
                            st.rerun()

                else:
                    # TRACKING & FINISHING
                    curr_loc = job.get('machine_id')
                    worker = job.get('operator_id') if job['status'] == "In-House" else job.get('vendor_id')
                    st.success(f"Ongoing: {job['status']} | {RES_LABEL}: {curr_loc} | Assigned: {worker}")
                    
                    if st.button("🏁 Mark Work Completed", key=f"f_in_{job['id']}", use_container_width=True):
                        conn.table(DB_TABLE).update({"status": "Finished"}).eq("id", job['id']).execute()
                        st.rerun()
    else:
        st.info("🔒 Enter PIN to manage internal allocations.")

# --- TAB 3: BETA LOGBOOK ---
with tab_log:
    st.subheader(f"📋 {hub_mode} Master Log (Sandbox)")
    if all_logs:
        df = pd.DataFrame(all_logs)
        st.dataframe(df, use_container_width=True)
        
        # Simple Download for Sandbox testing
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📂 Download Beta Data", csv, f"beta_{hub_mode}.csv", "text/csv")
