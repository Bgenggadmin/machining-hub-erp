import streamlit as st
from st_supabase_connection import SupabaseConnection

# 1. Initialize Connection
conn = st.connection("supabase", type=SupabaseConnection)

st.set_page_config(page_title="B&G Machining Hub", layout="wide")
st.title("⚙️ Machining Unit: Incharge Control Desk")

# 2. Fetch Master Data with Error Handling
def get_master_data():
    try:
        machines = conn.table("machine_master").select("machine_name").execute().data or []
        operators = conn.table("operator_master").select("operator_name").execute().data or []
        vendors = conn.table("vendor_master").select("vendor_name").execute().data or []
        vehicles = conn.table("vehicle_master").select("vehicle_number").execute().data or []
        
        return (
            [m['machine_name'] for m in machines],
            [o['operator_name'] for o in operators],
            [v['vendor_name'] for v in vendors],
            [vh['vehicle_number'] for vh in vehicles]
        )
    except Exception:
        return ([], [], [], [])

machine_list, operator_list, vendor_list, vehicle_list = get_master_data()

# 3. Sidebar: Quick Stats
st.sidebar.header("Unit Overview")
try:
    total_pending = conn.table("machining_logs").select("*", count="exact").eq("status", "Pending").execute().count
    st.sidebar.metric("Pending Requests", total_pending)
except:
    st.sidebar.warning("Database Connection Issue")

# 4. Main Interface Tabs
tab_log, tab_outsource, tab_masters = st.tabs(["📋 Activity Log", "🚚 Outsourcing & Gatepass", "🛠️ Manage Masters"])

with tab_log:
    st.subheader("📋 Book New Machining Activity")
    with st.form("entry_form", clear_on_submit=True):
        row1_col1, row1_col2 = st.columns(2)
        row2_col1, row2_col2 = st.columns(2)
        row3_col1, row3_col2 = st.columns(2)

        with row1_col1:
            u_no = st.selectbox("Unit No", [1, 2, 3])
        with row1_col2:
            j_code = st.text_input("Job Code", placeholder="e.g. BG-2026-001")
            
        with row2_col1:
            part = st.text_input("Part Name", placeholder="e.g. Shaft-Pinion")
        with row2_col2:
            act = st.selectbox("Activity", ["Turning", "Drilling", "Milling", "Keyway", "Dishbending"])
            
        with row3_col1:
            req_date = st.date_input("Required Delivery Date")
        with row3_col2:
            op = st.selectbox("Assign Initial Operator", ["-- Select Operator --"] + operator_list)

        submit = st.form_submit_button("🚀 Save to Supabase")

        if submit:
            if j_code and part and op != "-- Select Operator --":
                conn.table("machining_logs").insert({
                    "unit_no": u_no, 
                    "job_code": j_code, 
                    "part_name": part,
                    "activity_type": act, 
                    "required_date": str(req_date),
                    "operator_id": op, 
                    "status": "Pending"
                }).execute()
                st.success(f"✅ Job {j_code} registered successfully!")
                st.rerun()
            else:
                st.error("⚠️ Please fill all fields and select an Operator.")

with tab_outsource:
    st.subheader("🚛 Incharge Dispatch & Decision Desk")
    pending_jobs = conn.table("machining_logs").select("*").eq("status", "Pending").execute().data
    
    if not pending_jobs:
        st.info("No pending requests from the production units.")
    else:
        for job in pending_jobs:
            with st.expander(f"📌 Job: {job['job_code']} | Part: {job['part_name']}"):
                choice = st.radio("Decision", ["In-House", "Outsource"], key=f"dec_{job['id']}")
                
                if choice == "In-House":
                    c1, c2 = st.columns(2)
                    m_sel = c1.selectbox("Machine", machine_list, key=f"m_{job['id']}")
                    o_sel = c2.selectbox("Operator", operator_list, key=f"o_{job['id']}")
                    if st.button("Start In-House", key=f"btn_in_{job['id']}"):
                        conn.table("machining_logs").update({"status": "In-House", "machine_id": m_sel, "operator_id": o_sel}).eq("id", job['id']).execute()
                        st.rerun()
                else:
                    c1, c2, c3 = st.columns(3)
                    v_sel = c1.selectbox("Vendor", vendor_list, key=f"v_{job['id']}")
                    gp_val = c2.text_input("Gatepass No.", key=f"gp_{job['id']}")
                    vh_sel = c3.selectbox("Vehicle", vehicle_list, key=f"vh_{job['id']}")
                    if st.button("Dispatch Outward", key=f"btn_out_{job['id']}"):
                        if gp_val:
                            conn.table("machining_logs").update({"status": "Outsourced", "vendor_id": v_sel, "gatepass_no": gp_val, "vehicle_no": vh_sel}).eq("id", job['id']).execute()
                            st.rerun()
                        else:
                            st.error("Gatepass No. is mandatory.")

with tab_masters:
    st.subheader("🛠️ Manage Master Data")
    
    # 1. Machinery Editor
    st.write("### 🏗️ Machinery List")
    m_data = conn.table("machine_master").select("*").execute().data
    edited_m = st.data_editor(m_data, num_rows="dynamic", key="m_edit", use_container_width=True)
    
    # 2. Operator Editor
    st.write("### 👨‍🔧 Operator List")
    o_data = conn.table("operator_master").select("*").execute().data
    edited_o = st.data_editor(o_data, num_rows="dynamic", key="o_edit", use_container_width=True)

    # 3. Vendor Editor (ADDED)
    st.write("### 🏢 Vendor List")
    v_data = conn.table("vendor_master").select("*").execute().data
    edited_v = st.data_editor(v_data, num_rows="dynamic", key="v_edit", use_container_width=True)

    # 4. Vehicle Editor (ADDED)
    st.write("### 🚛 Vehicle List")
    vh_data = conn.table("vehicle_master").select("*").execute().data
    edited_vh = st.data_editor(vh_data, num_rows="dynamic", key="vh_edit", use_container_width=True)

    if st.button("Save All Changes to Masters"):
        try:
            if edited_m: conn.table("machine_master").upsert(edited_m).execute()
            if edited_o: conn.table("operator_master").upsert(edited_o).execute()
            if edited_v: conn.table("vendor_master").upsert(edited_v).execute()
            if edited_vh: conn.table("vehicle_master").upsert(edited_vh).execute()
            st.success("✅ All Masters updated successfully!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error updating masters: {e}")

# 5. Live Data View
st.divider()
st.subheader("Live Machining Logbook")
all_logs = conn.table("machining_logs").select("*").order("created_at", desc=True).execute()
if all_logs.data:
    st.dataframe(all_logs.data, use_container_width=True)
