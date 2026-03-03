import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import plotly.express as px

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

# Fetch all logs for use in all tabs
all_logs_query = conn.table("machining_logs").select("*").order("created_at", desc=True).execute()
all_data = all_logs_query.data or []

# 3. Tabs (Added Analytics Tab)
tab_prod, tab_incharge, tab_analytics, tab_log, tab_masters = st.tabs([
    "📝 Request", "👨‍💻 Incharge", "📊 Analytics", "📋 Logbook", "🛠️ Masters"
])

# --- TAB 1: PRODUCTION REQUEST ---
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
                st.success(f"Request {j_code} sent!")
                st.rerun()

# --- TAB 2: INCHARGE DECISION ---
with tab_incharge:
    st.subheader("🎯 Allocation & Intervention")
    active_jobs = [j for j in all_data if j['status'] != "Finished"]
    
    if not active_jobs:
        st.info("No active jobs.")
    else:
        for job in active_jobs:
            p_color = {"URGENT": "🔴", "High": "🟠", "Medium": "🟡", "Low": "⚪"}.get(job['priority'], "⚪")
            with st.expander(f"{p_color} {job['priority']} | Job: {job['job_code']} | Status: {job['status']}"):
                c_del, c_int = st.columns(2)
                d_reason = c_del.text_input("Delay Reason", value=job.get('delay_reason',''), key=f"d_{job['id']}")
                i_note = c_int.text_area("Intervention Note", value=job.get('intervention_note',''), key=f"i_{job['id']}")
                
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
                        with tab_incharge:
    # A simple password to prevent accidental edits by the wrong team
    auth_code = st.text_input("Enter Incharge Pin to unlock actions", type="password")
    
    if auth_code == "1234": # You can change this to your desired pin
        st.success("Access Granted")
        # ... (Existing Incharge Code)
    else:
        st.warning("Please enter the Incharge Pin to manage jobs.")

# --- TAB 3: ANALYTICS & ACTION LISTS (WITH AGING) ---
with tab_analytics:
    st.subheader("📊 Executive Action Center")
    
    if all_data:
        import datetime
        df = pd.DataFrame(all_data)
        
        # Convert created_at to a readable date format
        df['created_at'] = pd.to_datetime(df['created_at'])
        today = pd.Timestamp.now(tz='UTC')
        
        # Calculate Aging (Days since request)
        df['Days Idle'] = (today - df['created_at']).dt.days
        
        # 1. THE RED FLAG LIST
        st.error("### 🚨 Urgent & High Priority Action List")
        urgent_df = df[df['priority'].isin(['URGENT', 'High']) & (df['status'] != 'Finished')]
        if not urgent_df.empty:
            # Sort by highest aging first
            st.dataframe(urgent_df[['job_code', 'part_name', 'priority', 'Days Idle', 'status', 'delay_reason']], 
                         use_container_width=True, hide_index=True)
        else:
            st.success("No urgent bottlenecks!")

        st.divider()

        # 2. VENDOR TRACKING
        st.warning("### 🚚 Vendor Outsourcing Tracker")
        vendor_df = df[df['status'] == 'Outsourced']
        if not vendor_df.empty:
            st.dataframe(vendor_df[['job_code', 'part_name', 'vendor_id', 'Days Idle', 'gatepass_no']], 
                         use_container_width=True, hide_index=True)
        else:
            st.info("No material is currently outside.")

        st.divider()

        # 3. PENDING APPROVAL (WITH AGING)
        st.info("### ⏳ Jobs Awaiting Allotment (Pending)")
        pending_df = df[df['status'] == 'Pending']
        if not pending_df.empty:
            # We highlight jobs pending for more than 2 days
            def highlight_aging(val):
                color = 'red' if val > 2 else 'black'
                return f'color: {color}'

            st.write("Jobs marked in red have been pending for more than 2 days.")
            st.dataframe(pending_df[['job_code', 'part_name', 'Days Idle', 'priority']].style.applymap(highlight_aging, subset=['Days Idle']),
                         use_container_width=True, hide_index=True)
        else:
            st.write("Incharge has cleared all requests!")

    else:
        st.info("No data found in the Logbook.")
        # --- ADD THIS TO THE BOTTOM OF TAB 3 (ANALYTICS) ---
st.divider()
st.subheader("📥 Export Reports")

if all_data:
    # Prepare the final report dataframe
    report_df = pd.DataFrame(all_data)
    
    # Clean up column names for the Excel sheet
    report_df = report_df.rename(columns={
        'job_code': 'Job Code',
        'part_name': 'Part Name',
        'status': 'Current Status',
        'priority': 'Priority',
        'vendor_id': 'Vendor',
        'gatepass_no': 'Gatepass No'
    })

    # Function to convert DF to Excel bytes
    import io
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        report_df.to_excel(writer, index=False, sheet_name='Production_Report')
    
    st.download_button(
        label="📂 Download Full Production Report (Excel)",
        data=buffer.getvalue(),
        file_name=f"BG_Machining_Report_{datetime.date.today()}.xlsx",
        mime="application/vnd.ms-excel"
    )
else:
    st.write("No data available to export.")

# --- TAB 4: LOGBOOK ---
with tab_log:
    st.dataframe(all_data, use_container_width=True)

# --- TAB 5: MASTERS ---
with tab_masters:
    st.info("Use the editors below to manage dropdown lists.")
    # (Data editor logic for masters goes here)
