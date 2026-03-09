import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import datetime
import io

# 1. Initialize Connection & Page Config
st.set_page_config(page_title="B&G ERP BETA", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)

# --- CSS FOR ROUND PILL BUTTONS & UI ---
st.markdown("""
    <style>
    div.stButton > button {
        border-radius: 50px;
        padding-left: 25px;
        padding-right: 25px;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

if 'hub' not in st.session_state:
    st.session_state.hub = "Machining Hub"

# --- HUB SELECTION BAR ---
st.write("### 🏢 Department Selection")
c1, c2, _ = st.columns([1, 1, 2])
if c1.button("⚙️ MACHINING HUB", use_container_width=True, type="primary" if st.session_state.hub == "Machining Hub" else "secondary"):
    st.session_state.hub = "Machining Hub"; st.rerun()
if c2.button("✨ BUFFING HUB", use_container_width=True, type="primary" if st.session_state.hub == "Buffing Hub" else "secondary"):
    st.session_state.hub = "Buffing Hub"; st.rerun()

st.divider()

# --- DYNAMIC CONFIGURATION ---
if st.session_state.hub == "Machining Hub":
    DB_TABLE, MASTER_TABLE, MASTER_COL, RES_LABEL = "beta_machining_logs", "beta_machine_master", "machine_name", "Machine"
    ACTIVITIES = ["Turning", "Drilling", "Milling", "Keyway", "Dishbending"]
else:
    DB_TABLE, MASTER_TABLE, MASTER_COL, RES_LABEL = "beta_buffing_logs", "beta_buffing_station_master", "station_name", "Buffing Station"
    ACTIVITIES = ["Rough Buffing", "Mirror Polishing", "Satin Finish", "RA Value Check"]

# 2. Fetch Master Data (RESTORED ALL CATEGORIES)
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

# --- TAB 1: PRODUCTION REQUEST & LIVE STATUS ---
with tab_prod:
    st.subheader(f"📋 New {st.session_state.hub} Request")
    with st.form("prod_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        u_no, j_code = c1.selectbox("Unit No", [1, 2, 3]), c1.text_input("Job Code")
        part, act = c2.text_input("Part Name"), c2.selectbox("Activity", ACTIVITIES)
        req_date, prio = c3.date_input("Required Date"), c3.selectbox("Priority", ["Low", "Medium", "High", "URGENT"])
        notes = st.text_area("Special Production Notes")
        if st.form_submit_button("Send to Incharge"):
            if j_code and part:
                conn.table(DB_TABLE).insert({
                    "unit_no": u_no, "job_code": j_code, "part_name": part, "activity_type": act, 
                    "required_date": str(req_date), "request_date": str(datetime.date.today()),
                    "priority": prio, "status": "Pending", "special_notes": notes
                }).execute(); st.rerun()

    st.divider()
    st.subheader("🚦 Current Shop Floor Status")
    if all_data:
        df_status = pd.DataFrame(all_data)
        df_status['required_date'] = pd.to_datetime(df_status['required_date'], errors='coerce')
        today = pd.Timestamp(datetime.date.today())
        df_status['Days Left'] = (df_status['required_date'] - today).dt.days
        unit_sel = st.radio("View Unit", [1, 2, 3], horizontal=True)
        unit_view = df_status[df_status['unit_no'] == unit_sel].copy()
        st.dataframe(unit_view[['job_code', 'part_name', 'status', 'priority', 'required_date', 'Days Left', 'special_notes']], use_container_width=True, hide_index=True)

# --- TAB 2: INCHARGE DESK (RESTORED LOGISTICS & PIN) ---
with tab_incharge:
    auth_code = st.text_input("Enter Incharge Pin", type="password", key="inch_pin")
    if auth_code == "1234":
        active_jobs = [j for j in all_data if j['status'] != "Finished"]
        for job in active_jobs:
            p_marker = {"URGENT": "🔴", "High": "🟠", "Medium": "🟡", "Low": "⚪"}.get(job['priority'], "⚪")
            with st.expander(f"{p_marker} Unit {job['unit_no']} | {job['job_code']} - {job['part_name']}"):
                st.write(f"**PPC Req:** {job.get('required_date')} | **Notes:** {job.get('special_notes') or 'None'}")
                c_del, c_int = st.columns(2)
                d_reason = c_del.text_input("Delay Reason", value=job.get('delay_reason') or '', key=f"d_{job['id']}")
                i_note = c_int.text_area("Intervention Note", value=job.get('intervention_note') or '', key=f"n_{job['id']}")
                
                if job['status'] == "Pending":
                    mode = st.radio("Allocation Mode", ["In-House", "Outsource"], key=f"mode_{job['id']}", horizontal=True)
                    if mode == "In-House":
                        c1, c2 = st.columns(2)
                        m = c1.selectbox(f"Select {RES_LABEL}", resource_list, key=f"m_{job['id']}")
                        o = c2.selectbox("Select Operator", operator_list, key=f"o_{job['id']}")
                        if st.button("🚀 Allot to Production", key=f"btn_in_{job['id']}", use_container_width=True):
                            conn.table(DB_TABLE).update({"status": "In-House", "machine_id": m, "operator_id": o, "delay_reason": d_reason, "intervention_note": i_note}).eq("id", job['id']).execute(); st.rerun()
                    else:
                        c1, c2, c3 = st.columns(3)
                        v = c1.selectbox("Select Vendor", vendor_list, key=f"v_{job['id']}")
                        vh = c2.selectbox("Vehicle No", vehicle_list, key=f"vh_{job['id']}")
                        gp = c3.text_input("Gatepass No", key=f"gp_{job['id']}")
                        if st.button("🚚 Dispatch Outward", key=f"btn_out_{job['id']}", use_container_width=True):
                            conn.table(DB_TABLE).update({"status": "Outsourced", "vendor_id": v, "vehicle_no": vh, "gatepass_no": gp, "delay_reason": d_reason, "intervention_note": i_note}).eq("id", job['id']).execute(); st.rerun()
                elif job['status'] == "Outsourced":
                    wb = st.text_input("Waybill / Return DC No", key=f"wb_{job['id']}")
                    if st.button("✅ Mark as Received & Finished", key=f"btn_fin_out_{job['id']}", use_container_width=True):
                        conn.table(DB_TABLE).update({"status": "Finished", "waybill_no": wb, "delay_reason": d_reason, "intervention_note": i_note}).eq("id", job['id']).execute(); st.rerun()
                elif job['status'] == "In-House":
                    if st.button("🏁 Mark Work Completed", key=f"btn_fin_in_{job['id']}", use_container_width=True):
                        conn.table(DB_TABLE).update({"status": "Finished", "delay_reason": d_reason, "intervention_note": i_note}).eq("id", job['id']).execute(); st.rerun()
    else: st.warning("🔒 Please enter the Incharge Pin to unlock actions.")

# --- TAB 3: EXECUTIVE ANALYTICS (RESTORED REPORTING) ---
with tab_analytics:
    if all_data:
        df = pd.DataFrame(all_data)
        st.error("### 🚨 High Priority Active Jobs")
        urgent = df[(df['priority'].isin(['URGENT', 'High'])) & (df['status'] != 'Finished')]
        st.dataframe(urgent[['job_code', 'part_name', 'status', 'required_date', 'delay_reason']], use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("📥 Export Production Data")
        # Fix for Excel Export: Remove Timezones
        report_df = df.copy()
        for col in report_df.columns:
            if pd.api.types.is_datetime64_any_dtype(report_df[col]):
                report_df[col] = report_df[col].dt.tz_localize(None)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            report_df.to_excel(writer, index=False, sheet_name='ERP_Export')
        st.download_button(label="📂 Download Full Excel Report", data=buffer.getvalue(), file_name=f"BG_Report_{datetime.date.today()}.xlsx", mime="application/vnd.ms-excel")

# --- TAB 4: LOGBOOK ---
with tab_log:
    st.dataframe(all_data, use_container_width=True)

# --- TAB 5: MASTERS (RESTORED ADD/DELETE LOGIC) ---
with tab_masters:
    admin_pin = st.text_input("Admin Pin", type="password", key="adm_pin")
    if admin_pin == "1234":
        col_map = {MASTER_TABLE: MASTER_COL, "beta_operator_master": "operator_name", "beta_vendor_master": "vendor_name", "beta_vehicle_master": "vehicle_number"}
        
        st.write("### ➕ Add New Resource")
        c1, c2, c3 = st.columns([2, 2, 1])
        add_cat = c1.selectbox("Table", list(col_map.keys()), key="add_cat")
        new_val = c2.text_input("Name/Value", key="add_val")
        if c3.button("➕ Add"):
            if new_val: conn.table(add_cat).insert({col_map[add_cat]: new_val}).execute(); st.rerun()

        st.divider()
        st.write("### 🗑️ Remove Resource")
        d1, d2, d3 = st.columns([2, 2, 1])
        del_cat = d1.selectbox("Table", list(col_map.keys()), key="del_cat")
        # Dynamic fetch for delete list
        current_items = [r[col_map[del_cat]] for r in conn.table(del_cat).select(col_map[del_cat]).execute().data or []]
        to_del = d2.selectbox("Item to Remove", current_items, key="del_val")
        if d3.button("🗑️ Delete"):
            if to_del: conn.table(del_cat).delete().eq(col_map[del_cat], to_del).execute(); st.rerun()
