import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import plotly.express as px
import datetime
import io

# 1. Initialize Connection & Page Config
st.set_page_config(page_title="B&G Machining Hub", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)

st.title("⚙️ B&G Machining Hub: Integrated ERP")

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

# Fetch live logs
all_logs_query = conn.table("machining_logs").select("*").order("created_at", desc=True).execute()
all_data = all_logs_query.data or []

# 3. Define Tabs
tab_prod, tab_incharge, tab_analytics, tab_log, tab_masters = st.tabs([
    "📝 Request & Live Status", "👨‍💻 Incharge Desk", "📊 Executive Analytics", "📋 Full Logbook", "🛠️ Masters"
])

# --- TAB 1: PRODUCTION REQUEST & LIVE STATUS ---
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
        
        if st.form_submit_button("Submit Request"):
            if j_code and part:
                conn.table("machining_logs").insert({
                    "unit_no": u_no, "job_code": j_code, "part_name": part,
                    "activity_type": act, "required_date": str(req_date), 
                    "priority": priority, "status": "Pending"
                }).execute()
                st.success(f"Job {j_code} added to queue!")
                st.rerun()

    st.divider()
    st.subheader("🚦 Your Unit's Current Jobs")
    unit_sel = st.radio("Select Unit to View Status", [1, 2, 3], horizontal=True)
    if all_data:
        df_status = pd.DataFrame(all_data)
        unit_df = df_status[df_status['unit_no'] == unit_sel].head(10)
        st.dataframe(unit_df[['job_code', 'part_name', 'status', 'priority', 'required_date']], use_container_width=True, hide_index=True)

# --- TAB 2: INCHARGE DECISION (PIN PROTECTED) ---
with tab_incharge:
    st.subheader("🎯 Allocation & Intervention")
    auth_code = st.text_input("Enter Incharge Pin to unlock actions", type="password")
    
    if auth_code == "1234": # Change this PIN as needed
        active_jobs = [j for j in all_data if j['status'] != "Finished"]
        if not active_jobs:
            st.info("All jobs completed!")
        else:
            for job in active_jobs:
                p_color = {"URGENT": "🔴", "High": "🟠", "Medium": "🟡", "Low": "⚪"}.get(job['priority'], "⚪")
                with st.expander(f"{p_color} {job['priority']} | Unit {job['unit_no']} | Job: {job['job_code']}"):
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
                        wb = st.text_input("Waybill No", key=f"wb_{job['id']}")
                        if st.button("Receive & Finish", key=f"b3_{job['id']}"):
                            conn.table("machining_logs").update({"status":"Finished","waybill_no":wb,"delay_reason":d_reason,"intervention_note":i_note}).eq("id", job['id']).execute()
                            st.rerun()
                    elif job['status'] == "In-House":
                        if st.button("Mark Work Completed", key=f"b4_{job['id']}"):
                            conn.table("machining_logs").update({"status":"Finished","delay_reason":d_reason,"intervention_note":i_note}).eq("id", job['id']).execute()
                            st.rerun()
    else:
        st.warning("Please enter the Incharge Pin to manage jobs.")

# --- TAB 3: EXECUTIVE ANALYTICS ---
with tab_analytics:
    st.subheader("📊 Executive Action Center")
    if all_data:
        df = pd.DataFrame(all_data)
        df['created_at'] = pd.to_datetime(df['created_at'])
        df['Days Idle'] = (pd.Timestamp.now(tz='UTC') - df['created_at']).dt.days
        
        # Action Tables
        st.error("### 🚨 High Priority Bottlenecks")
        urgent_df = df[df['priority'].isin(['URGENT', 'High']) & (df['status'] != 'Finished')]
        st.dataframe(urgent_df[['job_code', 'part_name', 'Days Idle', 'status', 'delay_reason']], use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("📥 Export Reports")
        
        # Create a copy for the report so we don't mess up the live display
        export_df = df.copy()
        
        # 🚨 FIX: Remove timezone info from all datetime columns
        for col in export_df.columns:
            if pd.api.types.is_datetime64_any_dtype(export_df[col]):
                export_df[col] = export_df[col].dt.tz_localize(None)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            export_df.to_excel(writer, index=False, sheet_name='Production_Report')
        
        st.download_button(
            label="📂 Download Full Excel Report", 
            data=buffer.getvalue(), 
            file_name=f"BG_Report_{datetime.date.today()}.xlsx", 
            mime="application/vnd.ms-excel"
        )

# --- TAB 4: LOGBOOK ---
with tab_log:
    st.subheader("📋 Complete History")
    st.dataframe(all_data, use_container_width=True)

# --- TAB 5: MASTERS ---
with tab_masters:
    st.info("Master Data Management is currently done via Supabase Dashboard.")
