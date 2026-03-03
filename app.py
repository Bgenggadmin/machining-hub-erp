import streamlit as st
from st_supabase_connection import SupabaseConnection

# 1. Initialize Connection
# This uses the Project URL and API Key from your Supabase Settings
conn = st.connection("supabase", type=SupabaseConnection)

st.set_page_config(page_title="Machining Hub", layout="wide")
st.title("⚙️ Machining Unit: Incharge Control Desk")

# 2. Fetch Master Data for Dropdowns
# We pull this live so the Incharge can add new machines/vendors anytime
def get_master_data():
    machines = conn.table("machine_master").select("machine_name").execute().data
    operators = conn.table("operator_master").select("operator_name").execute().data
    vendors = conn.table("vendor_master").select("vendor_name").execute().data
    vehicles = conn.table("vehicle_master").select("vehicle_number").execute().data
    
    return (
        [m['machine_name'] for m in machines],
        [o['operator_name'] for o in operators],
        [v['vendor_name'] for v in vendors],
        [vh['vehicle_number'] for vh in vehicles]
    )

machine_list, operator_list, vendor_list, vehicle_list = get_master_data()

# 3. Sidebar: Quick Stats (Founder/Incharge View)
st.sidebar.header("Unit Overview")
total_pending = conn.table("machining_logs").select("*", count="exact").eq("status", "Pending").execute().count
st.sidebar.metric("Pending Requests", total_pending)

# 4. Main Interface Tabs
tab_log, tab_outsource, tab_masters = st.tabs(["📋 Activity Log", "🚚 Outsourcing & Gatepass", "🛠️ Manage Masters"])

with tab_log:
    st.subheader("Book New Machining Activity")
    with st.form("entry_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            u_no = st.selectbox("Unit No", [1, 2, 3])
            j_code = st.text_input("Job Code (e.g. B&G-2026-01)")
            part = st.text_input("Part Name")
        with col2:
            act = st.selectbox("Activity", ["Turning", "Drilling", "Milling", "Keyway", "Dishbending"])
            req_date = st.date_input("Required Delivery Date")
            op = st.selectbox("Assign Operator", operator_list)

        if st.form_submit_button("Save to Supabase"):
            res = conn.table("machining_logs").insert({
                "unit_no": u_no, "job_code": j_code, "part_name": part,
                "activity_type": act, "required_date": str(req_date),
                "operator_id": op, "status": "In-House"
            }).execute()
            st.success("Entry Saved Successfully!")
            st.rerun()

with tab_outsource:
    st.subheader("Send for Outsourcing")
    # Show only jobs marked for outsourcing or needing a decision
    st.info("Here the Incharge will enter Gatepass and Vehicle details.")
    # Example field for logic check
    gp_no = st.text_input("Enter Gatepass No")
    v_no = st.selectbox("Select Vehicle", vehicle_list)

with tab_masters:
    st.subheader("🛠️ Update Machine & Personnel Masters")
    
    # 1. Machine Editor
    st.write("### Machinery List")
    existing_machines = conn.table("machine_master").select("*").execute().data
    edited_machines = st.data_editor(existing_machines, num_rows="dynamic", key="m_edit")
    
    # 2. Operator Editor
    st.write("### Operator List")
    existing_ops = conn.table("operator_master").select("*").execute().data
    edited_ops = st.data_editor(existing_ops, num_rows="dynamic", key="o_edit")
    
    if st.button("Save Changes to Masters"):
        # This pushes any new rows or edits back to Supabase
        conn.table("machine_master").upsert(edited_machines).execute()
        conn.table("operator_master").upsert(edited_ops).execute()
        st.success("Masters updated! Refresh the page to see changes in dropdowns.")

# 5. Live Data View (The Logbook)
st.divider()
st.subheader("Live Machining Logbook")
all_logs = conn.table("machining_logs").select("*").order("created_at", desc=True).execute()
if all_logs.data:
    st.dataframe(all_logs.data, use_container_width=True)
else:
    st.write("No logs found. Start by adding an entry above!")
