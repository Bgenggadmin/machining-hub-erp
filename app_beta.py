import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import datetime
import io

# 1. Initialize Connection & Page Config
st.set_page_config(page_title="B&G ERP BETA", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)

# --- CSS FOR ROUND PILL BUTTONS ---
st.markdown("""
    <style>
    div.stButton > button { border-radius: 50px; font-weight: 600; }
    </style>
""", unsafe_allow_html=True)

if 'hub' not in st.session_state:
    st.session_state.hub = "Machining Hub"

# --- HUB SELECTION ---
c1, c2, _ = st.columns([1, 1, 2])
if c1.button("⚙️ MACHINING HUB", use_container_width=True, type="primary" if st.session_state.hub == "Machining Hub" else "secondary"):
    st.session_state.hub = "Machining Hub"; st.rerun()
if c2.button("✨ BUFFING HUB", use_container_width=True, type="primary" if st.session_state.hub == "Buffing Hub" else "secondary"):
    st.session_state.hub = "Buffing Hub"; st.rerun()

# --- DYNAMIC CONFIG ---
if st.session_state.hub == "Machining Hub":
    DB_TABLE, MASTER_TABLE, MASTER_COL, RES_LABEL = "beta_machining_logs", "beta_machine_master", "machine_name", "Machine"
    ACTIVITIES = ["Turning", "Drilling", "Milling", "Keyway", "Dishbending"]
else:
    DB_TABLE, MASTER_TABLE, MASTER_COL, RES_LABEL = "beta_buffing_logs", "beta_buffing_station_master", "station_name", "Buffing Station"
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

# --- TAB 1: PRODUCTION REQUEST & LIVE (Unchanged) ---
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
                conn.table(DB_TABLE).insert({"unit_no": u_no, "job_code": j_code, "part_name": part, "activity_type": act, "required_date": str(req_date), "request_date": str(datetime.date.today()), "priority": prio, "status": "Pending", "special_notes": notes}).execute(); st.rerun()

    st.divider()
    if all_data:
        df_status = pd.DataFrame(all_data)
        df_status['required_date'] = pd.to_datetime(df_status['required_date'], errors='coerce')
        df_status['Days Left'] = (df_status['required_date'] - pd.Timestamp(datetime.date.today())).dt.days
        unit_sel = st.radio("View Unit", [1, 2, 3], horizontal=True)
        st.dataframe(df_status[df_status['unit_no'] == unit_sel][['job_code', 'part_name', 'status', 'priority', 'required_date', 'Days Left', 'special_notes']], use_container_width=True, hide_index=True)

# --- TAB 2: INCHARGE DESK (RESTORED LOGISTICS & PIN) ---
with tab_incharge:
    auth_code = st.text_input("Enter Incharge Pin", type="password", key="inch_pin")
    if auth_code == "1234":
        active_jobs = [j for j in all_data if j['status'] != "Finished"]
        for job in active_jobs:
            p_marker = {"URGENT": "🔴", "High": "🟠", "Medium": "🟡", "Low": "⚪"}.get(job['priority'], "⚪")
            with st.expander(f"{p_marker} Unit {job['unit_no']} | {job['job_code']} - {job['part_name']}"):
                c_del, c_int = st.columns(2)
                d_reason = c_del.text_input("Delay Reason", value=job.get('delay_reason') or '', key=f"d_{job['id']}")
                i_note = c_int.text_area("Intervention Note", value=job.get('intervention_note') or '', key=f"n_{job['id']}")
                
                if job['status'] == "Pending":
                    mode = st.radio("Path", ["In-House", "Outsource"], key=f"mode_{job['id']}", horizontal=True)
                    if mode == "In-House":
                        c1, c2 = st.columns(2)
                        m, o = c1.selectbox(f"Select {RES_LABEL}", resource_list, key=f"m_{job['id']}"), c2.selectbox("Select Operator", operator_list, key=f"o_{job['id']}")
                        if st.button("🚀 Allot", key=f"btn_in_{job['id']}", use_container_width=True):
                            conn.table(DB_TABLE).update({"status": "In-House", "machine_id": m, "operator_id": o, "delay_reason": d_reason, "intervention_note": i_note}).eq("id", job['id']).execute(); st.rerun()
                    else:
                        c1, c2, c3 = st.columns(3)
                        v, vh, gp = c1.selectbox("Vendor", vendor_list, key=f"v_{job['id']}"), c2.selectbox("Vehicle", vehicle_list, key=f"vh_{job['id']}"), c3.text_input("Gatepass No", key=f"gp_{job['id']}")
                        if st.button("🚚 Dispatch", key=f"btn_out_{job['id']}", use_container_width=True):
                            conn.table(DB_TABLE).update({"status": "Outsourced", "vendor_id": v, "vehicle_no": vh, "gatepass_no": gp, "delay_reason": d_reason, "intervention_note": i_note}).eq("id", job['id']).execute(); st.rerun()
                elif job['status'] == "Outsourced":
                    wb = st.text_input("Waybill No", key=f"wb_{job['id']}")
                    if st.button("✅ Received", key=f"btn_fin_out_{job['id']}", use_container_width=True):
                        conn.table(DB_TABLE).update({"status": "Finished", "waybill_no": wb, "delay_reason": d_reason, "intervention_note": i_note}).eq("id", job['id']).execute(); st.rerun()
                elif job['status'] == "In-House":
                    if st.button("🏁 Finish", key=f"btn_fin_in_{job['id']}", use_container_width=True):
                        conn.table(DB_TABLE).update({"status": "Finished", "delay_reason": d_reason, "intervention_note": i_note}).eq("id", job['id']).execute(); st.rerun()
    else: st.warning("🔒 Enter Incharge Pin.")

