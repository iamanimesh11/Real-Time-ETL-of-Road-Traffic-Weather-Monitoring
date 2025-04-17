import requests,sys,os,random
import psycopg2
from psycopg2 import extras
import random
from geopy.distance import geodesic


AIRFLOW_HOME = os.getenv("AIRFLOW_HOME", "/opt/airflow")  

if AIRFLOW_HOME != "/opt/airflow":
    BASE_DIR = os.path.abspath(os.path.join(AIRFLOW_HOME, ".."))  
    print("BASE_DIR:", BASE_DIR) 
    AIRFLOW_HOME = BASE_DIR
    
COMMON_PATH = os.path.join(AIRFLOW_HOME, "common", "logging_and_monitoring")
sys.path.append(COMMON_PATH)
COMMON_PATH = os.path.join(AIRFLOW_HOME, "common","logging_and_monitoring","logs") 
sys.path.append(COMMON_PATH)

traffic_data_main_log_path=os.path.join(COMMON_PATH, "road_data_main.log")

from centralized_logging import setup_logger
functions_Com = setup_logger("traffic_data_script", "get_route()", "python", traffic_data_main_log_path)


def filter_significant_points(route_points, interval):
    """Filters route_points that have a significant change in distance."""
    functions_Com.info(f"filter_significant_route_points() begins with {len(route_points)} route_points", extra={"stage": "filter_significant_route_points"})
    if not route_points:
        functions_Com.warning("No route_points provided, returning empty list.", extra={"stage": "filter_significant_route_points"})
        return []
    filtered_route_points = [route_points[0]]  # Always include the first point
    prev_point = route_points[0]
    count_filtered = 1  # Start with the first point included


    for point in route_points[1:]:
        distance = geodesic(
            (prev_point["latitude"], prev_point["longitude"]),
            (point["latitude"], point["longitude"])
        ).meters

        if distance >= interval:
            filtered_route_points.append(point)
            prev_point = point
            count_filtered += 1  # Increment count for logging
    functions_Com.info(
        f"Filtered {count_filtered} significant route_points from {len(route_points)} total",
        extra={"stage": "filter_significant_route_points"}
    )
    functions_Com.info(
        f"Filtered route_points ; {filtered_route_points}", extra={"stage": "filter_significant_route_points"}
    )

    return filtered_route_points

