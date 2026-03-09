import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
from datetime import datetime

# 1. Setup
st.set_page_config(page_title="B&G Enterprise ERP", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)

if 'hub' not in st.session_state:
    st.session_state.hub = "Machining Hub"

# --- HUB SELECTION ---
st.write("### 🏢 Select Department")
c1, c2 = st.columns(2)
if c1.button("⚙️ MACHINING HUB", use_container_width=True, type="primary" if st.session_state.hub == "Machining Hub" else "secondary"):
    st.session_state.hub = "Machining Hub"; st.rerun()
if c2.button("✨ BUFFING & POLISHING", use_container_width=True, type="primary" if st.session_state.hub == "Buffing & Polishing" else "secondary"):
    st.session_state.hub = "Buffing & Polishing"; st.rerun()

# --- DYNAMIC CONFIG ---
if st.session_state.hub == "Machining Hub":
    DB_TABLE, RES_MASTER, RES_LABEL, RES_COL = "beta_machining_logs", "beta_machine_master", "Machine", "machine_name"
    ACTIVITY_LIST = ["Turning", "Drilling", "Milling", "Keyway", "Tapping", "Boring"]
else:
    DB_TABLE, RES_MASTER, RES_LABEL, RES_COL = "beta_buffing_logs", "beta_buffing_station_master", "Buffing Station", "station_name"
    ACTIVITY_LIST = ["Rough Buffing", "Mirror Polishing", "Satin Finish", "RA Value Check"]

# 2. Data Fetching
def fetch_data():
    try:
        logs = conn.table(DB_TABLE).select("*").order("created_at", desc=True).execute().data or []
        res = conn.table(RES_MASTER).select(RES_COL).execute().data or []
        ops = conn.table("beta_operator_master").select("operator_name").execute().data or []
        vends = conn.table("beta_vendor_master").select("vendor_name").execute().data or []
        return logs, [r[RES_COL] for r in res], [o['operator_name'] for o in ops], [v['vendor_name'] for v in vends]
    except: return [], [], [], []

all_logs, resource_list, operator_list, vendor_list = fetch_data()

t_prod, t_inch, t_exec, t_masters = st.tabs(["📝 Request & Live", "👨‍💻 Incharge Desk", "📋 Executive Analysis", "🛠️ Masters"])

# --- TAB 1: PRODUCTION ---
with t_prod:
    with st.form(key=f"f_{st.session_state.hub}", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        u_no, j_code = col1.selectbox("Unit", [1, 2, 3]), col1.text_input("Job Code")
        part, act = col2.text_input("Part Name"), col2.selectbox("Process", ACTIVITY_LIST)
        r_date, prio = col3.date_input("Required Date"), col3.selectbox("Priority", ["Low", "Medium", "High", "URGENT"])
        notes = st.text_area("🗒️ Special Production Notes")
        
        if st.form_submit_button("Submit Request"):
            if j_code:
                conn.table(DB_TABLE).insert({
                    "unit_no": u_no, "job_code": j_code, "part_name": part, "activity_type": act, 
                    "priority": prio, "status": "Pending", "request_date": str(datetime.now().date()), 
                    "required_date": str(r_date), "special_notes": notes
                }).execute(); st.rerun()

    st.subheader("🚦 Shop Floor Status")
    if all_logs:
        df = pd.DataFrame(all_logs)
        df_live = df[df['status'] != "Finished"].copy()
        if not df_live.empty:
            df_live['required_date'] = pd.to_datetime(df_live['required_date'])
            df_live['Days Left'] = (df_live['required_date'] - pd.Timestamp(datetime.now().date())).dt.days
            # Full column visibility restored
            disp_cols = ['unit_no', 'job_code', 'part_name', 'request_date', 'required_date', 'Days Left', 'priority', 'status', 'special_notes']
            st.dataframe(df_live[disp_cols], use_container_width=True, hide_index=True)

# --- TAB 2: INCHARGE DESK (RESTORED LOGIC) ---
with t_inch:
    pending = [j for j in all_logs if j['status'] != "Finished"]
    for j in pending:
        with st.expander(f"UNIT {j['unit_no']} | JOB: {j['job_code']} | Req: {j.get('required_date')} | {j['status']}"):
            if j.get('special_notes'): st.warning(f"Note: {j['special_notes']}")
            
            m_type = st.radio("Execution Path:", ["In-House Team", "Outsource / Contractor"], key=f"m{j['id']}", horizontal=True)
            
            c1, c2, c3 = st.columns(3)
            # LOGIC RESTORED: Resource vs Vendor
            res_val = c1.selectbox(f"Select {RES_LABEL}", resource_list, key=f"res{j['id']}")
            
            if m_type == "In-House Team":
                worker = c2.selectbox("Assign Operator", operator_list, key=f"op{j['id']}")
                gp, wb = None, None
            else:
                worker = c2.selectbox("Select Vendor", vendor_list, key=f"vn{j['id']}")
                gp = c3.text_input("Gate Pass No.", key=f"gp{j['id']}")
                wb = c3.text_input("Waybill No.", key=f"wb{j['id']}")

            if st.button("🚀 Authorize & Start", key=f"btn{j['id']}", use_container_width=True):
                upd = {
                    "status": "In-House" if m_type == "In-House Team" else "Outsourced",
                    "machine_id": res_val,
                    "operator_id": worker if m_type == "In-House Team" else None,
                    "vendor_id": worker if m_type == "Outsource / Contractor" else None,
                    "gate_pass_no": gp,
                    "waybill_no": wb
                }
                conn.table(DB_TABLE).update(upd).eq("id", j['id']).execute(); st.rerun()
            
            if j['status'] in ["In-House", "Outsourced"]:
                if st.button("🏁 Mark as Finished", key=f"fin{j['id']}", use_container_width=True):
                    conn.table(DB_TABLE).update({"status": "Finished"}).eq("id", j['id']).execute(); st.rerun()

# --- TAB 3: EXECUTIVE ANALYSIS ---
with t_exec:
    if all_logs:
        df_e = pd.DataFrame(all_logs)
        st.subheader("📊 Load Analysis")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total", len(df_e))
        c2.metric("WIP", len(df_e[df_e['status'] != 'Finished']))
        c3.metric("Lagging", len(df_e[(pd.to_datetime(df_e['required_date']) < pd.Timestamp(datetime.now().date())) & (df_e['status'] != 'Finished')]))
        
        st.markdown("#### 📖 Detailed Audit Log (Includes Logistics)")
        st.dataframe(df_e, use_container_width=True)
        st.download_button("📥 Download ERP Data", df_e.to_csv(index=False).encode('utf-8'), f"BG_{st.session_state.hub}.csv")

# --- TAB 4: MASTERS ---
with t_masters:
    col1, col2 = st.columns(2)
    with col1:
        new_res = st.text_input(f"New {RES_LABEL}")
        if st.button(f"Add {RES_LABEL}"): conn.table(RES_MASTER).insert({RES_COL: new_res}).execute(); st.rerun()
    with col2:
        m_cat = st.selectbox("Category", ["Operator", "Vendor"])
        m_name = st.text_input("Name")
        if st.button("Save to Masters"):
            tbl = "beta_operator_master" if m_cat == "Operator" else "beta_vendor_master"
            col = "operator_name" if m_cat == "Operator" else "vendor_name"
            conn.table(tbl).insert({col: m_name}).execute(); st.rerun()
