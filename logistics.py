import streamlit as st
import pandas as pd
import requests
from geopy.distance import geodesic
import re

# --- Google Maps API Key ---
GOOGLE_MAPS_API_KEY = "AIzaSyAr3YAZlR8CNcjPoRA4hV_ePS93bCF39EQ"

# --- Function to Get Coordinates ---
def get_lat_lon(city):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={city}&key={GOOGLE_MAPS_API_KEY}"
    response = requests.get(url).json()
    if response["status"] == "OK":
        location = response["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]
    return None

def get_near_city(lat, lon):
    # use reverse geocoding api to get correct city name for coordinates
    url = f"https://maps.googleapis.com/maps/api/geocode/json"
    parms = {
        "latlng": f"{lat},{lon}",
        "key": GOOGLE_MAPS_API_KEY
    }
    response = requests.get(url, params=parms).json()

    if response["status"] == "OK":
        city_name = None
        district_name = None
        for result in response["results"]:
            for component in result["address_components"]:
                if "locality" in component["types"]:
                    city_name =  component["long_name"]
                if "administrative_area_level_2" in component["types"]:
                    district_name =  component["long_name"]
        return city_name if city_name else district_name
    return "Unknown City"

# --- Function to Find Nearest Transport Hub (Airport/Railway) ---
def find_nearest_place(lat, lon, place_type):
    url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lon}",
        "radius": 50000,  # Search within 50 km
        "type": place_type,  # "airport" or "train_station"
        "key": GOOGLE_MAPS_API_KEY
    }
    response = requests.get(url, params=params).json()
    if response["status"] == "OK" and response["results"]:
        nearest_place = response["results"][0]
        place_name = nearest_place["name"]
        place_lat = nearest_place["geometry"]["location"]["lat"]
        place_lon = nearest_place["geometry"]["location"]["lng"]
        city_name = get_near_city(place_lat, place_lon)
        return place_name, city_name, (place_lat, place_lon)
    return None, None, None

# --- Function to Get Distance between Two Places ---
def get_distance(origin, destination, mode):
    url = f"https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": f"{origin[0]},{origin[1]}",
        "destinations": f"{destination[0]},{destination[1]}",
        "mode": mode,  # "driving", "transit"
        "key": GOOGLE_MAPS_API_KEY
    }
    response = requests.get(url, params=params).json()

    if "rows" in response and response["rows"]:
        element = response["rows"][0]["elements"][0]
        if "status" in element:
            if element["status"] == "OK":
                return element["distance"]["text"]
        elif element["status"] == "ZERO_RESULTS":
            return "No results found"
        else:
            return "Error: " + element["status"]
    return "N/A"

# --- Load OpenFlights Data ---
routes_cols = ["Airline", "Airline_ID", "Source_Airport", "Source_Airport_ID", 
               "Destination_Airport", "Destination_Airport_ID", "Codeshare", 
               "Stops", "Equipment"]

airports_cols = ["Airport_ID", "Name", "City", "Country", "IATA", "ICAO", 
                 "Latitude", "Longitude", "Altitude", "Timezone", "DST", 
                 "Tz_database", "Type", "Source"]

# Load CSV Data
routes_df = pd.read_csv("../routes.csv", names=routes_cols, usecols=["Source_Airport", "Destination_Airport"])
airports_df = pd.read_csv('../airports.csv', names=airports_cols, usecols=["Name","City", "IATA", "Latitude", "Longitude"])


