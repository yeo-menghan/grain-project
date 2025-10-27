import streamlit as st
import json
import pandas as pd
from streamlit_folium import st_folium
import folium
from pathlib import Path
from datetime import datetime

# ---- CONFIG ----
st.set_page_config(
    page_title="Delivery Allocation System",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# File paths - adjust based on where you run streamlit from
DATA_DIR = Path("./data")
if not DATA_DIR.exists():
    DATA_DIR = Path("../data")  # Try parent directory
if not DATA_DIR.exists():
    DATA_DIR = Path("../../data")  # Try grandparent directory

DRIVERS_FILE = DATA_DIR / "drivers.json"
ORDERS_FILE = DATA_DIR / "orders.json"
RESULTS_FILE = DATA_DIR / "allocation_results.json"

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
def load_json_file(filepath):
    """Load JSON file"""
    try:
        if filepath.exists():
            with open(filepath, 'r') as f:
                return json.load(f)
    except Exception as e:
        st.error(f"Error loading {filepath.name}: {str(e)}")
    return None

def get_data_status():
    """Check which data files exist"""
    status = {
        "drivers_exists": DRIVERS_FILE.exists(),
        "orders_exists": ORDERS_FILE.exists(),
        "results_exists": RESULTS_FILE.exists(),
        "drivers_count": 0,
        "orders_count": 0
    }
    
    if status["drivers_exists"]:
        drivers = load_json_file(DRIVERS_FILE)
        if drivers:
            status["drivers_count"] = len(drivers)
    
    if status["orders_exists"]:
        orders = load_json_file(ORDERS_FILE)
        if orders:
            status["orders_count"] = len(orders)
    
    return status

def determine_order_type(tags):
    """Determine order type from tags"""
    if isinstance(tags, list):
        if any(tag in tags for tag in ["wedding", "vip", "large_events"]):
            return "Wedding"
        elif "corporate" in tags:
            return "Corporate"
    return "Regular"

def filter_results(results, region=None, order_type=None):
    """Filter allocation results by region and/or order type"""
    if not results:
        return None
    
    filtered = {
        "allocations": {},
        "unallocated_orders": [],
        "metrics": results.get("metrics", {}),
        "summary": results.get("summary", {}),
        "warnings": results.get("warnings", [])
    }
    
    allocations = results.get("allocations", {})
    
    for driver_id, driver_data in allocations.items():
        driver = driver_data.get("driver", {})
        driver_region = driver.get("preferred_region")
        assigned_orders = driver_data.get("assigned_orders", [])
        
        # Filter by region
        if region and region != "All" and driver_region != region:
            continue
        
        # Filter orders by type if specified
        if order_type and order_type != "All":
            filtered_orders = []
            for order in assigned_orders:
                tags = order.get("tags", [])
                order_order_type = determine_order_type(tags)
                
                if order_order_type == order_type:
                    filtered_orders.append(order)
            
            # Only include driver if they have matching orders
            if filtered_orders:
                driver_data_copy = driver_data.copy()
                driver_data_copy["assigned_orders"] = filtered_orders
                filtered["allocations"][driver_id] = driver_data_copy
        else:
            # No order type filter, include all orders for this driver
            filtered["allocations"][driver_id] = driver_data
    
    # Filter unallocated orders
    for order in results.get("unallocated_orders", []):
        # Filter by region
        if region and region != "All" and order.get("region") != region:
            continue
        
        # Filter by order type
        if order_type and order_type != "All":
            tags = order.get("tags", [])
            order_order_type = determine_order_type(tags)
            if order_order_type != order_type:
                continue
        
        filtered["unallocated_orders"].append(order)
    
    filtered["filtered_driver_count"] = len(filtered["allocations"])
    filtered["original_driver_count"] = len(allocations)
    
    return filtered

# ---- MAIN APP ----
st.markdown('<div class="main-header">🚚 Delivery Allocation System</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Visualize driver routes and allocation results</div>', unsafe_allow_html=True)

# Check data availability
data_status = get_data_status()

if not DATA_DIR.exists():
    st.error(f"⚠️ Data directory not found. Looking for: {DATA_DIR.absolute()}")
    st.info("Please ensure you're running this from the correct directory or that the data folder exists.")
    st.stop()

st.info(f"📁 Data directory: `{DATA_DIR.absolute()}`")

# ============ SIDEBAR ============
st.sidebar.title("📋 Data Status")

# Data Status
status_col1, status_col2 = st.sidebar.columns(2)

with status_col1:
    st.metric("Drivers", data_status.get("drivers_count", 0))
    st.markdown("✅" if data_status.get("drivers_exists") else "❌")

with status_col2:
    st.metric("Orders", data_status.get("orders_count", 0))
    st.markdown("✅" if data_status.get("orders_exists") else "❌")

if data_status.get("results_exists"):
    st.sidebar.success("✅ Allocation results available")
else:
    st.sidebar.warning("⚠️ No allocation results found")
    st.sidebar.info("Run the allocator first:\n```bash\npython -m allocator.main\n```")

st.sidebar.markdown("---")

# ============ MAIN CONTENT ============

if not data_status.get("results_exists"):
    st.warning("⚠️ No allocation results found. Please run the allocation algorithm first.")
    st.code("python -m allocator.main", language="bash")
    st.stop()

# Load results
results = load_json_file(RESULTS_FILE)

if not results:
    st.error("Failed to load allocation results")
    st.stop()

# ---- FILTERS ----
st.sidebar.markdown("### 🔍 Filters")

# Extract regions
regions = set()
for driver_id, driver_data in results.get("allocations", {}).items():
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
    ["All", "Wedding", "Corporate", "Regular"],
    index=0,
    help="Filter orders by type"
)

