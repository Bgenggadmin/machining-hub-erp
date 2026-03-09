import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import datetime
import io

# 1. Initialize Connection & Page Config
st.set_page_config(page_title="B&G ERP BETA", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)

if 'hub' not in st.session_state:
    st.session_state.hub = "Machining Hub"

st.title(f"⚙️ B&G {st.session_state.hub}: ERP (BETA)")

# --- HUB SWITCHER ---
c1, c2 = st.sidebar.columns(2)
if c1.button("⚙️ Machining Hub"): st.session_state.hub = "Machining Hub"; st.rerun()
if c2.button("✨ Buffing Hub"): st.session_state.hub = "Buffing Hub"; st.rerun()

# --- DYNAMIC CONFIGURATION ---
if st.session_state.hub == "Machining Hub":
    DB_TABLE = "beta_machining_logs"
    MASTER_TABLE = "beta_machine_master" # Ensure these beta names exist
    MASTER_COL = "machine_name"
    RES_LABEL = "Machine"
    ACTIVITIES = ["Turning", "Drilling", "Milling", "Keyway", "Dishbending"]
else:
    DB_TABLE = "beta_buffing_logs"
    MASTER_TABLE = "beta_buffing_station_master"
    MASTER_COL = "station_name"
    RES_LABEL = "Buffing Station"
    ACTIVITIES = ["Rough Buffing", "Mirror Polishing", "Satin Finish", "RA Value Check"]

# 2. Fetch Master Data
def get_master_data():
    try:
        res = conn.table(MASTER_TABLE).select(MASTER_COL).execute().data or []
        ops = conn.table("beta_operator_master").select("operator_name").execute().data or []
        vnds = conn.table("beta_vendor_master").select("vendor_name").execute().data or []
        vhs = conn.table("beta_vehicle_master").select("vehicle_number").execute().data or []
        return ([r[MASTER_COL] for r in res], [o['operator_name'] for o in ops], 
                [v['vendor_name'] for v in vnds], [vh['vehicle_number'] for vh in vhs])
    except: return ([], [], [], [])

resource_list, operator_list, vendor_list, vehicle_list = get_master_data()

all_logs_query = conn.table(DB_TABLE).select("*").order("created_at", desc=True).execute()
all_data = all_logs_query.data or []

tab_prod, tab_incharge, tab_analytics, tab_log, tab_masters = st.tabs([
    "📝 Request & Live", "👨‍💻 Incharge Desk", "📊 Executive Analytics", "📋 Full Logbook", "🛠️ Masters"
])

