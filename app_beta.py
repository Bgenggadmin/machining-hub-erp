import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import datetime
import io

# 1. Setup
st.set_page_config(page_title="B&G ERP BETA", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)

# Rounded Pill Button Styling
st.markdown("""<style>div.stButton > button { border-radius: 50px; font-weight: 600; padding: 0.5rem 2rem; }</style>""", unsafe_allow_html=True)

if 'hub' not in st.session_state:
    st.session_state.hub = "Machining Hub"

# --- HUB SELECTION BAR ---
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
def get_data():
    try:
        res = conn.table(MASTER_TABLE).select(MASTER_COL).execute().data or []
        ops = conn.table("beta_operator_master").select("operator_name").execute().data or []
        vnds = conn.table("beta_vendor_master").select("vendor_name").execute().data or []
        vhs = conn.table("beta_vehicle_master").select("vehicle_number").execute().data or []
        logs = conn.table(DB_TABLE).select("*").order("created_at", desc=True).execute().data or []
        return [r[MASTER_COL] for r in res], [o['operator_name'] for o in ops], [v['vendor_name'] for v in vnds], [vh['vehicle_number'] for vh in vhs], logs
    except: return [], [], [], [], []

resource_list, operator_list, vendor_list, vehicle_list, all_data = get_data()

tabs = st.tabs(["📝 Request & Live", "👨‍💻 Incharge Desk", "📊 Executive Analytics", "🛠️ Masters"])

# --- TAB 1: PRODUCTION REQUEST ---
with tabs[0]:
    with st.form("p_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        u_no, j_code = c1.selectbox("Unit", [1, 2, 3]), c1.text_input("Job Code")
        part, act = c2.text_input("Part Name"), c2.selectbox("Activity", ACTIVITIES)
        req_d, prio = c3.date_input("Req Date"), c3.selectbox("Priority", ["Low", "Medium", "High", "URGENT"])
        notes = st.text_area("Production Notes")
        if st.form_submit_button("Submit"):
            conn.table(DB_TABLE).insert({"unit_no": u_no, "job_code": j_code, "part_name": part, "activity_type": act, "required_date": str(req_d), "status": "Pending", "special_notes": notes}).execute(); st.rerun()

# --- TAB 2: INCHARGE DESK (FULL LOGISTICS) ---
with tabs[1]:
    active = [j for j in all_data if j['status'] != "Finished"]
    for job in active:
        with st.expander(f"Job: {job['job_code']} | Status: {job['status']}"):
            c_del, c_int = st.columns(2)
            d_r = c_del.text_input("Delay Reason", value=job.get('delay_reason') or '', key=f"dr_{job['id']}")
            i_n = c_int.text_area("Incharge Note", value=job.get('intervention_note') or '', key=f"in_{job['id']}")
            
            if job['status'] == "Pending":
                mode = st.radio("Path", ["In-House", "Outsource"], key=f"md_{job['id']}", horizontal=True)
                if mode == "In-House":
                    c1, c2 = st.columns(2)
                    m = c1.selectbox(f"Select {RES_LABEL}", resource_list, key=f"m_{job['id']}")
                    o = c2.selectbox("Operator", operator_list, key=f"o_{job['id']}")
                    if st.button("🚀 Allot In-House", key=f"b1_{job['id']}"):
                        conn.table(DB_TABLE).update({"status": "In-House", "machine_id": m, "operator_id": o, "delay_reason": d_r, "intervention_note": i_n}).eq("id", job['id']).execute(); st.rerun()
                else:
                    c1, c2, c3 = st.columns(3)
                    v, vh, gp = c1.selectbox("Vendor", vendor_list, key=f"v_{job['id']}"), c2.selectbox("Vehicle", vehicle_list, key=f"vh_{job['id']}"), c3.text_input("Gatepass No", key=f"gp_{job['id']}")
                    if st.button("🚚 Dispatch Outward", key=f"b2_{job['id']}"):
                        conn.table(DB_TABLE).update({"status": "Outsourced", "vendor_id": v, "vehicle_no": vh, "gatepass_no": gp, "delay_reason": d_r, "intervention_note": i_n}).eq("id", job['id']).execute(); st.rerun()
            elif job['status'] == "Outsourced":
                wb = st.text_input("Waybill No", key=f"wb_{job['id']}")
                if st.button("✅ Received", key=f"b3_{job['id']}"):
                    conn.table(DB_TABLE).update({"status": "Finished", "waybill_no": wb, "delay_reason": d_r, "intervention_note": i_n}).eq("id", job['id']).execute(); st.rerun()
            else:
                if st.button("🏁 Mark Finished", key=f"b4_{job['id']}"):
                    conn.table(DB_TABLE).update({"status": "Finished", "delay_reason": d_r, "intervention_note": i_n}).eq("id", job['id']).execute(); st.rerun()

# --- TAB 3: EXECUTIVE ANALYTICS (KEYERROR PROOF) ---
with tabs[2]:
    if all_data:
        df = pd.DataFrame(all_data)
        
        # Helper to safely select columns
        def safe_cols(df, cols): return [c for c in cols if c in df.columns]
        
        c1, c2 = st.columns(2)
        with c1:
            st.write("### 🏠 In-House Load")
            cols = safe_cols(df, ['machine_id', 'job_code', 'operator_id', 'priority'])
            st.dataframe(df[df['status'] == 'In-House'][cols], use_container_width=True, hide_index=True)
        with c2:
            st.write("### 🚚 Vendor Status")
            cols = safe_cols(df, ['vendor_id', 'job_code', 'vehicle_no', 'gatepass_no'])
            st.dataframe(df[df['status'] == 'Outsourced'][cols], use_container_width=True, hide_index=True)
            
        st.divider()
        st.write("### 📋 Full Audit Log")
        st.dataframe(df, use_container_width=True)

# --- TAB 4: MASTERS ---
with tabs[3]:
    cmap = {MASTER_TABLE: MASTER_COL, "beta_operator_master": "operator_name", "beta_vendor_master": "vendor_name", "beta_vehicle_master": "vehicle_number"}
    c1, c2, c3 = st.columns([2, 2, 1])
    cat = c1.selectbox("Category", list(cmap.keys()))
    val = c2.text_input("Name")
    if c3.button("➕ Add"):
        if val: conn.table(cat).insert({cmap[cat]: val}).execute(); st.rerun()
    
    st.divider()
    d1, d2, d3 = st.columns([2, 2, 1])
    d_cat = d1.selectbox("Remove From", list(cmap.keys()), key="del")
    d_items = [r[cmap[d_cat]] for r in conn.table(d_cat).select(cmap[d_cat]).execute().data or []]
    d_val = d2.selectbox("Item", d_items)
    if d3.button("🗑️ Delete"):
        conn.table(d_cat).delete().eq(cmap[d_cat], d_val).execute(); st.rerun()
