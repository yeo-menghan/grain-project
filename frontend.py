import streamlit as st
import json
import pandas as pd
from streamlit_folium import st_folium
import folium

# ---- CONFIG ----
st.set_page_config(page_title="Delivery Allocation Visualizer", layout="wide")

# ---- LOAD DATA ----
@st.cache_data
def load_allocation(file_path):
    with open(file_path, "r") as f:
        return json.load(f)

# ---- MAIN APP ----
st.title("🚚 Delivery Allocation Visualizer")
st.caption("View each driver's allocated orders, locations, and time windows.")

# --- File Upload/Load ---
# allocation_file = st.sidebar.file_uploader("Upload Allocation JSON", type=["json"], help="Exported by allocator.py")
# if not allocation_file:
#     st.info("Please upload an allocation JSON file.")
#     st.stop()

# data = load_allocation(allocation_file)

DEFAULT_PATH = "./data/allocation_results.json"
try:
    data = load_allocation(DEFAULT_PATH)
except FileNotFoundError:
    st.error(f"Default file {DEFAULT_PATH} not found. Please run allocator.py first or upload a results file.")
    st.stop()

driver_dict = data["allocations"]
driver_ids = list(driver_dict.keys())
driver_labels = [
    f"{drv['driver']['driver_id']} - {drv['driver']['name']}" if 'name' in drv['driver'] else drv['driver']['driver_id']
    for drv in driver_dict.values()
]

driver_id_to_label = {drv['driver']['driver_id']: label for drv, label in zip(driver_dict.values(), driver_labels)}
label_to_driver_id = {label: drv['driver']['driver_id'] for drv, label in zip(driver_dict.values(), driver_labels)}

# --- SIDEBAR: DRIVER SELECT ---
selected_driver_label = st.sidebar.selectbox(
    "Select Driver",
    driver_labels,
    index=0 if driver_labels else None,
    help="Pick a driver to view their route and orders."
)
selected_driver_id = label_to_driver_id[selected_driver_label]
selected_driver = driver_dict[selected_driver_id]

# ---- DRIVER SUMMARY ----
driver = selected_driver["driver"]
orders = selected_driver["assigned_orders"]
utilization = selected_driver.get("utilization", 0)

# --- Top Summary ---
cols = st.columns([2,2,2,2])
cols[0].markdown(f"**Driver:** `{driver.get('driver_id','')}`<br>{driver.get('name','')}", unsafe_allow_html=True)
cols[1].markdown(f"**Region:** {driver.get('preferred_region','')}")
cols[2].markdown(f"**Capacity:** {len(orders)}/{driver.get('max_orders_per_day', '?')}")
cols[3].markdown(f"**Utilization:** {utilization:.0%}")

st.markdown("---")

# ---- MAP VISUALIZATION ----
if not orders:
    st.warning("This driver has no assigned orders.")
else:
    # Data for map/table
    df = pd.DataFrame(orders)
    if "lat" not in df.columns or "lon" not in df.columns:
        if "location" in df.columns:
            df["lat"] = df["location"].apply(lambda loc: loc.get("lat") if isinstance(loc, dict) else None)
            # Accept both 'lng' and 'lon'
            df["lon"] = df["location"].apply(
                lambda loc: loc.get("lng") if isinstance(loc, dict) and "lng" in loc else (loc.get("lon") if isinstance(loc, dict) else None)
            )

    if df["lat"].isnull().any() or df["lon"].isnull().any():
        st.error("Some orders are missing latitude/longitude information.")
    else:
        # Sort by pickup_time
        df = df.sort_values("pickup_time")
        # Map center: mean of points
        map_center = [df["lat"].mean(), df["lon"].mean()]

        m = folium.Map(location=map_center, zoom_start=12, height="80%")

        # Draw route line (in pickup order)
        route = list(zip(df["lat"], df["lon"]))
        folium.PolyLine(route, color="blue", weight=3, opacity=0.6).add_to(m)

        # Add markers
        for idx, row in df.iterrows():
            popup = f"""
            <b>Order ID:</b> {row['order_id']}<br>
            <b>Pickup:</b> {row['pickup_time']}<br>
            <b>Teardown:</b> {row['teardown_time']}<br>
            <b>Region:</b> {row['region']}<br>
            <b>Tags:</b> {', '.join(row.get('tags', []))}
            """
            folium.Marker(
                location=[row["lat"], row["lon"]],
                popup=popup,
                icon=folium.Icon(color="red" if "wedding" in row.get("tags", []) or "vip" in row.get("tags", []) else "blue"),
                tooltip=row["order_id"]
            ).add_to(m)

        # Show map
        st_folium(m, width=900, height=500)

        # ---- Order Table ----
        show_table = st.expander("Show Orders Table", expanded=True)
        with show_table:
            display_df = df[["order_id", "pickup_time", "teardown_time", "region", "pax_count", "tags", "lat", "lon"]]
            display_df["order_type"] = display_df["tags"].apply(
                lambda t: "Wedding" if any(x in t for x in ("wedding", "vip", "large_events")) else ("Corporate" if "corporate" in t else "Regular")
            )
            st.dataframe(
                display_df[["order_id","order_type","pickup_time","teardown_time","region","pax_count","tags","lat","lon"]],
                hide_index=True,
                use_container_width=True
            )

# ---- UNALLOCATED ORDERS ----
with st.expander("Show Unallocated Orders"):
    unallocated = data.get("unallocated_orders", [])
    if not unallocated:
        st.success("No unallocated orders!")
    else:
        st.error(f"{len(unallocated)} orders were **not allocated**.")
        st.dataframe(pd.DataFrame(unallocated), use_container_width=True)

# ---- METRICS ----
with st.expander("Show Allocation Metrics & Summary"):
    st.json(data.get("metrics", {}), expanded=False)
    st.json(data.get("summary", {}), expanded=False)
    if "warnings" in data and data["warnings"]:
        st.warning("Warnings:")
        for w in data["warnings"]:
            st.markdown(f"- {w}")