# Apply filters
filtered_results = filter_results(
    results,
    region=selected_region if selected_region != "All" else None,
    order_type=selected_order_type if selected_order_type != "All" else None
)

# Show filter status
if selected_region != "All" or selected_order_type != "All":
    filter_info = []
    if selected_region != "All":
        filter_info.append(f"Region: **{selected_region}**")
    if selected_order_type != "All":
        filter_info.append(f"Order Type: **{selected_order_type}**")
    
    st.info(f"🔍 Filters active: {' | '.join(filter_info)}")
    st.caption(f"Showing {filtered_results.get('filtered_driver_count', 0)} of {filtered_results.get('original_driver_count', 0)} drivers")

st.markdown("---")

# ---- METRICS OVERVIEW ----
metrics = filtered_results.get("metrics", {})
summary = filtered_results.get("summary", {})

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("Total Orders", summary.get("total_orders", 0))

with col2:
    st.metric("Allocated", summary.get("orders_allocated", 0))

with col3:
    st.metric("Unallocated", summary.get("orders_unallocated", 0))

with col4:
    region_match = metrics.get("region_match_rate", 0)
    st.metric("Region Match", f"{region_match:.1%}")

with col5:
    average_orders_per_driver = metrics.get("average_orders_per_driver", 0)
    st.metric("Avg Orders/Driver", f"{average_orders_per_driver:.1f}")

st.markdown("---")

# ---- DRIVER SELECTION ----
driver_dict = filtered_results.get("allocations", {})

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
    max_orders = driver.get('max_orders_per_day', 0)
    st.markdown(f"**Capacity:** {len(orders)}/{max_orders}")
    if max_orders > 0:
        st.progress(min(len(orders) / max_orders, 1.0))

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
                return ['background-color: black'] * len(row)
            
            styled_df = display_df.style.apply(highlight_order_type, axis=1)
            st.dataframe(styled_df, hide_index=True, use_container_width=True)

# ---- UNALLOCATED ORDERS ----
with st.expander("🚫 Unallocated Orders", expanded=False):
    unallocated = filtered_results.get("unallocated_orders", [])
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
        st.json(filtered_results.get("metrics", {}))
    
    with col2:
        st.subheader("Summary")
        st.json(filtered_results.get("summary", {}))
    
    # Warnings
    if filtered_results.get("warnings"):
        st.subheader("⚠️ Warnings")
        for warning in filtered_results["warnings"]:
            st.warning(warning)

# ---- FOOTER ----
st.markdown("---")
st.caption("🚚 Delivery Allocation System | Standalone Frontend")