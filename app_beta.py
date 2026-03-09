import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import datetime
import io

# 1. Setup & Style
st.set_page_config(page_title="B&G ERP BETA", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)

st.markdown("""<style>div.stButton > button { border-radius: 50px; font-weight: 600; }</style>""", unsafe_allow_html=True)

if 'hub' not in st.session_state:
    st.session_state.hub = "Machining Hub"

# --- HUB SELECTION ---
c1, c2, _ = st.columns([1, 1, 2])
if c1.button("⚙️ MACHINING HUB", use_container_width=True, type="primary" if st.session_state.hub == "Machining Hub" else "secondary"):
    st.session_state.hub = "Machining Hub"; st.rerun()
if c2.button("✨ BUFFING HUB", use_container_width=True, type="primary" if st.session_state.hub == "Buffing Hub" else "secondary"):
    st.session_state.hub = "Buffing Hub"; st.rerun()

# --- CONFIGURATION (Syncing with your actual DB names) ---
if st.session_state.hub == "Machining Hub":
    DB_TABLE, MASTER_TABLE, MASTER_COL, RES_LABEL = "beta_machining_logs", "beta_machine_master", "machine_name", "Machine"
    ACTIVITIES = ["Turning", "Drilling", "Milling", "Keyway", "Dishbending"]
else:
    DB_TABLE, MASTER_TABLE, MASTER_COL, RES_LABEL = "beta_buffing_logs", "beta_buffing_station_master", "station_name", "Buffing Station"
    ACTIVITIES = ["Rough Buffing", "Mirror Polishing", "Satin Finish", "RA Value Check"]

# Correcting Master Table Names based on your Error Hint
OP_MASTER = "operator_master"
VN_MASTER = "vendor_master"
VH_MASTER = "vehicle_master"

# 2. Robust Data Fetching
def get_all_data():
    try:
        # Fetch Masters using the verified table names
        m_data = conn.table(MASTER_TABLE).select(MASTER_COL).execute().data or []
        o_data = conn.table(OP_MASTER).select("operator_name").execute().data or []
        v_data = conn.table(VN_MASTER).select("vendor_name").execute().data or []
        vh_data = conn.table(VH_MASTER).select("vehicle_number").execute().data or []
        
        # Fetch Logs
        logs = conn.table(DB_TABLE).select("*").order("created_at", desc=True).execute().data or []
        
        # Convert to DataFrame and SANITIZE
        df = pd.DataFrame(logs)
        required_cols = ['id', 'status', 'job_code', 'part_name', 'priority', 'required_date', 
                         'machine_id', 'operator_id', 'vendor_id', 'vehicle_no', 'gatepass_no', 'waybill_no',
                         'delay_reason', 'intervention_note', 'special_notes']
        
        if df.empty:
            df = pd.DataFrame(columns=required_cols)
        else:
            for col in required_cols:
                if col not in df.columns:
                    df[col] = None
        
        return [r[MASTER_COL] for r in m_data], [o['operator_name'] for o in o_data], \
               [v['vendor_name'] for v in v_data], [vh['vehicle_number'] for vh in vh_data], df
    except Exception as e:
        st.error(f"Data Sync Error: {e}")
        return [], [], [], [], pd.DataFrame()

resource_list, operator_list, vendor_list, vehicle_list, df_main = get_all_data()

tabs = st.tabs(["📝 Production Request", "👨‍💻 Incharge Entry Desk", "📊 Executive Analytics", "🛠️ Masters"])

