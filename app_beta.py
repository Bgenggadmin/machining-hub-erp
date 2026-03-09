import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
from datetime import datetime

# 1. Page Config & Connection
st.set_page_config(page_title="B&G Enterprise Hub", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)

if 'hub' not in st.session_state:
    st.session_state.hub = "Machining Hub"

# --- HUB SELECTION ---
st.write("### 🏢 Department Selection")
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

# --- TAB 1: PRODUCTION & LIVE STATUS ---
with t_prod:
    st.subheader(f"New {st.session_state.hub} Request")
    with st.form(key=f"f_{st.session_state.hub}", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        u_no, j_code = col1.selectbox("Unit", [1, 2, 3]), col1.text_input("Job Code")
        part, act = col2.text_input("Part Name"), col2.selectbox("Process", ACTIVITY_LIST)
        r_date, prio = col3.date_input("Required Delivery Date"), col3.selectbox("Priority", ["Low", "Medium", "High", "URGENT"])
        
        # --- INPUT FIELD FOR NOTES ---
        notes = st.text_area("🗒️ Special Production Notes", placeholder="Enter specific instructions, material issues, or tooling requirements...")
        
        if st.form_submit_button("Submit Request"):
            if j_code and part:
                conn.table(DB_TABLE).insert({
                    "unit_no": u_no, "job_code": j_code, "part_name": part, 
                    "activity_type": act, "priority": prio, "status": "Pending", 
                    "request_date": str(datetime.now().date()), "required_date": str(r_date),
                    "special_notes": notes
                }).execute(); st.rerun()

    st.divider()
    st.subheader("🚦 Shop Floor Status (Live)")
    if all_logs:
        df = pd.DataFrame(all_logs)
        df_live = df[df['status'] != "Finished"].copy()
        if not df_live.empty:
            df_live['required_date'] = pd.to_datetime(df_live['required_date'])
            df_live['Days Left'] = (df_live['required_date'] - pd.Timestamp(datetime.now().date())).dt.days
            
            # --- DISPLAYING SPECIAL NOTES IN THE MAIN TABLE ---
            st.dataframe(
                df_live[['unit_no', 'job_code', 'part_name', 'status', 'Days Left', 'priority', 'special_notes']], 
                use_container_width=True, hide_index=True
            )
        else: st.info("Shop floor is currently clear.")

# --- TAB 2: INCHARGE DESK ---
with t_inch:
    pending = [j for j in all_logs if j['status'] != "Finished"]
    for j in pending:
        # Show Notes in the Expander so Incharge can see them immediately
        note_display = f" | 🗒️: {j['special_notes']}" if j.get('special_notes') else ""
        with st.expander(f"Unit {j['unit_no']} | {j['job_code']}{note_display}"):
            m = st.radio("Manpower Type:", ["Own", "Contractor"], key=f"m{j['id']}", horizontal=True)
            c1, c2 = st.columns(2)
            r_sel = c1.selectbox(f"Assign {RES_LABEL}", resource_list, key=f"r{j['id']}")
            w_sel = c2.selectbox("Assign Person/Agency", operator_list if m=="Own" else vendor_list, key=f"w{j['id']}")
            
            b1, b2 = st.columns(2)
            if b1.button("🚀 Start Production", key=f"s{j['id']}", use_container_width=True):
                upd = {"status": "In-House" if m=="Own" else "Outsourced", "machine_id": r_sel}
                if m=="Own": upd["operator_id"] = w_sel
                else: upd["vendor_id"] = w_sel
                conn.table(DB_TABLE).update(upd).eq("id", j['id']).execute(); st.rerun()
            if j['status'] in ["In-House", "Outsourced"] and b2.button("🏁 Finish Job", key=f"f{j['id']}", use_container_width=True):
                conn.table(DB_TABLE).update({"status": "Finished"}).eq("id", j['id']).execute(); st.rerun()

# --- TAB 3: EXECUTIVE ANALYSIS ---
with t_exec:
    if all_logs:
        df_e = pd.DataFrame(all_logs)
        st.markdown("#### 🚨 Delayed/High Priority Jobs")
        if 'required_date' in df_e.columns:
            df_e['required_date'] = pd.to_datetime(df_e['required_date'])
            df_e['Lag'] = (pd.Timestamp(datetime.now().date()) - df_e['required_date']).dt.days
            lagging = df_e[(df_e['Lag'] > 0) & (df_e['status'] != 'Finished')]
            
            if not lagging.empty:
                # Executive can see notes to understand why a job is lagging
                st.dataframe(lagging[['job_code', 'part_name', 'Lag', 'priority', 'special_notes']], use_container_width=True, hide_index=True)
            else: st.success("✅ No jobs are lagging.")
        
        st.divider()
        st.markdown("#### 📖 Full History Log")
        st.dataframe(df_e, use_container_width=True, hide_index=True)
        st.download_button("📥 Export CSV", df_e.to_csv(index=False).encode('utf-8'), f"{st.session_state.hub}.csv")

# --- TAB 4: MASTERS ---
with t_masters:
    col1, col2 = st.columns(2)
    with col1:
        new_res = st.text_input(f"New {RES_LABEL}")
        if st.button(f"Add {RES_LABEL}"): conn.table(RES_MASTER).insert({RES_COL: new_res}).execute(); st.rerun()
    with col2:
        m_type = st.selectbox("Category", ["Operator", "Contractor"])
        m_name = st.text_input("Full Name")
        if st.button("Add Person"):
            tbl = "beta_operator_master" if m_type=="Operator" else "beta_vendor_master"
            col = "operator_name" if m_type=="Operator" else "vendor_name"
            conn.table(tbl).insert({col: m_name}).execute(); st.rerun()
