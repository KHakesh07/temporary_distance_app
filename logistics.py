import streamlit as st
import pandas as pd
import requests
from geopy.distance import geodesic

# --- Load OpenFlights Data ---
routes_cols = ["Airline", "Airline_ID", "Source_Airport", "Source_Airport_ID", 
               "Destination_Airport", "Destination_Airport_ID", "Codeshare", 
               "Stops", "Equipment"]

airports_cols = ["Airport_ID", "Name", "City", "Country", "IATA", "ICAO", 
                 "Latitude", "Longitude", "Altitude", "Timezone", "DST", 
                 "Tz_database", "Type", "Source"]

# Load CSV Data
routes_df = pd.read_csv("routes.csv", names=routes_cols, usecols=["Source_Airport", "Destination_Airport"])
airports_df = pd.read_csv('airports.csv', names=airports_cols, usecols=["City", "IATA", "Latitude", "Longitude"])

# --- Function to Get Air Distance ---
def get_air_distance_by_city(origin_city, destination_city):
    """Find airline distance between two cities using OpenFlights data."""
    origin_airport = airports_df[airports_df["City"].str.lower() == origin_city.lower()]
    destination_airport = airports_df[airports_df["City"].str.lower() == destination_city.lower()]

    if not origin_airport.empty and not destination_airport.empty:
        origin_coords = (origin_airport.iloc[0]["Latitude"], origin_airport.iloc[0]["Longitude"])
        destination_coords = (destination_airport.iloc[0]["Latitude"], destination_airport.iloc[0]["Longitude"])
        return round(geodesic(origin_coords, destination_coords).km, 2)
    
    return None

# --- Function to Get Lat/Lon from Nominatim API ---
def get_lat_lon(city):
    """Fetch latitude & longitude using OpenStreetMap's Nominatim API."""
    url = f"https://nominatim.openstreetmap.org/search?q={city}&format=json"
    headers = {"User-Agent": "LogisticsApp/1.0 (your_email@example.com)"}  

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except requests.exceptions.RequestException:
        return None

    return None

# --- Function to Get Road & Rail Distances from GraphHopper API ---
def get_distance_graphhopper(origin, destination, mode):
    """Get distance between two points using GraphHopper API."""
    GH_API_KEY = "57da7ad6-4516-4f0d-a376-19a5fce5324f"  # Replace with your GraphHopper API key
    base_url = "https://graphhopper.com/api/1/route"

    origin_coords = get_lat_lon(origin)
    dest_coords = get_lat_lon(destination)

    if origin_coords and dest_coords:
        params = {
            "point": [f"{origin_coords[0]},{origin_coords[1]}", f"{dest_coords[0]},{dest_coords[1]}"],
            "profile": mode,  # 'car' for road, 'rail' for rail
            "calc_points": "false",
            "key": GH_API_KEY,
        }
        
        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()
            return round(data["paths"][0]["distance"] / 1000, 2)  # Convert meters to km
        except requests.exceptions.RequestException:
            return None

    return None

# --- Streamlit UI ---
st.title("📍 Logistics Distance Calculator")

# Input fields for origin & destination
origin_city = st.text_input("Enter Origin City", "Mumbai")
destination_city = st.text_input("Enter Destination City", "Bengaluru")

if st.button("Calculate Distances"):
    with st.spinner("Fetching distances..."):
        # Get Air Distance
        air_distance = get_air_distance_by_city(origin_city, destination_city)
        
        # Get Road & Rail Distances
        road_distance = get_distance_graphhopper(origin_city, destination_city, "car")
        rail_distance = get_distance_graphhopper(origin_city, destination_city, "rail")

    # Display Results
    st.subheader("📍 Distance Results")
    if air_distance:
        st.success(f"✈️ Air Distance: {air_distance} km")
    else:
        st.warning("Air distance data not available.")

    if road_distance:
        st.success(f"🚗 Road Distance: {road_distance} km")
    else:
        st.warning("Road distance data not available.")

    if rail_distance:
        st.success("For ttrack Need to be Implemented")
    else:
        st.warning("Rail distance data not available.")
