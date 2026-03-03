import streamlit as st
from st_supabase_connection import SupabaseConnection

# 1. Initialize Connection
conn = st.connection("supabase", type=SupabaseConnection)

st.set_page_config(page_title="B&G Machining Hub", layout="wide")
st.title("⚙️ Machining Unit: Master Control")

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

# 3. Tabs
tab_prod, tab_incharge, tab_log, tab_masters = st.tabs([
    "📝 Production Request", "👨‍💻 Incharge Decision", "📊 Live Logbook", "🛠️ Manage Masters"
])

# --- TAB 1: PRODUCTION REQUEST (WITH PRIORITY) ---
with tab_prod:
    st.subheader("📋 New Machining Request")
    with st.form("prod_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        u_no = c1.selectbox("Unit No", [1, 2, 3])
        j_code = c1.text_input("Job Code")
        part = c2.text_input("Part Name")
        act = c2.selectbox("Activity", ["Turning", "Drilling", "Milling", "Keyway", "Dishbending"])
        req_date = c3.date_input("Required Date")
        priority = c3.selectbox("Priority", ["Low", "Medium", "High", "URGENT"])
        
        if st.form_submit_button("Send to Incharge"):
            if j_code and part:
                conn.table("machining_logs").insert({
                    "unit_no": u_no, "job_code": j_code, "part_name": part,
                    "activity_type": act, "required_date": str(req_date), 
                    "priority": priority, "status": "Pending"
                }).execute()
                st.success(f"Request {j_code} sent with {priority} priority!")
                st.rerun()

# --- TAB 2: INCHARGE DECISION (WITH INTERVENTION) ---
with tab_incharge:
    st.subheader("🎯 Allocation & Intervention")
    active_jobs = conn.table("machining_logs").select("*").neq("status", "Finished").order("priority").execute().data
    
    if not active_jobs:
        st.info("No active jobs.")
    else:
        for job in active_jobs:
            p_color = {"URGENT": "🔴", "High": "🟠", "Medium": "🟡", "Low": "⚪"}.get(job['priority'], "⚪")
            with st.expander(f"{p_color} {job['priority']} | Job: {job['job_code']} | Status: {job['status']}"):
                
                # Intervention Section
                c_del, c_int = st.columns(2)
                d_reason = c_del.text_input("Delay Reason", value=job.get('delay_reason',''), key=f"d_{job['id']}")
                i_note = c_int.text_area("Intervention Note", value=job.get('intervention_note',''), key=f"i_{job['id']}")
                
                # Allocation Logic
                if job['status'] == "Pending":
                    mode = st.radio("Mode", ["In-House", "Outsource"], key=f"m_{job['id']}", horizontal=True)
                    if mode == "In-House":
                        c1, c2 = st.columns(2)
                        m = c1.selectbox("Machine", machine_list, key=f"mac_{job['id']}")
                        o = c2.selectbox("Operator", operator_list, key=f"op_{job['id']}")
                        if st.button("Allot In-House", key=f"b1_{job['id']}"):
                            conn.table("machining_logs").update({"status":"In-House","machine_id":m,"operator_id":o,"delay_reason":d_reason,"intervention_note":i_note}).eq("id", job['id']).execute()
                            st.rerun()
                    else:
                        c1, c2, c3 = st.columns(3)
                        v = c1.selectbox("Vendor", vendor_list, key=f"v_{job['id']}")
                        vh = c2.selectbox("Vehicle", vehicle_list, key=f"vh_{job['id']}")
                        gp = c3.text_input("Gatepass No", key=f"gp_{job['id']}")
                        if st.button("Dispatch Outward", key=f"b2_{job['id']}"):
                            conn.table("machining_logs").update({"status":"Outsourced","vendor_id":v,"vehicle_no":vh,"gatepass_no":gp,"delay_reason":d_reason,"intervention_note":i_note}).eq("id", job['id']).execute()
                            st.rerun()
                
                elif job['status'] == "Outsourced":
                    wb = st.text_input("Waybill No (on return)", key=f"wb_{job['id']}")
                    if st.button("Receive & Finish", key=f"b3_{job['id']}"):
                        conn.table("machining_logs").update({"status":"Finished","waybill_no":wb,"delay_reason":d_reason,"intervention_note":i_note}).eq("id", job['id']).execute()
                        st.rerun()
                
                elif job['status'] == "In-House":
                    if st.button("Work Completed", key=f"b4_{job['id']}"):
                        conn.table("machining_logs").update({"status":"Finished","delay_reason":d_reason,"intervention_note":i_note}).eq("id", job['id']).execute()
                        st.rerun()

# --- TAB 3: LOGBOOK ---
with tab_log:
    st.subheader("📊 Live Production Log")
    logs = conn.table("machining_logs").select("*").order("created_at", desc=True).execute().data
    st.dataframe(logs, use_container_width=True)

# --- TAB 4: MASTERS ---
with tab_masters:
    st.subheader("🛠️ Master Data Management")
    # Display the 4 Master Data Editors here as previously discussed...
