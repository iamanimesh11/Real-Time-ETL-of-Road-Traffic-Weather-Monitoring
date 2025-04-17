import requests,sys,os,random


AIRFLOW_HOME = os.getenv("AIRFLOW_HOME", "/opt/airflow")  # Default to Airflow's path

if AIRFLOW_HOME != "/opt/airflow":
    BASE_DIR = os.path.abspath(os.path.join(AIRFLOW_HOME, ".."))  
    print("BASE_DIR:", BASE_DIR) 
    AIRFLOW_HOME = BASE_DIR


CREDENTIALS_PATH = os.path.join(AIRFLOW_HOME, "common", "credentials")
COMMON_PATH = os.path.join(AIRFLOW_HOME, "common", "logging_and_monitoring")
sys.path.append(COMMON_PATH)
COMMON_PATH = os.path.join(AIRFLOW_HOME, "common","logging_and_monitoring","logs") 
sys.path.append(COMMON_PATH)

from utils.firebase_db_api_track_util import ApiMonitor
from centralized_logging import setup_logger
Script_logs_path=os.path.join(COMMON_PATH, "api_utils.log")

road_logger = setup_logger("Road_Data_ETL", "api_utils", "python", Script_logs_path)

traffic_logger = setup_logger("Traffic_Data_ETL", "api_utils", "python", Script_logs_path)

monitor = ApiMonitor()
Wmonitor = ApiMonitor()

TOMTOM_API_KEY = monitor.get_api_key("tomtom_key")
Weather_API_key = Wmonitor.get_api_key("weather_key")

if TOMTOM_API_KEY is not None:
    traffic_logger.info("Tomtom API key fetched success")
else:
    traffic_logger.critical("Tomtom API key fetched failed")

if Weather_API_key is not None:
    traffic_logger.info("weather API key fetched success") 

else:
    traffic_logger.critical("weather API key fetched failed") 

count, failures, is_down = monitor.get_status("tomtom")
wcount, wfailures, wis_down = Wmonitor.get_status("weather")

def tomtom_api(lat, lon):
    
    url = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"

    try:
        # Add a small random offset to avoid cached responses
        lat += random.uniform(-0.0005, 0.0005)
        lon += random.uniform(-0.0005, 0.0005)

        # Use a params dictionary for cleaner URL building
        params = {
            "point": f"{lat},{lon}",
            "key": TOMTOM_API_KEY,
            "realTime": "true"
        }
        response = requests.get(url, params=params, verify=False)
        safe_params = {k: v for k, v in params.items() if k != "key"}

        traffic_logger.info(f"Calling TomTom API for route: {url},parameter:{safe_params}", extra={"stage": "tomtom_api"})

        if response.status_code == 200:
            traffic_logger.info(f"Response: {response.status_code}", extra={"stage": "tomtom_api"})
            monitor.increment_api_count("tomtom")
            monitor.reset_failure_count("tomtom")
            monitor.mark_api_status("tomtom", False)
            return response.json()  # ✅ API call successful

        elif response.status_code == 429:
            # ✅ API rate limit hit
            traffic_logger.warning("TomTom API limit reached. Status: 429", extra={"stage": "tomtom_api"})
            monitor.increment_failure("tomtom")
            return {
                "error": "TomTom API limit reached. Please try again tomorrow."
            }

        else:
            # Handle other errors
            traffic_logger.error(f"Error fetching traffic data: {response.status_code} - {response.text}", extra={"stage": "tomtom_api"})

    except requests.RequestException as e:
        traffic_logger.critical(f"Network error fetching traffic data: {e}", extra={"stage": "tomtom_api"})
        monitor.increment_failure("tomtom")
    except Exception as e:
        monitor.increment_failure("tomtom")
        traffic_logger.critical(f"Unexpected error querying point ({lat}, {lon}): {e}", extra={"stage": "tomtom_api"})
    return None  # Return None if an error occurs



