import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd

# 1. Setup
st.set_page_config(page_title="B&G Integrated Beta", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)

# --- HUB SELECTION BUTTONS ---
if 'hub' not in st.session_state:
    st.session_state.hub = "Machining Hub"

st.write("### 🏢 Select Department")
c1, c2 = st.columns(2)

if c1.button("⚙️ MACHINING HUB", use_container_width=True, 
             type="primary" if st.session_state.hub == "Machining Hub" else "secondary"):
    st.session_state.hub = "Machining Hub"
    st.rerun()

if c2.button("✨ BUFFING & POLISHING", use_container_width=True, 
             type="primary" if st.session_state.hub == "Buffing & Polishing" else "secondary"):
    st.session_state.hub = "Buffing & Polishing"
    st.rerun()

# --- DYNAMIC CONFIG BASED ON SELECTION ---
if st.session_state.hub == "Machining Hub":
    DB_TABLE = "beta_machining_logs"
    RES_MASTER = "beta_machine_master"
    ACTIVITY_LIST = ["Turning", "Drilling", "Milling", "Keyway", "Dishbending"]
else:
    DB_TABLE = "beta_buffing_logs"
    RES_MASTER = "beta_buffing_station_master"
    ACTIVITY_LIST = ["Rough Buffing", "Mirror Polishing", "Satin Finish", "RA Value Check"]

st.divider()

# 2. Fetch Data
all_logs = conn.table(DB_TABLE).select("*").order("created_at", desc=True).execute().data or []

# 3. Tabs
t_prod, t_inch, t_log = st.tabs(["📝 Request & Status", "👨‍💻 Incharge Desk", "📋 Logbook"])

# --- TAB 1: REQUEST + LIVE STATUS ---
with t_prod:
    # Part A: The Form
    st.subheader(f"New {st.session_state.hub} Request")
    with st.form(key=f"form_{st.session_state.hub}", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        u_no = col1.selectbox("Unit No", [1, 2, 3])
        j_code = col1.text_input("Job Code")
        part = col2.text_input("Part Name")
        act = col2.selectbox("Process", ACTIVITY_LIST)
        priority = col3.selectbox("Priority", ["Low", "Medium", "High", "URGENT"])
        
        if st.form_submit_button("Submit Request"):
            if j_code and part:
                conn.table(DB_TABLE).insert({
                    "unit_no": u_no, "job_code": j_code, "part_name": part,
                    "activity_type": act, "priority": priority, "status": "Pending"
                }).execute()
                st.success("Request Sent!")
                st.rerun()

    # Part B: YOUR UNIT'S CURRENT JOBS (The Missing Section)
    st.divider()
    st.subheader(f"🚦 Current {st.session_state.hub} Jobs")
    
    if all_logs:
        df = pd.DataFrame(all_logs)
        # Filter for only active (not finished) jobs
        active_df = df[df['status'] != "Finished"]
        
        if not active_df.empty:
            # Clean up the view for the production floor
            display_df = active_df[['unit_no', 'job_code', 'part_name', 'activity_type', 'status', 'priority']]
            
            # Styling priority colors
            def color_priority(val):
                color = 'red' if val == 'URGENT' else ('orange' if val == 'High' else 'black')
                return f'color: {color}'
            
            st.dataframe(display_df.style.applymap(color_priority, subset=['priority']), 
                         use_container_width=True, hide_index=True)
        else:
            st.info("No active jobs currently on the floor.")

# --- TAB 2: INCHARGE DESK ---
with t_inch:
    # ... (Keep your PIN and Allocation logic here) ...
    st.write(f"Allocation Logic for {st.session_state.hub} goes here.")

# --- TAB 3: LOGBOOK ---
with t_log:
    st.subheader(f"History: {st.session_state.hub}")
    if all_logs:
        st.dataframe(pd.DataFrame(all_logs), use_container_width=True)
