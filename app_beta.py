import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import datetime
import io

# 1. Initialize Connection & Page Config
st.set_page_config(page_title="B&G ERP BETA", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)

# --- CUSTOM CSS FOR ROUND BUTTON BARS ---
st.markdown("""
    <style>
    div.stButton > button {
        border-radius: 20px;
        border: 1px solid #ccc;
        transition: all 0.3s;
    }
    div.stButton > button:hover {
        border-color: #ff4b4b;
        color: #ff4b4b;
    }
    </style>
""", unsafe_allow_index=True)

if 'hub' not in st.session_state:
    st.session_state.hub = "Machining Hub"

# --- HUB SELECTION BAR (ROUND BUTTONS) ---
st.write("### 🏢 Select Department")
c1, c2, c3 = st.columns([1, 1, 2])
if c1.button("⚙️ Machining Hub", use_container_width=True, type="primary" if st.session_state.hub == "Machining Hub" else "secondary"):
    st.session_state.hub = "Machining Hub"
    st.rerun()
if c2.button("✨ Buffing Hub", use_container_width=True, type="primary" if st.session_state.hub == "Buffing Hub" else "secondary"):
    st.session_state.hub = "Buffing Hub"
    st.rerun()

st.divider()
st.title(f"📍 {st.session_state.hub}")

# --- DYNAMIC CONFIGURATION ---
if st.session_state.hub == "Machining Hub":
    DB_TABLE, MASTER_TABLE, MASTER_COL, RES_LABEL = "beta_machining_logs", "beta_machine_master", "machine_name", "Machine"
    ACTIVITIES = ["Turning", "Drilling", "Milling", "Keyway", "Dishbending"]
else:
    DB_TABLE, MASTER_TABLE, MASTER_COL, RES_LABEL = "beta_buffing_logs", "beta_buffing_station_master", "station_name", "Buffing Station"
    ACTIVITIES = ["Rough Buffing", "Mirror Polishing", "Satin Finish", "RA Value Check"]

# 2. Data Fetching
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

# --- TAB 1: PRODUCTION ---
with tab_prod:
    with st.form("prod_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        u_no, j_code = c1.selectbox("Unit No", [1, 2, 3]), c1.text_input("Job Code")
        part, act = c2.text_input("Part Name"), c2.selectbox("Activity", ACTIVITIES)
        req_date, prio = c3.date_input("Required Date"), c3.selectbox("Priority", ["Low", "Medium", "High", "URGENT"])
        notes = st.text_area("🗒️ Special Production Notes")
        if st.form_submit_button("Submit Request"):
            if j_code and part:
                conn.table(DB_TABLE).insert({"unit_no": u_no, "job_code": j_code, "part_name": part, "activity_type": act, "required_date": str(req_date), "request_date": str(datetime.date.today()), "priority": prio, "status": "Pending", "special_notes": notes}).execute()
                st.rerun()

    st.subheader("🚦 Current Shop Floor Status")
    if all_data:
        df_status = pd.DataFrame(all_data)
        # FIX: Handle potential Null dates and avoid TypeError
        df_status['required_date'] = pd.to_datetime(df_status['required_date'], errors='coerce')
        
        # Calculate Days Left safely
        today = pd.Timestamp(datetime.date.today())
        df_status['Days Left'] = (df_status['required_date'] - today).dt.days
        
        unit_sel = st.radio("View Unit", [1, 2, 3], horizontal=True)
        unit_view = df_status[df_status['unit_no'] == unit_sel].copy()
        
        disp_cols = ['job_code', 'part_name', 'status', 'priority', 'request_date', 'required_date', 'Days Left', 'special_notes']
        st.dataframe(unit_view[disp_cols], use_container_width=True, hide_index=True)

# --- TAB 2: INCHARGE DESK (RESTORED LOGISTICS) ---
with tab_incharge:
    auth_code = st.text_input("Incharge Pin", type="password")
    if auth_code == "1234":
        active_jobs = [j for j in all_data if j['status'] != "Finished"]
        for job in active_jobs:
            with st.expander(f"Unit {job['unit_no']} | {job['job_code']} - {job['part_name']}"):
                st.write(f"**PPC Req:** {job.get('required_date')} | **Notes:** {job.get('special_notes') or 'N/A'}")
                c_del, c_int = st.columns(2)
                d_reason = c_del.text_input("Delay Reason", value=job.get('delay_reason') or '', key=f"d_{job['id']}")
                i_note = c_int.text_area("Intervention Note", value=job.get('intervention_note') or '', key=f"n_{job['id']}")
                
                if job['status'] == "Pending":
                    mode = st.radio("Path", ["In-House", "Outsource"], key=f"m_{job['id']}", horizontal=True)
                    if mode == "In-House":
                        c1, c2 = st.columns(2)
                        m = c1.selectbox(f"Assign {RES_LABEL}", resource_list, key=f"res_{job['id']}")
                        o = c2.selectbox("Assign Operator", operator_list, key=f"op_{job['id']}")
                        if st.button("🚀 Start Production", key=f"b1_{job['id']}"):
                            conn.table(DB_TABLE).update({"status": "In-House", "machine_id": m, "operator_id": o, "delay_reason": d_reason, "intervention_note": i_note}).eq("id", job['id']).execute(); st.rerun()
                    else:
                        c1, c2, c3 = st.columns(3)
                        v, vh = c1.selectbox("Vendor", vendor_list, key=f"v_{job['id']}"), c2.selectbox("Vehicle", vehicle_list, key=f"vh_{job['id']}")
                        gp = c3.text_input("Gatepass No", key=f"gp_{job['id']}")
                        if st.button("🚚 Dispatch", key=f"b2_{job['id']}"):
                            conn.table(DB_TABLE).update({"status": "Outsourced", "vendor_id": v, "vehicle_no": vh, "gatepass_no": gp, "delay_reason": d_reason, "intervention_note": i_note}).eq("id", job['id']).execute(); st.rerun()
                
                elif job['status'] == "Outsourced":
                    wb = st.text_input("Waybill / Return DC", key=f"wb_{job['id']}")
                    if st.button("✅ Mark Received", key=f"b3_{job['id']}"):
                        conn.table(DB_TABLE).update({"status": "Finished", "waybill_no": wb, "delay_reason": d_reason, "intervention_note": i_note}).eq("id", job['id']).execute(); st.rerun()
                
                elif job['status'] == "In-House":
                    if st.button("🏁 Mark Finished", key=f"b4_{job['id']}"):
                        conn.table(DB_TABLE).update({"status": "Finished", "delay_reason": d_reason, "intervention_note": i_note}).eq("id", job['id']).execute(); st.rerun()
