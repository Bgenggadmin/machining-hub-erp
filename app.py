import streamlit as st
from st_supabase_connection import SupabaseConnection

# 1. Initialize Connection
conn = st.connection("supabase", type=SupabaseConnection)

st.set_page_config(page_title="B&G Machining Hub", layout="wide")
st.title("⚙️ Machining Unit: Production & Incharge Portal")

# 2. Fetch Master Data
def get_master_data():
    try:
        machines = conn.table("machine_master").select("machine_name").execute().data or []
        operators = conn.table("operator_master").select("operator_name").execute().data or []
        vendors = conn.table("vendor_master").select("vendor_name").execute().data or []
        vehicles = conn.table("vehicle_master").select("vehicle_number").execute().data or []
        return ([m['machine_name'] for m in machines], [o['operator_name'] for o in operators], 
                [v['vendor_name'] for v in vendors], [vh['vehicle_number'] for vh in vehicles])
    except: return ([], [], [], [])

machine_list, operator_list, vendor_list, vehicle_list = get_master_data()

# 3. Main Interface Tabs
tab_prod, tab_incharge, tab_logbook, tab_masters = st.tabs([
    "📝 Production Request", "👨‍💻 Incharge Decision Board", "📊 Live Logbook", "🛠️ Manage Masters"
])

# --- TAB 1: PRODUCTION TEAM (BOOKING) ---
with tab_prod:
    st.subheader("📋 Book New Machining Activity")
    with st.form("prod_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        u_no = c1.selectbox("Unit No", [1, 2, 3])
        j_code = c1.text_input("Job Code", placeholder="e.g. BG-2026-001")
        part = c2.text_input("Part Name")
        act = c2.selectbox("Activity", ["Turning", "Drilling", "Milling", "Keyway", "Dishbending"])
        req_date = st.date_input("Required Delivery Date")
        
        if st.form_submit_button("Send to Incharge"):
            if j_code and part:
                conn.table("machining_logs").insert({
                    "unit_no": u_no, "job_code": j_code, "part_name": part,
                    "activity_type": act, "required_date": str(req_date), "status": "Pending"
                }).execute()
                st.success("Request logged! Awaiting Incharge decision.")
                st.rerun()

# --- TAB 2: INCHARGE DECISION BOARD (UPDATED) ---
with tab_incharge:
    st.subheader("🎯 Allocation, Dispatch & Intervention")
    
    # Fetch jobs that are NOT Finished
    active_jobs = conn.table("machining_logs").select("*").neq("status", "Finished").execute().data
    
    if not active_jobs:
        st.info("No active jobs requiring intervention.")
    else:
        for job in active_jobs:
            # Color code: Red for Pending, Yellow for In-Progress
            status_emoji = "🔴" if job['status'] == "Pending" else "🟡"
            
            with st.expander(f"{status_emoji} Job: {job['job_code']} | Part: {job['part_name']}"):
                
                # --- NEW: INTERVENTION & DELAY SECTION ---
                st.markdown("##### ⚠️ Status & Intervention Note")
                c_delay, c_inter = st.columns(2)
                delay_reason = c_delay.text_input("Delay Reason (if any)", value=job.get('delay_reason', ''), key=f"del_{job['id']}")
                intervention = c_inter.text_area("Intervention / Specific Note", value=job.get('intervention_note', ''), key=f"int_{job['id']}")
                
                st.divider()

                # --- DECISION LOGIC ---
                if job['status'] == "Pending":
                    mode = st.radio("Allotment Mode", ["In-House", "Outsource"], key=f"mode_{job['id']}", horizontal=True)
                    
                    if mode == "In-House":
                        col1, col2 = st.columns(2)
                        m_sel = col1.selectbox("Machine", machine_list, key=f"m_{job['id']}")
                        o_sel = col2.selectbox("Operator", operator_list, key=f"o_{job['id']}")
                        if st.button("Confirm In-House & Update Notes", key=f"bin_{job['id']}"):
                            conn.table("machining_logs").update({
                                "status": "In-House", 
                                "machine_id": m_sel, 
                                "operator_id": o_sel,
                                "delay_reason": delay_reason,
                                "intervention_note": intervention
                            }).eq("id", job['id']).execute()
                            st.rerun()
                    
                    else: # Outsource Logic
                        col1, col2 = st.columns(2)
                        v_sel = col1.selectbox("Vendor", vendor_list, key=f"v_{job['id']}")
                        vh_sel = col1.selectbox("Vehicle", vehicle_list, key=f"vh_{job['id']}")
                        gp_no = col2.text_input("Gate Pass No", key=f"gp_{job['id']}")
                        if st.button("Dispatch & Update Notes", key=f"bout_{job['id']}"):
                            conn.table("machining_logs").update({
                                "status": "Outsourced", 
                                "vendor_id": v_sel, 
                                "vehicle_no": vh_sel, 
                                "gatepass_no": gp_no,
                                "delay_reason": delay_reason,
                                "intervention_note": intervention
                            }).eq("id", job['id']).execute()
                            st.rerun()

                # --- IN-PROGRESS UPDATES (INWARD TRACKING) ---
                elif job['status'] == "Outsourced":
                    st.info(f"Currently at Vendor: {job.get('vendor_id')}")
                    wb_no = st.text_input("Waybill / DC No (On Return)", key=f"wb_{job['id']}")
                    if st.button("Receive & Close Job", key=f"fin_{job['id']}"):
                        conn.table("machining_logs").update({
                            "status": "Finished", 
                            "waybill_no": wb_no,
                            "delay_reason": delay_reason,
                            "intervention_note": intervention
                        }).eq("id", job['id']).execute()
                        st.rerun()

                elif job['status'] == "In-House":
                    if st.button("Complete Work & Close", key=f"comp_{job['id']}"):
                        conn.table("machining_logs").update({
                            "status": "Finished",
                            "delay_reason": delay_reason,
                            "intervention_note": intervention
                        }).eq("id", job['id']).execute()
                        st.rerun()

# --- TAB 3: LOGBOOK (THE REPOSITORY) ---
with tab_logbook:
    st.subheader("📊 Central Production Data")
    all_data = conn.table("machining_logs").select("*").order("created_at", desc=True).execute().data
    st.dataframe(all_data, use_container_width=True)

# --- TAB 4: MASTERS ---
with tab_masters:
    st.subheader("🛠️ Update Master Lists")
    # (Same data_editor logic for Machine, Operator, Vendor, Vehicle)
    m_data = conn.table("machine_master").select("*").execute().data
    ed_m = st.data_editor(m_data, num_rows="dynamic", key="me", use_container_width=True)
    if st.button("Save Machines"):
        conn.table("machine_master").upsert(ed_m).execute()
        st.success("Machine list updated!")