# --- TAB 1: PRODUCTION REQUEST & LIVE ---
with tab_prod:
    st.subheader(f"📋 New {st.session_state.hub} Request")
    with st.form("prod_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        u_no = c1.selectbox("Unit No", [1, 2, 3])
        j_code = c1.text_input("Job Code")
        part = c2.text_input("Part Name")
        act = c2.selectbox("Activity", ACTIVITIES)
        req_date = c3.date_input("Required Date")
        priority = c3.selectbox("Priority", ["Low", "Medium", "High", "URGENT"])
        notes = st.text_area("🗒️ Special Production Notes")
        
        if st.form_submit_button("Send to Incharge"):
            if j_code and part:
                conn.table(DB_TABLE).insert({
                    "unit_no": u_no, "job_code": j_code, "part_name": part,
                    "activity_type": act, "required_date": str(req_date), 
                    "request_date": str(datetime.date.today()),
                    "priority": priority, "status": "Pending", "special_notes": notes
                }).execute()
                st.success(f"Request {j_code} submitted."); st.rerun()

    st.divider()
    st.subheader("🚦 Current Shop Floor Status")
    unit_sel = st.radio("View Unit", [1, 2, 3], horizontal=True)
    if all_data:
        df_status = pd.DataFrame(all_data)
        unit_view = df_status[df_status['unit_no'] == unit_sel].copy()
        if not unit_view.empty:
            unit_view['required_date'] = pd.to_datetime(unit_view['required_date'])
            unit_view['Days Left'] = (unit_view['required_date'].dt.date - datetime.date.today()).apply(lambda x: x.days)
            disp_cols = ['job_code', 'part_name', 'status', 'priority', 'request_date', 'required_date', 'Days Left', 'special_notes']
            st.dataframe(unit_view[disp_cols], use_container_width=True, hide_index=True)

# --- TAB 2: INCHARGE DESK (ALL LOGIC RESTORED) ---
with tab_incharge:
    st.subheader("🎯 Allocation & Intervention")
    auth_code = st.text_input("Incharge Pin", type="password")
    
    if auth_code == "1234":
        active_jobs = [j for j in all_data if j['status'] != "Finished"]
        for job in active_jobs:
            p_color = {"URGENT": "🔴", "High": "🟠", "Medium": "🟡", "Low": "⚪"}.get(job['priority'], "⚪")
            with st.expander(f"{p_color} {job['priority']} | Unit {job['unit_no']} | Job: {job['job_code']} - {job['part_name']}"):
                st.info(f"PPC Required: {job.get('required_date')} | Notes: {job.get('special_notes') or 'None'}")
                c_del, c_int = st.columns(2)
                d_reason = c_del.text_input("Delay Reason", value=job.get('delay_reason') or '', key=f"d_{job['id']}")
                i_note = c_int.text_area("Intervention Note", value=job.get('intervention_note') or '', key=f"n_{job['id']}")
                
                if job['status'] == "Pending":
                    mode = st.radio("Path", ["In-House", "Outsource"], key=f"m_{job['id']}", horizontal=True)
                    if mode == "In-House":
                        c1, c2 = st.columns(2)
                        m = c1.selectbox(f"Assign {RES_LABEL}", resource_list, key=f"res_{job['id']}")
                        o = c2.selectbox("Assign Operator", operator_list, key=f"op_{job['id']}")
                        if st.button("🚀 Allot", key=f"b1_{job['id']}", use_container_width=True):
                            conn.table(DB_TABLE).update({"status": "In-House", "machine_id": m, "operator_id": o, "delay_reason": d_reason, "intervention_note": i_note}).eq("id", job['id']).execute(); st.rerun()
                    else:
                        c1, c2, c3 = st.columns(3)
                        v = c1.selectbox("Vendor", vendor_list, key=f"v_{job['id']}")
                        vh = c2.selectbox("Vehicle", vehicle_list, key=f"vh_{job['id']}")
                        gp = c3.text_input("Gatepass No", key=f"gp_{job['id']}")
                        if st.button("🚚 Dispatch", key=f"b2_{job['id']}", use_container_width=True):
                            conn.table(DB_TABLE).update({"status": "Outsourced", "vendor_id": v, "vehicle_no": vh, "gatepass_no": gp, "delay_reason": d_reason, "intervention_note": i_note}).eq("id", job['id']).execute(); st.rerun()
                
                elif job['status'] == "Outsourced":
                    wb = st.text_input("Waybill / Return DC", key=f"wb_{job['id']}")
                    if st.button("✅ Mark Received", key=f"b3_{job['id']}", use_container_width=True):
                        conn.table(DB_TABLE).update({"status": "Finished", "waybill_no": wb, "delay_reason": d_reason, "intervention_note": i_note}).eq("id", job['id']).execute(); st.rerun()
                
                elif job['status'] == "In-House":
                    if st.button("🏁 Mark Finished", key=f"b4_{job['id']}", use_container_width=True):
                        conn.table(DB_TABLE).update({"status": "Finished", "delay_reason": d_reason, "intervention_note": i_note}).eq("id", job['id']).execute(); st.rerun()

# --- TAB 3: EXECUTIVE ANALYTICS ---
with tab_analytics:
    if all_data:
        df = pd.DataFrame(all_data)
        st.error("### 🚨 Urgent Attention Required")
        urgent = df[df['priority'].isin(['URGENT', 'High']) & (df['status'] != 'Finished')]
        st.dataframe(urgent[['job_code', 'priority', 'status', 'required_date', 'delay_reason']], use_container_width=True, hide_index=True)
        
        st.divider()
        report_df = df.copy()
        # Clean timestamps for Excel
        for col in report_df.columns:
            if pd.api.types.is_datetime64_any_dtype(report_df[col]):
                report_df[col] = report_df[col].dt.tz_localize(None)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            report_df.to_excel(writer, index=False, sheet_name='Sheet1')
        st.download_button("📂 Download Full Excel Report", data=buffer.getvalue(), file_name=f"B_G_Report_{datetime.date.today()}.xlsx")

# --- TAB 4: LOGBOOK ---
with tab_log:
    st.dataframe(all_data, use_container_width=True)

# --- TAB 5: MASTERS ---
with tab_masters:
    admin_pin = st.text_input("Admin Pin", type="password", key="adm_pin")
    if admin_pin == "1234":
        st.write("### ➕ Manage Resources")
        c1, c2, c3 = st.columns([2, 2, 1])
        cat = c1.selectbox("Table", [MASTER_TABLE, "beta_operator_master", "beta_vendor_master", "beta_vehicle_master"])
        cmap = {MASTER_TABLE: MASTER_COL, "beta_operator_master": "operator_name", "beta_vendor_master": "vendor_name", "beta_vehicle_master": "vehicle_number"}
        val = c2.text_input("New Entry Name")
        if c3.button("Add"):
            if val: conn.table(cat).insert({cmap[cat]: val}).execute(); st.rerun()