def get_air_distance_by_city(origin_city, destination_city):
    """Find airline distance between two cities using OpenFlights data."""
    origin_airport = airports_df[airports_df["City"].str.lower() == origin_city.lower()]
    destination_airport = airports_df[airports_df["City"].str.lower() == destination_city.lower()]

    if not origin_airport.empty and not destination_airport.empty:
        print(f"Origin Airport: {origin_airport.iloc[0]['Name']} ({origin_airport.iloc[0]['City']})")
        print(f"Destination Airport: {destination_airport.iloc[0]['Name']} ({destination_airport.iloc[0]['City']})")

        origin_coords = (origin_airport.iloc[0]["Latitude"], origin_airport.iloc[0]["Longitude"])
        destination_coords = (destination_airport.iloc[0]["Latitude"], destination_airport.iloc[0]["Longitude"])

        print("Origin Coordinates:", origin_coords)
        print("Destination Coordinates:", destination_coords)
        distance= round(geodesic(origin_coords, destination_coords).km, 2)
        print("COrrect air distance:", distance)
        return distance
    return None

def extract_distance(value):
    """Extracts the numeric distance from a string like '3.3 km' or returns float directly."""
    if isinstance(value, str):
        match = re.search(r"[\d\.]+", value)  # Find number (including decimals)
        return float(match.group()) if match else 0.0  # Convert to float
    return float(value)
# --- Streamlit UI ---
st.title("🚀 Multi-Mode Distance Calculator")

# --- User Input ---
origin_city = st.text_input("Enter Origin City", "Tenali")
destination_city = st.text_input("Enter Destination City", "Delhi")
mode = st.radio("Select Mode of Transport", ["Rail", "Road", "Air"])

if st.button("Calculate Distance"):
    with st.spinner("Fetching distance..."):
        origin_coords = get_lat_lon(origin_city)
        dest_coords = get_lat_lon(destination_city)

        if origin_coords and dest_coords:
            if mode == "Air":
                # Get Nearest Airports
                origin_airport, o_city, origin_airport_coords = find_nearest_place(*origin_coords, "airport")
                dest_airport,d_city,  dest_airport_coords = find_nearest_place(*dest_coords, "airport")
                
                if origin_airport and dest_airport:
                    # Compute Distances
                    to_airport = get_distance(origin_coords, origin_airport_coords, "driving")
                    air_distance = get_air_distance_by_city(o_city, d_city)
                    if not air_distance:
                        air_distance = get_air_distance_by_city(origin_city, destination_city)
                    from_airport = get_distance(dest_airport_coords, dest_coords, "driving")

                    # Display Results
                    st.success(f"✈️ **Air Travel Distance**:\n")
                    st.write(f"🚗 **{origin_city} → {origin_airport}**: {to_airport}")
                    if air_distance is None or 0.0:
                        st.warning("Enter City Big city names near by AirPort")
                        origin_city = st.text_input("Enter Origin City", key = "HO")
                        destination_city = st.text_input("Enter Destination City", key = "HG")
                        air_distance = get_air_distance_by_city(origin_city, destination_city)

                        
                    else:
                        st.write(f"✈️ **{o_city} → {d_city}**: {air_distance}")
                    st.write(f"🚗 **{dest_airport} → {destination_city}**: {from_airport}")
                    to_airport = extract_distance(to_airport)
                    air_distance = extract_distance(air_distance)
                    from_airport = extract_distance(from_airport)
                    
                    st.write("Total Distance:", to_airport + air_distance + from_airport)

                else:
                    st.warning("Could not find nearby airports.")

            elif mode == "Rail":
                # Get Nearest Railway Stations
                origin_station, o_city, origin_station_coords = find_nearest_place(*origin_coords, "train_station")
                dest_station,d_city, dest_station_coords = find_nearest_place(*dest_coords, "train_station")

                if origin_station and dest_station:
                    rail_distance = get_distance(origin_station_coords, dest_station_coords, "transit")
                    st.success(f"🚆 **Rail Distance**:\n")
                    st.write(f"🚉 **{origin_station} → {dest_station}**: {rail_distance}")

                else:
                    st.warning("Could not find nearby railway stations.")

            else:  # Road Mode
                road_distance = get_distance(origin_coords, dest_coords, "driving")
                st.success(f"🚗 **Road Distance**: {road_distance}")

        else:
            st.warning("Could not fetch location data.")


