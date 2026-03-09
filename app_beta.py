import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd

# 1. Page Configuration
st.set_page_config(page_title="B&G Integrated Sandbox", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)

# --- SIDEBAR: HUB SELECTOR ---
# This MUST be visible on the left to change the form from Machining to Buffing
st.sidebar.title("🏢 Department Switcher")
hub_mode = st.sidebar.radio(
    "Select Hub to View/Request:", 
    ["Machining Hub", "Buffing & Polishing"],
    key="main_hub_switch"
)

# 2. Dynamic Configuration Mapping
# This section changes the Form Labels and Database Tables based on the Sidebar
if hub_mode == "Machining Hub":
    DB_TABLE = "beta_machining_logs"
    RES_MASTER = "beta_machine_master"
    RES_LABEL = "Machine"
    RES_COL = "machine_name"
    # Specific activities for Machining
    ACTIVITY_OPTS = ["Turning", "Drilling", "Milling", "Keyway", "Dishbending"]
    FORM_TITLE = "New Machining Request"
else:
    # Specific activities for Buffing
    DB_TABLE = "beta_buffing_logs"
    RES_MASTER = "beta_buffing_station_master"
    RES_LABEL = "Buffing Station"
    RES_COL = "station_name"
    ACTIVITY_OPTS = ["Rough Buffing", "Mirror Polishing", "Satin Finish", "RA Value Check", "Cleaning"]
    FORM_TITLE = "New Buffing & Polishing Request"

st.title(f"🧪 {hub_mode}: Sandbox Beta")

# 3. Fetch Master Data from your new beta_ tables
def get_beta_masters():
    try:
        res = conn.table(RES_MASTER).select(RES_COL).execute().data or []
        ops = conn.table("beta_operator_master").select("operator_name").execute().data or []
        vends = conn.table("beta_vendor_master").select("vendor_name").execute().data or []
        return (
            [r[RES_COL] for r in res], 
            [o['operator_name'] for o in ops], 
            [v['vendor_name'] for v in vends]
        )
    except Exception as e:
        return [], [], []

resource_list, operator_list, vendor_list = get_beta_masters()

# 4. Tabs
tab_prod, tab_incharge, tab_log = st.tabs(["📝 Request Form", "👨‍💻 Incharge Desk", "📋 Beta Logbook"])

# --- TAB 1: DYNAMIC PRODUCTION REQUEST ---
with tab_prod:
    # This header now changes based on your sidebar selection
    st.subheader(f"📋 {FORM_TITLE}")
    
    with st.form("dynamic_prod_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        u_no = c1.selectbox("Unit No", [1, 2, 3])
        j_code = c1.text_input("Job Code")
        part = c2.text_input("Part Name")
        
        # KEY FIX: The dropdown list 'ACTIVITY_OPTS' now changes when you flip the sidebar
        act = c2.selectbox("Activity/Process", ACTIVITY_OPTS)
        
        req_date = c3.date_input("Required Date")
        priority = c3.selectbox("Priority", ["Low", "Medium", "High", "URGENT"])
        
        if st.form_submit_button("Send to Incharge"):
            if j_code and part:
                conn.table(DB_TABLE).insert({
                    "unit_no": u_no, "job_code": j_code, "part_name": part,
                    "activity_type": act, "required_date": str(req_date), 
                    "priority": priority, "status": "Pending"
                }).execute()
                st.success(f"Successfully sent {j_code} to the {hub_mode} Incharge!")
                st.rerun()

# --- TAB 2 & 3 Logic follows the same DB_TABLE variable ---
# (Allocation logic using operator_list/vendor_list for In-house only)
