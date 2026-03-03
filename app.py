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

# --- TAB 2: INCHARGE DECISION BOARD ---
with tab_incharge:
    st.subheader("🎯 Allocation & Inward Tracking")
    
    # Filter for jobs that are NOT Finished
    active_jobs = conn.table("machining_logs").select("*").neq("status", "Finished").execute().data
    
    if not active_jobs:
        st.info("No active jobs in the system.")
    else:
        for job in active_jobs:
            status_color = "🔴" if job['status'] == "Pending" else "🟡"
            with st.expander(f"{status_color} Job: {job['job_code']} | Status: {job['status']}"):
                
                # PATH A: JOB IS PENDING (Decide In-House or Outsource)
                if job['status'] == "Pending":
                    mode = st.radio("Decision", ["In-House", "Outsource"], key=f"dec_{job['id']}", horizontal=True)
                    
                    if mode == "In-House":
                        c1, c2 = st.columns(2)
                        m_sel = c1.selectbox("Allot Machine", machine_list, key=f"m_{job['id']}")
                        o_sel = c2.selectbox("Allot Operator", operator_list, key=f"o_{job['id']}")
                        if st.button("Start In-House", key=f"bin_{job['id']}"):
                            conn.table("machining_logs").update({"status": "In-House", "machine_id": m_sel, "operator_id": o_sel}).eq("id", job['id']).execute()
                            st.rerun()
                    
                    else: # Outsource Logic
                        c1, c2 = st.columns(2)
                        v_sel = c1.selectbox("Select Vendor", vendor_list, key=f"v_{job['id']}")
                        vh_sel = c1.selectbox("Select Vehicle", vehicle_list, key=f"vh_{job['id']}")
                        gp_no = c2.text_input("Gate Pass No", key=f"gp_{job['id']}")
                        if st.button("Dispatch to Vendor", key=f"bout_{job['id']}"):
                            conn.table("machining_logs").update({"status": "Outsourced", "vendor_id": v_sel, "vehicle_no": vh_sel, "gatepass_no": gp_no}).eq("id", job['id']).execute()
                            st.rerun()

                # PATH B: JOB IS OUTSOURCED (Update Waybill when it comes back)
                elif job['status'] == "Outsourced":
                    st.warning(f"Material is at Vendor: {job.get('vendor_id')}")
                    wb_no = st.text_input("Enter Waybill / DC No (On Return)", key=f"wb_{job['id']}")
                    if st.button("Mark as Received & Finished", key=f"fin_{job['id']}"):
                        if wb_no:
                            conn.table("machining_logs").update({"status": "Finished", "waybill_no": wb_no}).eq("id", job['id']).execute()
                            st.success("Job marked as Finished!")
                            st.rerun()
                        else:
                            st.error("Please enter Waybill No to close the job.")

                # PATH C: JOB IS IN-HOUSE (Close it)
                elif job['status'] == "In-House":
                    if st.button("Mark Work Completed", key=f"comp_{job['id']}"):
                        conn.table("machining_logs").update({"status": "Finished"}).eq("id", job['id']).execute()
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