# --- TAB 3: EXECUTIVE ANALYTICS (EXPANDED FIELDS) ---
with tab_analytics:
    if all_data:
        df = pd.DataFrame(all_data)
        df['required_date'] = pd.to_datetime(df['required_date'], errors='coerce')
        
        # 1. Summary Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Jobs", len(df))
        m2.metric("In-House WIP", len(df[df['status'] == 'In-House']))
        m3.metric("Outsourced", len(df[df['status'] == 'Outsourced']))
        m4.metric("Pending Allotment", len(df[df['status'] == 'Pending']))

        # 2. Expanded View: Logistics & Delay Tracker
        st.write("### 🚛 Vendor & Logistics Tracker")
        v_df = df[df['status'] == 'Outsourced'].copy()
        if not v_df.empty:
            st.dataframe(v_df[['job_code', 'part_name', 'vendor_id', 'vehicle_no', 'gatepass_no', 'required_date', 'delay_reason']], use_container_width=True, hide_index=True)
        else: st.info("No jobs currently at vendors.")

        # 3. Expanded View: Machine/Station Load
        st.write(f"### ⚙️ {RES_LABEL} Load Analysis")
        load_df = df[df['status'] == 'In-House'].copy()
        if not load_df.empty:
            st.dataframe(load_df[['machine_id', 'job_code', 'part_name', 'operator_id', 'priority', 'intervention_note']], use_container_width=True, hide_index=True)
        else: st.info(f"No active jobs on {RES_LABEL}s.")

        # 4. Urgent/High Priority (Maintained from Master)
        st.error("### 🚨 Urgent & High Priority Action List")
        urgent = df[(df['priority'].isin(['URGENT', 'High'])) & (df['status'] != 'Finished')]
        st.dataframe(urgent[['job_code', 'part_name', 'status', 'required_date', 'delay_reason', 'special_notes']], use_container_width=True, hide_index=True)

        st.divider()
        # Export Logic (Maintained)
        report_df = df.copy()
        for col in report_df.columns:
            if pd.api.types.is_datetime64_any_dtype(report_df[col]): report_df[col] = report_df[col].dt.tz_localize(None)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer: report_df.to_excel(writer, index=False, sheet_name='ERP_Export')
        st.download_button("📂 Download Full Excel Report", data=buffer.getvalue(), file_name=f"BG_Analytics_{datetime.date.today()}.xlsx")

# --- TAB 5: MASTERS (Unchanged) ---
with tab_masters:
    admin_pin = st.text_input("Admin Pin", type="password", key="adm_pin")
    if admin_pin == "1234":
        col_map = {MASTER_TABLE: MASTER_COL, "beta_operator_master": "operator_name", "beta_vendor_master": "vendor_name", "beta_vehicle_master": "vehicle_number"}
        st.write("### ➕ Add Resource")
        c1, c2, c3 = st.columns([2, 2, 1])
        add_cat = c1.selectbox("Table", list(col_map.keys()), key="add_cat")
        new_val = c2.text_input("Name", key="add_val")
        if c3.button("➕ Add"):
            if new_val: conn.table(add_cat).insert({col_map[add_cat]: new_val}).execute(); st.rerun()
        st.divider()
        st.write("### 🗑️ Remove Resource")
        d1, d2, d3 = st.columns([2, 2, 1])
        del_cat = d1.selectbox("Table", list(col_map.keys()), key="del_cat")
        current_items = [r[col_map[del_cat]] for r in conn.table(del_cat).select(col_map[del_cat]).execute().data or []]
        to_del = d2.selectbox("Item", current_items, key="del_val")
        if d3.button("🗑️ Delete"):
            if to_del: conn.table(del_cat).delete().eq(col_map[del_cat], to_del).execute(); st.rerun()
