import streamlit as st
import requests
import json
import pandas as pd
from streamlit_folium import st_folium
import folium
from datetime import datetime
import time

# ---- CONFIG ----
st.set_page_config(
    page_title="Delivery Allocation System",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API Configuration
API_BASE_URL = "http://localhost:8000"

# ---- CUSTOM CSS ----
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .success-box {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 1rem;
        margin: 1rem 0;
    }
    .warning-box {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 1rem;
        margin: 1rem 0;
    }
    .error-box {
        background-color: #f8d7da;
        border-left: 4px solid #dc3545;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ---- HELPER FUNCTIONS ----
def check_api_health():
    """Check if API is running"""
    try:
        response = requests.get(f"{API_BASE_URL}/", timeout=2)
        return response.status_code == 200
    except:
        return False

def get_data_status():
    """Get status of uploaded data"""
    try:
        response = requests.get(f"{API_BASE_URL}/data/status")
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

def upload_file(file, endpoint):
    """Upload file to API"""
    try:
        files = {"file": (file.name, file.getvalue(), "application/json")}
        response = requests.post(f"{API_BASE_URL}{endpoint}", files=files)
        return response.json(), response.status_code
    except Exception as e:
        return {"error": str(e)}, 500

def run_allocation():
    """Trigger allocation process"""
    try:
        response = requests.post(f"{API_BASE_URL}/allocate")
        return response.json(), response.status_code
    except Exception as e:
        return {"error": str(e)}, 500

def get_results(region=None, order_type=None):
    """Get allocation results with optional filters"""
    try:
        params = {}
        if region:
            params["region"] = region
        if order_type and order_type != "All":
            params["order_type"] = order_type
        
        endpoint = "/results/filtered" if params else "/results"
        response = requests.get(f"{API_BASE_URL}{endpoint}", params=params)
        
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Failed to fetch results: {str(e)}")
    return None

def determine_order_type(tags):
    """Determine order type from tags"""
    if any(tag in tags for tag in ["wedding", "vip", "large_events"]):
        return "Wedding"
    elif "corporate" in tags:
        return "Corporate"
    else:
        return "Regular"

# ---- MAIN APP ----
st.markdown('<div class="main-header">🚚 Delivery Allocation System</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Upload data, run allocation, and visualize driver routes with advanced filtering</div>', unsafe_allow_html=True)

# Check API connection
if not check_api_health():
    st.error("⚠️ Cannot connect to API. Please ensure the FastAPI backend is running on http://localhost:8000")
    st.code("python backend/main.py", language="bash")
    st.stop()

# ============ SIDEBAR ============
st.sidebar.title("📋 Control Panel")

# Data Status
data_status = get_data_status()
if data_status:
    st.sidebar.markdown("### 📊 Data Status")
    status_col1, status_col2 = st.sidebar.columns(2)
    
    with status_col1:
        st.metric("Drivers", data_status.get("drivers_count", 0))
        st.markdown("✅" if data_status.get("drivers_uploaded") else "❌")
    
    with status_col2:
        st.metric("Orders", data_status.get("orders_count", 0))
        st.markdown("✅" if data_status.get("orders_uploaded") else "❌")
    
    if data_status.get("results_available"):
        st.sidebar.success("✅ Allocation results available")
    
    st.sidebar.markdown("---")

# ============ TABS ============
tab1, tab2, tab3 = st.tabs(["📤 Upload Data", "🎯 Run Allocation", "📊 View Results"])

# ============ TAB 1: UPLOAD DATA ============
with tab1:
    st.header("Upload Data Files")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("👥 Upload Drivers")
        drivers_file = st.file_uploader(
            "Choose drivers.json",
            type=["json"],
            key="drivers_upload",
            help="Upload JSON file containing driver information"
        )
        
        if drivers_file:
            if st.button("Upload Drivers File", type="primary"):
                with st.spinner("Uploading drivers..."):
                    result, status = upload_file(drivers_file, "/upload/drivers")
                    
                    if status == 200:
                        st.success(f"✅ {result['message']}")
                        st.info(f"📊 Uploaded {result['count']} drivers")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error(f"❌ Upload failed: {result.get('detail', 'Unknown error')}")
    
    with col2:
        st.subheader("📦 Upload Orders")
        orders_file = st.file_uploader(
            "Choose orders.json",
            type=["json"],
            key="orders_upload",
            help="Upload JSON file containing order information"
        )
        
        if orders_file:
            if st.button("Upload Orders File", type="primary"):
                with st.spinner("Uploading orders..."):
                    result, status = upload_file(orders_file, "/upload/orders")
                    
                    if status == 200:
                        st.success(f"✅ {result['message']}")
                        st.info(f"📊 Uploaded {result['count']} orders")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error(f"❌ Upload failed: {result.get('detail', 'Unknown error')}")
    
    st.markdown("---")
    
    # Clear data option
    st.subheader("🗑️ Data Management")
    if st.button("Clear All Data", type="secondary"):
        if st.session_state.get('confirm_clear'):
            try:
                response = requests.delete(f"{API_BASE_URL}/data/clear")
                if response.status_code == 200:
                    st.success("✅ All data cleared")
                    st.session_state.confirm_clear = False
                    time.sleep(0.5)
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to clear data: {str(e)}")
        else:
            st.session_state.confirm_clear = True
            st.warning("⚠️ Click again to confirm deletion of all data")

# ============ TAB 2: RUN ALLOCATION ============
with tab2:
    st.header("Run Allocation Algorithm")
    
    if not data_status or not data_status.get("drivers_uploaded") or not data_status.get("orders_uploaded"):
        st.warning("⚠️ Please upload both drivers and orders data before running allocation")
    else:
        st.success(f"✅ Ready to allocate {data_status['orders_count']} orders to {data_status['drivers_count']} drivers")
        
        if st.button("🎯 Run Allocation", type="primary", use_container_width=True):
            with st.spinner("Running allocation algorithm... This may take a moment."):
                progress_bar = st.progress(0)
                for i in range(100):
                    time.sleep(0.01)
                    progress_bar.progress(i + 1)
                
                result, status = run_allocation()
                
                if status == 200:
                    st.success("✅ Allocation completed successfully!")
                    
                    # Show summary
                    col1, col2, col3, col4 = st.columns(4)
                    
                    summary = result.get("summary", {})
                    metrics = result.get("metrics", {})
                    
                    with col1:
                        st.metric(
                            "Total Orders",
                            summary.get("total_orders", 0)
                        )
                    
                    with col2:
                        st.metric(
                            "Allocated",
                            summary.get("allocated_orders", 0)
                        )
                    
                    with col3:
                        st.metric(
                            "Unallocated",
                            summary.get("unallocated_orders", 0)
                        )
                    
                    with col4:
                        utilization = metrics.get("average_utilization", 0)
                        st.metric(
                            "Avg Utilization",
                            f"{utilization:.1%}"
                        )
                    
                    # Warnings
                    if result.get("warnings"):
                        st.markdown("### ⚠️ Warnings")
                        for warning in result["warnings"]:
                            st.warning(warning)
                    
                    st.info("💡 Switch to 'View Results' tab to visualize the allocation")
                    
                else:
                    st.error(f"❌ Allocation failed: {result.get('detail', 'Unknown error')}")

# ============ TAB 3: VIEW RESULTS ============
with tab3:
    st.header("Allocation Results & Visualization")
    
    # Check if results exist
    if not data_status or not data_status.get("results_available"):
        st.info("ℹ️ No allocation results available. Please run allocation first.")
        st.stop()
    
    # ---- FILTERS ----
    st.sidebar.markdown("### 🔍 Filters")
    
    # Get unique regions and order types from results
    initial_results = get_results()
    if not initial_results:
        st.error("Failed to load results")
        st.stop()
    
    # Extract regions
    regions = set()
    order_types = {"All", "Wedding", "Corporate", "Regular"}
    
    for driver_data in initial_results.get("allocations", {}).values():
        region = driver_data.get("driver", {}).get("preferred_region")
        if region:
            regions.add(region)
    
    regions = sorted(list(regions))
    
    # Filter controls
    selected_region = st.sidebar.selectbox(
        "Filter by Region",
        ["All"] + regions,
        index=0,
        help="Filter drivers and orders by region"
    )
    
    selected_order_type = st.sidebar.selectbox(
        "Filter by Order Type",
        sorted(list(order_types)),
        index=0,
        help="Filter orders by type (Wedding, Corporate, Regular)"
    )
    
    # Apply filters
    filter_region = None if selected_region == "All" else selected_region
    filter_order_type = None if selected_order_type == "All" else selected_order_type
    
    # Get filtered results
    results = get_results(region=filter_region, order_type=filter_order_type)
    
    if not results:
        st.error("Failed to load filtered results")
        st.stop()
    
    # Show filter status
    if filter_region or filter_order_type:
        filter_info = []
        if filter_region:
            filter_info.append(f"Region: **{filter_region}**")
        if filter_order_type:
            filter_info.append(f"Order Type: **{filter_order_type}**")
        
        st.info(f"🔍 Filters active: {' | '.join(filter_info)}")
        st.caption(f"Showing {results.get('filtered_driver_count', 0)} of {results.get('original_driver_count', 0)} drivers")
    
    st.markdown("---")
    
    # ---- METRICS OVERVIEW ----
    metrics = results.get("metrics", {})
    summary = results.get("summary", {})
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Orders", summary.get("total_orders", 0))
    
    with col2:
        st.metric("Allocated", summary.get("allocated_orders", 0))
    
    with col3:
        st.metric("Unallocated", summary.get("unallocated_orders", 0))
    
    with col4:
        avg_util = metrics.get("average_utilization", 0)
        st.metric("Avg Utilization", f"{avg_util:.1%}")
    
    with col5:
        capacity_util = metrics.get("capacity_utilization", 0)
        st.metric("Capacity Used", f"{capacity_util:.1%}")
    
    st.markdown("---")
    
    # ---- DRIVER SELECTION ----
    driver_dict = results.get("allocations", {})
    
    if not driver_dict:
        st.warning("No drivers match the current filters")
        st.stop()
    
    driver_labels = []
    label_to_driver_id = {}
    
    for driver_id, driver_data in driver_dict.items():
        driver = driver_data["driver"]
        order_count = len(driver_data.get("assigned_orders", []))
        
        label = f"{driver.get('name', driver_id)} ({driver_id}) - {order_count} orders"
        driver_labels.append(label)
        label_to_driver_id[label] = driver_id
    
    selected_driver_label = st.selectbox(
        "Select Driver to View Route",
        driver_labels,
        index=0 if driver_labels else None,
        help="Pick a driver to view their route and assigned orders"
    )
    
    selected_driver_id = label_to_driver_id[selected_driver_label]
    selected_driver_data = driver_dict[selected_driver_id]
    
    # ---- DRIVER DETAILS ----
    driver = selected_driver_data["driver"]
    orders = selected_driver_data.get("assigned_orders", [])
    utilization = selected_driver_data.get("utilization", 0)
    
    # Header
    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
    
    with col1:
        st.markdown(f"**Driver:** `{driver.get('driver_id', '')}`")
        st.markdown(f"{driver.get('name', 'N/A')}")
    
    with col2:
        st.markdown(f"**Region:** {driver.get('preferred_region', 'N/A')}")
        caps = driver.get('capabilities', [])
        st.markdown(f"**Capabilities:** {', '.join(caps) if caps else 'Standard'}")
    
    with col3:
        max_orders = driver.get('max_orders_per_day', '?')
        st.markdown(f"**Capacity:** {len(orders)}/{max_orders}")
        st.progress(min(len(orders) / max_orders if max_orders != '?' else 0, 1.0))
    
    with col4:
        st.markdown(f"**Utilization:** {utilization:.0%}")
        color = "🟢" if utilization > 0.8 else "🟡" if utilization > 0.5 else "🔴"
        st.markdown(f"{color} {utilization:.0%}")
    
    st.markdown("---")
    
    # ---- MAP VISUALIZATION ----
    if not orders:
        st.warning("This driver has no assigned orders matching the current filters")
    else:
        # Prepare dataframe
        df = pd.DataFrame(orders)
        
        # Extract lat/lon
        if "lat" not in df.columns or "lon" not in df.columns:
            if "location" in df.columns:
                df["lat"] = df["location"].apply(lambda loc: loc.get("lat") if isinstance(loc, dict) else None)
                df["lon"] = df["location"].apply(
                    lambda loc: loc.get("lng") if isinstance(loc, dict) and "lng" in loc else (loc.get("lon") if isinstance(loc, dict) else None)
                )
        
        # Add order type
        df["order_type"] = df["tags"].apply(determine_order_type)
        
        # Check for missing coordinates
        if df["lat"].isnull().any() or df["lon"].isnull().any():
            st.error("⚠️ Some orders are missing latitude/longitude information")
            missing = df[df["lat"].isnull() | df["lon"].isnull()]
            st.dataframe(missing[["order_id", "location"]], use_container_width=True)
        else:
            # Sort by pickup time
            df = df.sort_values("pickup_time")
            
            # Create map
            map_center = [df["lat"].mean(), df["lon"].mean()]
            m = folium.Map(location=map_center, zoom_start=12)
            
            # Draw route
            route = list(zip(df["lat"], df["lon"]))
            folium.PolyLine(route, color="blue", weight=3, opacity=0.6, tooltip="Delivery Route").add_to(m)
            
            # Add markers
            for idx, row in df.iterrows():
                # Determine marker color
                order_type = row["order_type"]
                if order_type == "Wedding":
                    color = "red"
                    icon = "heart"
                elif order_type == "Corporate":
                    color = "purple"
                    icon = "briefcase"
                else:
                    color = "blue"
                    icon = "shopping-cart"
                
                popup_html = f"""
                <div style="font-family: Arial; min-width: 200px;">
                    <h4 style="margin: 0 0 10px 0; color: #333;">{row['order_id']}</h4>
                    <table style="width: 100%; font-size: 12px;">
                        <tr><td><b>Type:</b></td><td>{order_type}</td></tr>
                        <tr><td><b>Pickup:</b></td><td>{row['pickup_time']}</td></tr>
                        <tr><td><b>Teardown:</b></td><td>{row['teardown_time']}</td></tr>
                        <tr><td><b>Region:</b></td><td>{row['region']}</td></tr>
                        <tr><td><b>PAX:</b></td><td>{row.get('pax_count', 'N/A')}</td></tr>
                        <tr><td><b>Tags:</b></td><td>{', '.join(row.get('tags', []))}</td></tr>
                    </table>
                </div>
                """
                
                folium.Marker(
                    location=[row["lat"], row["lon"]],
                    popup=folium.Popup(popup_html, max_width=300),
                    icon=folium.Icon(color=color, icon=icon, prefix='fa'),
                    tooltip=f"{row['order_id']} - {order_type}"
                ).add_to(m)
            
            # Display map
            st_folium(m, width=None, height=500, use_container_width=True)
            
            # ---- ORDERS TABLE ----
            with st.expander("📋 Orders Table", expanded=False):
                display_df = df[[
                    "order_id", "order_type", "pickup_time", "teardown_time",
                    "region", "pax_count", "tags", "lat", "lon"
                ]].copy()
                
                # Style the dataframe
                def highlight_order_type(row):
                    if row['order_type'] == 'Wedding':
                        return ['background-color: #ffe6e6'] * len(row)
                    elif row['order_type'] == 'Corporate':
                        return ['background-color: #e6e6ff'] * len(row)
                    else:
                        return ['background-color: white'] * len(row)
                
                styled_df = display_df.style.apply(highlight_order_type, axis=1)
                st.dataframe(styled_df, hide_index=True, use_container_width=True)
    
    # ---- UNALLOCATED ORDERS ----
    with st.expander("🚫 Unallocated Orders", expanded=False):
        unallocated = results.get("unallocated_orders", [])
        if not unallocated:
            st.success("✅ All orders successfully allocated!")
        else:
            st.error(f"❌ {len(unallocated)} orders could not be allocated")
            
            unallocated_df = pd.DataFrame(unallocated)
            if "tags" in unallocated_df.columns:
                unallocated_df["order_type"] = unallocated_df["tags"].apply(determine_order_type)
            
            st.dataframe(unallocated_df, use_container_width=True, hide_index=True)
    
    # ---- METRICS & SUMMARY ----
    with st.expander("📊 Detailed Metrics & Summary", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Metrics")
            st.json(results.get("metrics", {}))
        
        with col2:
            st.subheader("Summary")
            st.json(results.get("summary", {}))
        
        # Warnings
        if results.get("warnings"):
            st.subheader("⚠️ Warnings")
            for warning in results["warnings"]:
                st.warning(warning)

# ---- FOOTER ----
st.markdown("---")
st.caption("🚚 Delivery Allocation System | Powered by FastAPI + Streamlit + Claude AI")