def get_weather_data(lat, lon):
    url = "http://api.weatherapi.com/v1/current.json"

    traffic_logger.info(f"get_weather_data() begins {Weather_API_key}", extra={"stage": "get_weather_data"})

    try:
        params = {
            "key": Weather_API_key,
            "q": f"{lat},{lon}"
        }

        response = requests.get(url, params=params,timeout=10)
        response.raise_for_status()  # Raise an error for bad HTTP responses (4xx, 5xx)

        data = response.json()
        current = data.get("current", {})
        Wmonitor.increment_api_count("weather")
        Wmonitor.reset_failure_count("weather")
        Wmonitor.mark_api_status("weather", False)
        # Extract weather data safely
        weather_conditions = current.get("condition", {}).get("text", "Unknown")
        temperature = float(current.get("temp_c", 0.0))
        humidity = float(current.get("humidity", 0.0))

        traffic_logger.info(f"Weather data fetched successfully ,weather_condition:{weather_conditions},temperature:{temperature},humidity:{humidity}", extra={"stage": "get_weather_data"})

        return weather_conditions, temperature, humidity

    except requests.exceptions.RequestException as e:
        traffic_logger.error(f"Network error: {e}", extra={"stage": "get_weather_data"})
        Wmonitor.increment_failure("weather")

    except (ValueError, KeyError) as e:
        traffic_logger.error(f"Data parsing error: {e}", extra={"stage": "get_weather_data"})
        Wmonitor.increment_failure("weather")

    return None, None, None  # Return None values on failure



def get_route(start_lat, start_lon, end_lat, end_lon):
    try:
        url = f"https://api.tomtom.com/routing/1/calculateRoute/{start_lat},{start_lon}:{end_lat},{end_lon}/json?key={TOMTOM_API_KEY}"

        safe_url = url.replace(TOMTOM_API_KEY, "****")
        road_logger.info(f"Calling TomTom API for route: {safe_url}", extra={"stage": "get_route"})
        headers={"Host":"api.tomtom.com"}

        response = requests.get(url, verify=False,timeout=30)  # Added timeout for reliability
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx, 5xx)
        monitor.increment_api_count("tomtom")
        monitor.reset_failure_count("tomtom")
        monitor.mark_api_status("tomtom", False)
        data = response.json()
        # Check if "routes" key exists and has data
        if not data.get("routes"):
            road_logger.warning(f"No route found for coordinates ({start_lat}, {start_lon}) -> ({end_lat}, {end_lon})",
                                  extra={"stage": "get_route"})
            return None, None
        
        route_legs = data["routes"][0].get("legs", [])
        
        if not route_legs:
            road_logger.warning(f"Route legs missing for ({start_lat}, {start_lon}) -> ({end_lat}, {end_lon})",
                                  extra={"stage": "get_route"})
            return None, None

        points = route_legs[0].get("points", [])
        route_length = route_legs[0].get("summary", {}).get("lengthInMeters", 0)  # Get total route length

        road_logger.info(f"Successfully retrieved route. Length: {route_length} meters",
                           extra={"stage": "get_route"})

        return points, route_length

    except requests.exceptions.Timeout:
        road_logger.error(f"Request timed out for route ({start_lat}, {start_lon}) -> ({end_lat}, {end_lon})",
                            exc_info=True, extra={"stage": "get_route"})
        monitor.increment_failure("tomtom")
        if failures>4:
               monitor.mark_api_status("tomtom", True)

    except requests.exceptions.ConnectionError:
        road_logger.error(f"Network connection error for route ({start_lat}, {start_lon}) -> ({end_lat}, {end_lon})",
                            exc_info=True, extra={"stage": "get_route"})
        monitor.increment_failure("tomtom")
        if failures>4:
               monitor.mark_api_status("tomtom", True)
    except requests.exceptions.HTTPError as http_err:
        road_logger.error(f"HTTP error: {http_err} for route ({start_lat}, {start_lon}) -> ({end_lat}, {end_lon})",
                            exc_info=True, extra={"stage": "get_route"})
        monitor.increment_failure("tomtom")
        if failures>4:
                   monitor.mark_api_status("tomtom", True)
    except requests.exceptions.RequestException as req_err:
        road_logger.error(f"Unexpected request error: {req_err} for route ({start_lat}, {start_lon}) -> ({end_lat}, {end_lon})",
                            exc_info=True, extra={"stage": "get_route"})
        monitor.increment_failure("tomtom")
        if failures>4:
               monitor.mark_api_status("tomtom", True)
    except Exception as e:
        road_logger.critical(f"Unexpected error in get_route: {e}", exc_info=True, extra={"stage": "get_route"})
        monitor.increment_failure("tomtom")
        road_logger.critical(f"failures: {failures}", exc_info=True, extra={"stage": "get_route"})

        if failures>4:
               monitor.mark_api_status("tomtom", True)
    return None, None  # Return None in case of any failure





