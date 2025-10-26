import streamlit as st
import folium
from streamlit_folium import st_folium

# Create a folium map centered at some coordinates
m = folium.Map(location=[37.7749, -122.4194], zoom_start=12)

# Add a marker
folium.Marker([37.7749, -122.4194], popup="San Francisco").add_to(m)

# Display map in Streamlit
st_folium(m, width=700, height=500)