# --- TAB 1: PRODUCTION REQUEST ---
with tabs[0]:
    with st.form("req_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        u_no, j_code = c1.selectbox("Unit", [1, 2, 3]), c1.text_input("Job Code")
        part, act = c2.text_input("Part Name"), c2.selectbox("Activity", ACTIVITIES)
        req_d, prio = c3.date_input("Required Date"), c3.selectbox("Priority", ["Low", "Medium", "High", "URGENT"])
        notes = st.text_area("Special Notes")
        if st.form_submit_button("Submit Request"):
            if j_code and part:
                conn.table(DB_TABLE).insert({"unit_no": u_no, "job_code": j_code, "part_name": part, "activity_type": act, "required_date": str(req_d), "status": "Pending", "special_notes": notes}).execute(); st.rerun()

# --- TAB 2: INCHARGE ENTRY DESK (LOGISTICS) ---
with tabs[1]:
    if not df_main.empty:
        active_jobs = df_main[df_main['status'] != "Finished"].to_dict('records')
        if not active_jobs:
            st.info("No active jobs currently.")
        
        for job in active_jobs:
            with st.expander(f"📌 {job['job_code']} - {job['part_name']} ({job['status']})"):
                c_del, c_int = st.columns(2)
                d_r = c_del.text_input("Delay Reason", value=job['delay_reason'] or '', key=f"dr_{job['id']}")
                i_n = c_int.text_area("Incharge Note", value=job['intervention_note'] or '', key=f"in_{job['id']}")
                
                if job['status'] == "Pending":
                    mode = st.radio("Allotment", ["In-House", "Outsource"], key=f"m_{job['id']}", horizontal=True)
                    if mode == "In-House":
                        c1, c2 = st.columns(2)
                        m = c1.selectbox(f"Assign {RES_LABEL}", resource_list, key=f"m_sel_{job['id']}")
                        o = c2.selectbox("Assign Operator", operator_list, key=f"o_sel_{job['id']}")
                        if st.button("🚀 Start In-House", key=f"b_ih_{job['id']}", use_container_width=True):
                            conn.table(DB_TABLE).update({"status": "In-House", "machine_id": m, "operator_id": o, "delay_reason": d_r, "intervention_note": i_n}).eq("id", job['id']).execute(); st.rerun()
                    else:
                        c1, c2, c3 = st.columns(3)
                        v = c1.selectbox("Vendor", vendor_list, key=f"v_sel_{job['id']}")
                        vh = c2.selectbox("Vehicle", vehicle_list, key=f"vh_sel_{job['id']}")
                        gp = c3.text_input("Gatepass No", key=f"gp_{job['id']}")
                        if st.button("🚚 Dispatch to Vendor", key=f"b_os_{job['id']}", use_container_width=True):
                            conn.table(DB_TABLE).update({"status": "Outsourced", "vendor_id": v, "vehicle_no": vh, "gatepass_no": gp, "delay_reason": d_r, "intervention_note": i_n}).eq("id", job['id']).execute(); st.rerun()
                
                elif job['status'] == "Outsourced":
                    wb = st.text_input("Return Waybill No", key=f"wb_{job['id']}")
                    if st.button("✅ Mark Received", key=f"b_rc_{job['id']}", use_container_width=True):
                        conn.table(DB_TABLE).update({"status": "Finished", "waybill_no": wb, "delay_reason": d_r, "intervention_note": i_n}).eq("id", job['id']).execute(); st.rerun()
                
                else: # In-House
                    if st.button("🏁 Mark Finished", key=f"b_fi_{job['id']}", use_container_width=True):
                        conn.table(DB_TABLE).update({"status": "Finished", "delay_reason": d_r, "intervention_note": i_n}).eq("id", job['id']).execute(); st.rerun()

# --- TAB 3: EXECUTIVE ANALYTICS ---
with tabs[2]:
    if not df_main.empty:
        st.write("### 🌍 Shop Floor Overview")
        ih_df = df_main[df_main['status'] == 'In-House']
        st.write(f"**Current {RES_LABEL} Load**")
        st.dataframe(ih_df[['job_code', 'machine_id', 'operator_id', 'priority', 'delay_reason']], use_container_width=True, hide_index=True)
        
        os_df = df_main[df_main['status'] == 'Outsourced']
        st.write("**Vendor Logistics Tracking**")
        st.dataframe(os_df[['job_code', 'vendor_id', 'vehicle_no', 'gatepass_no', 'required_date']], use_container_width=True, hide_index=True)
        
        st.divider()
        st.write("**Complete Transaction Log**")
        st.dataframe(df_main, use_container_width=True)

# --- TAB 4: MASTERS ---
with tabs[3]:
    cmap = {MASTER_TABLE: MASTER_COL, OP_MASTER: "operator_name", VN_MASTER: "vendor_name", VH_MASTER: "vehicle_number"}
    c1, c2, c3 = st.columns([2, 2, 1])
    cat = c1.selectbox("Category", list(cmap.keys()))
    val = c2.text_input("Name")
    if c3.button("➕ Add Entry"):
        if val: conn.table(cat).insert({cmap[cat]: val}).execute(); st.rerun()
