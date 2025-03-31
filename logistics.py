import streamlit as st
import pandas as pd
import requests
from geopy.distance import geodesic
import re
import googlemaps
# --- Google Maps API Key ---
GOOGLE_MAPS_API_KEY = st.secrets["google"]["maps_api_key"]
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)



# --- Function to Get Coordinates ---
def get_lat_lon(city):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={city}&key={GOOGLE_MAPS_API_KEY}"
    response = requests.get(url).json()
    if response["status"] == "OK":
        result = response["results"][0]
        location = result["geometry"]["location"]
        country = None
        for component in result["address_components"]:
            if "country" in component["types"]:
                country = component["long_name"]
                break
        return location["lat"], location["lng"], country
    else:
        print(f"Error fetching coordinates for {city}: {response.get('status')}")
    return None, None, None

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


# --- Function to Find a Specific Station in a City ---
def find_city_station(city):
    url = f"https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": f"{city} railway station",
        "type": "train_station",
        "key": GOOGLE_MAPS_API_KEY
    }
    response = requests.get(url, params=params).json()
    if response["status"] == "OK" and response["results"]:
        station = response["results"][0]
        station_name = station["name"]
        station_lat = station["geometry"]["location"]["lat"]
        station_lon = station["geometry"]["location"]["lng"]
        return station_name, (station_lat, station_lon)
    return None, None

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
            elif element["status"] == "OK":
                distance_km = round(geodesic(origin, destination).km, 2)
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

# --- Match Airport Name to City in airports_df ---
def match_airport_to_city(airport_name, lat, lon):
    # Try to find a matching city based on coordinates proximity
    for _, row in airports_df.iterrows():
        dist = geodesic((lat, lon), (row["Latitude"], row["Longitude"])).km
        if dist < 50:  # Consider it a match if within 50 km
            return row["City"]
    return airport_name  # Fallback to airport name if no match

def get_air_distance_by_city(origin_city, destination_city):
    """Find airline distance between two cities using OpenFlights data."""
    origin_airport = airports_df[airports_df["City"].str.lower() == origin_city.lower()]
    destination_airport = airports_df[airports_df["City"].str.lower() == destination_city.lower()]

    if not origin_airport.empty and not destination_airport.empty:

        origin_coords = (origin_airport.iloc[0]["Latitude"], origin_airport.iloc[0]["Longitude"])
        destination_coords = (destination_airport.iloc[0]["Latitude"], destination_airport.iloc[0]["Longitude"])

        distance= round(geodesic(origin_coords, destination_coords).km, 2)
        return distance
    return None

def extract_distance(value):
    if value is None:
        return 0.0
    if isinstance(value, str):
        match = re.search(r"[\d\.]+", value)  # Find number (including decimals)
        return float(match.group()) if match else 0.0  # Convert to float
    return float(value)


def extract_rail_distance(value):
    if value is None:
        return 0.0
    if isinstance(value, str):
        match = re.search(r"[\d,]+\.?\d*", value)
        if match:
            result = float(match.group(0).replace(',', ''))
            if result < 10:  # Arbitrary threshold for suspicion
                print(f"Warning: Extracted distance {result} km seems unusually small.")
            return result
        return 0.0
    return float(value)

# --- Streamlit UI ---
st.title("🚀 Multi Travel Calculator & Distance Finder")

# Initialize session state
if "travel_entries" not in st.session_state:
    st.session_state.travel_entries = [
        {"id": 0, "mode": "Road", "type": "Petrol", "origin": "", "destination": ""}
    ]

# Iterate through travel entries
for entry in st.session_state.travel_entries:
    index = entry["id"]
    cols = st.columns([3, 3, 3, 3, 2])

    with cols[0]:  # Travel Mode
        mode_options = ["Road", "Rail", "Air"]
        default_index = mode_options.index(entry["mode"]) if entry["mode"] in mode_options else 0
        mode = st.selectbox(
            f"Mode {index + 1}:", mode_options,
            key=f"mode_{index}", index=default_index
        )
        entry["mode"] = mode
    with cols[1]:
        if entry["mode"] == "Road":
            type_options = ["Auto CNG","Bike","Car Petrol", "Car CNG", "Electric bike", "Electric car"]
            default_type_index = type_options.index(entry["type"]) if entry["type"] in type_options else 0
            type = st.selectbox(
                f"Type {index + 1}:", type_options,
                key=f"type_{index}", index=default_type_index
            )
        elif entry["mode"] == "Rail":
            type_options = ["Electric", "Diesel"]
            default_type_index = type_options.index(entry["type"]) if entry["type"] in type_options else 0
            type = st.selectbox(
                f"Type {index + 1}:", type_options,
                key=f"type_{index}", index=default_type_index
            )
        else:  # Default case (e.g., Air)
            type_options = ["Domestic"]  # Adjust as needed
            default_type_index = 0
            type = st.selectbox(
                f"Type {index + 1}:", type_options,
                key=f"type_{index}", index=default_type_index
            )
        entry["type"] = type
            
              # Update entry with new selection

    with cols[2]:  # Origin City
        origin = st.text_input(f"Origin {index + 1}:", entry["origin"], key=f"origin_{index}")
        entry["origin"] = origin

    with cols[3]:  # Destination City
        destination = st.text_input(f"Destination {index + 1}:", entry["destination"], key=f"destination_{index}")
        entry["destination"] = destination

    with cols[4]:  # Remove Entry Button
        if st.button("Remove", key=f"remove_{index}"):
            st.session_state.travel_entries = [e for e in st.session_state.travel_entries if e["id"] != index]
            st.rerun()
    