def get_nearby_roads_with_coordinates(lat, lng, radius=500):
    """Find nearby roads with names and their start & end coordinates."""
    traffic_logger.info(f"function started lat={lat}, lng={lng}, radius={radius}",
                                                  extra={"stage": "start"})

    overpass_url = "http://overpass-api.de/api/interpreter"
    query = f"""
    [out:json];
    way(around:{radius}, {lat}, {lng}) ["highway"];
    (._;>;);
    out body;
    """
    try:
        response = requests.get(overpass_url, params={"data": query})
        traffic_logger.info(f"Request sent to Overpass API", extra={"stage": "processing"})

        if response.status_code == 200:
            traffic_logger.info(f"Response received successfully",
                                                          extra={"stage": "processing"})

            data = response.json()
            if "elements" in data:
                traffic_logger.info(f"Processing received data...",
                                                              extra={"stage": "processing"})

                ways = [el for el in data["elements"] if el["type"] == "way"]
                nodes = {el["id"]: el for el in data["elements"] if el["type"] == "node"}
                road_details = {}

                traffic_logger.info("Found %d roads in response data", len(ways),
                                                              extra={"stage": "processing"})

                for way in ways:
                    if "tags" in way:
                        name = way["tags"].get("name")  # Road name
                        ref = way["tags"].get("ref")  # Highway number (if no name)
                        if not name and ref:
                            name = f"Highway {ref}"  # Use reference if no name
                        if name and "nodes" in way:
                            node_ids = way["nodes"]
                            start_node = nodes.get(node_ids[0])  # First node
                            end_node = nodes.get(node_ids[-1])  # Last node

                            if start_node and end_node:
                                start_coords = (start_node["lat"], start_node["lon"])
                                end_coords = (end_node["lat"], end_node["lon"])

                                # Merge roads with the same name
                                if name in road_details:
                                    # Update start point if it's earlier (smaller lat, lon)
                                    road_details[name]["start"] = min(
                                        road_details[name]["start"], start_coords
                                    )
                                    # Update end point if it's later (bigger lat, lon)
                                    road_details[name]["end"] = max(
                                        road_details[name]["end"], end_coords
                                    )
                                else:
                                    road_details[name] = {"start": start_coords, "end": end_coords}

                                traffic_logger.info("Road: %s | Start: %s | End: %s",
                                                                              name, start_coords, end_coords,
                                                                              extra={"stage": "processing"})
                if road_details:
                    traffic_logger.info(" Processed %d roads", len(road_details),
                                                                  extra={"stage": "processing"})
                    return road_details
                else:
                    traffic_logger.warning(" No named roads found",
                                                                     extra={"stage": "warning"})
                    return {"No named roads found."}
            else:
                traffic_logger.warning(" No roads found in response",
                                                                 extra={"stage": "warning"})
                return {"No roads found."}
        else:
            traffic_logger.error(
                f"Failed API Request! Status Code: {response.status_code}, Response: {response.text}",
                extra={"stage": "error"})
            return {"error": f"API request failed with status {response.status_code}"}
    except Exception as e:
        traffic_logger.critical(f"Exception occurred: {e}", exc_info=True,
                                                          extra={"stage": "critical"})