# Add Another Trip
if st.button("Add Another Trip"):
    new_id = max([e["id"] for e in st.session_state.travel_entries], default=-1) + 1
    st.session_state.travel_entries.append({"id": new_id, "mode": "Road", "origin": "", "destination": ""})
    st.rerun()

# Calculate Distance for Each Entry and Total
if st.button("Calculate Distance"):
    total_distance = 0.0  # Initialize total distance accumulator
    total_emission = 0.0
    st.write("### Travel Distances")

    for entry in st.session_state.travel_entries:
        if not (entry["origin"].strip() and entry["destination"].strip()):
            st.warning("Please enter both origin and destination.")
            continue

        origin_lat, origin_lon, origin_country = get_lat_lon(entry["origin"])
        dest_lat, dest_lon, dest_country = get_lat_lon(entry["destination"])

        if entry["mode"] in ["Rail", "Road"] and (origin_country != "India" or dest_country != "India"):
            st.warning(f"{entry['mode']} travel is limited to India only. {entry['origin']} ({origin_country}) or {entry['destination']} ({dest_country}) is outside India.")
            continue
        origin_coords = (origin_lat, origin_lon)
        dest_coords = (dest_lat, dest_lon)

        if origin_coords and dest_coords:
            if entry["mode"] == "Air":
                origin_airport, origin_city, origin_airport_coords = find_nearest_place(*origin_coords, "airport")
                dest_airport, dest_city, dest_airport_coords = find_nearest_place(*dest_coords, "airport")

                if origin_airport and dest_airport and origin_airport_coords and dest_airport_coords:
                    to_airport = round(extract_distance(get_distance(origin_coords, origin_airport_coords, "driving")), 2)
                    air_distance_result = get_air_distance_by_city(origin_city, dest_city)  # Use matched cities
                    if air_distance_result is None:
                        st.success("Using nearest airports distance.")                                
                        air_distance = round(geodesic(origin_airport_coords, dest_airport_coords).km, 2)
                    else:
                        air_distance = round(air_distance_result, 2)
                    from_airport = round(extract_distance(get_distance(dest_airport_coords, dest_coords, "driving")), 2)

                    trip_total = round(to_airport + air_distance + from_airport, 2)
                    total_distance += trip_total
                    air_emissions = round(air_distance*1.58, 2)
                    total_emission += air_emissions

                    st.success(f"✈️ **Flight Distance**:")
                    st.write(f"🚗 {entry['origin']} → {origin_airport}: {to_airport} km")
                    st.write(f"✈️ {origin_airport} → {dest_airport}: {air_distance} km")
                    st.write(f"🚗 {entry['destination']} ← {dest_airport}: {from_airport} km")
                    st.write(f"📏 **Trip AIR Total**: {trip_total} km")
                    st.write(f"Emission for air distance: {air_emissions} kgco2e")

                else:
                    st.warning(f"Could not fetch location data for {entry['origin']} or {entry['destination']}.")

            elif entry["mode"] == "Rail":
                origin_station, origin_station_coords = find_city_station(entry["origin"])
                if not origin_station:
                    origin_station, origin_city, origin_station_coords = find_nearest_place(*origin_coords, "train_station")
                    if not origin_station:
                        st.warning(f"No railwaystation found near {entry['origin']}.")
                dest_station, dest_station_coords = find_city_station(entry["destination"])
                if not dest_station:
                    dest_station, dest_city, dest_station_coords = find_nearest_place(*dest_coords, "train_station")
                    if not dest_station:
                        st.warning(f"No railwaystation found near {entry['destination']}.")

                if origin_station and dest_station:
                    rail_distance = get_distance(origin_station_coords, dest_station_coords, "transit")
                    rail_distance_value = round(extract_rail_distance(rail_distance), 4)
                    total_distance += rail_distance_value  # Add to total

                    st.success(f"🚆 **Rail Distance**:")
                    st.write(f"🚉 **{origin_station} → {dest_station}**: {rail_distance_value} km")
                    emission = 0.0
                    if entry["type"] == "Electric":
                        emission = rail_distance_value*0.82
                        st.write(f"🚉 Emission for Electric  rail from **{origin_station} → {dest_station}**: {emission} kgco2e")
                    else:
                        emission = rail_distance_value*2.651
                        st.write(f"🚉 Emission Diesel rail from **{origin_station} → {dest_station}**: {emission} kgco2e")
                    total_emission += emission
                else:
                    st.warning("Could not find nearby railway stations.")

            else:  # Road Mode
                road_distance = get_distance(origin_coords, dest_coords, "driving")
                road_distance_value = round(extract_distance(road_distance), 2)
                total_distance += road_distance_value  # Add to total

                st.write(f"🚗 Road Distance from {entry['origin']} → {entry['destination']}: {road_distance_value} km")
                emission_road = 0.0
                if entry["type"] == "Auto CNG":
                    emission_road = road_distance_value*0.107
                elif entry["type"] == "Bike":
                    emission_road = road_distance_value*0.049
                elif entry["type"] == "Car Petrol":
                    emission_road = road_distance_value*0.187
                elif entry["type"] == "Electric bike":
                    emission_road = road_distance_value*0.031
                elif entry["type"] == "Car CNG":
                    emission_road = road_distance_value*0.68
                else:
                    emission_road = road_distance_value * 0.012
                total_emission += emission_road
                
                
        else:
            st.warning(f"Could not fetch location data for {entry['origin']} or {entry['destination']}.")

    # Display the total distance across all entries
    total_distance = round(total_distance, 2)  # Round the final total
    if total_distance > 0 and total_emission > 0:
        st.write("---")
        st.success(f"🌍 **Total Distance Across All Trips**: {total_distance} km")
        st.success(f"🌍 **Total Emission Across All Trips**: {total_emission} kgco2e")
    else:
        st.info("No valid distances calculated.")

