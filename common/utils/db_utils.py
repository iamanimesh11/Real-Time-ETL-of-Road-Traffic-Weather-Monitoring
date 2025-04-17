import requests,sys,os,random
import psycopg2
from psycopg2 import extras
import random
from geopy.distance import geodesic
from datetime import datetime



AIRFLOW_HOME = os.getenv("AIRFLOW_HOME", "/opt/airflow")  # Default to Airflow's path

if AIRFLOW_HOME != "/opt/airflow":
    BASE_DIR = os.path.abspath(os.path.join(AIRFLOW_HOME, ".."))  
    print("BASE_DIR:", BASE_DIR)  
    AIRFLOW_HOME = BASE_DIR
    
COMMON_PATH = os.path.join(AIRFLOW_HOME, "common", "logging_and_monitoring")
sys.path.append(COMMON_PATH)
COMMON_PATH = os.path.join(AIRFLOW_HOME, "common","logging_and_monitoring","logs") 
sys.path.append(COMMON_PATH)


from centralized_logging import setup_logger
        
Script_logs_path=os.path.join(COMMON_PATH, "db_utils.log")
logger = setup_logger("Road_Data_ETL", "db_utils", "python", Script_logs_path)



def get_road_id(conn):
    logger.info(f"get_road_id() begins", extra={"stage": "get_road_id"})
    query = f"SELECT road_id ,start_lat,start_lon,end_lat,end_lon,road_name FROM roads_traffic.roads"
    logger.info(f"getting road id from query - {query}", extra={"stage": "get_road_id"})

    try:
        with conn.cursor() as cur:
                cur.execute(query)
                road_data = cur.fetchall()
        if road_data:
            logger.info(f"road_Data - {road_data}", extra={"stage": "get_road_id"})
            return road_data
        else:
            logger.error(f"Empty result from query - {road_data}", extra={"stage": "get_road_id"})
            return None

    except Exception as e:
        logger.critical(f"error fetching road id : {e}", extra={"stage": "get_road_id"})
        return None




def get_road_data_FROMroad_id(road_id,conn):
    logger.info(f"function() begins", extra={"stage": "get_road_data_FROMroad_id"})
    query = f"SELECT road_id ,start_lat,start_lon,end_lat,end_lon,road_name FROM roads_traffic.roads where road_id={road_id}"
    logger.info(f"getting road id from query - {query}", extra={"stage": "get_road_data_FROMroad_id"})

    try:
        with conn.cursor() as cur:
                cur.execute(query)
                road_data = cur.fetchall()
        if road_data:
            logger.info(f"road_Data - {road_data}", extra={"stage": "get_road_data_FROMroad_id"})
            return road_data
        else:
            logger.error(f"Empty result from query - {road_data}", extra={"stage": "get_road_data_FROMroad_id"})
            return None

    except Exception as e:
        logger.critical(f"error fetching road id : {e}", extra={"stage": "get_road_data_FROMroad_id"})
        return None


def bulk_insert_into_traffic_Data_Table(traffic_data_list,conn,weather_id_map):
    logger.info(f"bulk_insert_into_traffic_Data_Table function called length is {len(traffic_data_list)}", extra={"stage": "bulk_insert_into_traffic_Data_Table"})

    if not traffic_data_list:
        logger.warning("No data provided for insertion in traffic_data_list", extra={"stage": "bulk_insert_into_traffic_Data_Table"})
        return
    query = f"""
                 INSERT INTO roads_traffic.traffic_data 
                 (road_id,road_name,latitude,longitude ,current_speed, free_flow_speed, 
                 current_travel_time, free_flow_travel_time,mapurl,traffic_condition,weather_id,recorded_at) 
                 VALUES %s
           """

    try:
        # values = [(data["road_id"], data["road_name"], data["latitude"], data["longitude"], data["current_speed"], data["free_flow_speed"],
                   # data["current_travel_time"],
                   # data["free_flow_travel_time"], data['mapurl'],data['traffic_condition'])
                  # for data in traffic_data_list]
        values = []
        for data in traffic_data_list:
            key = (data["latitude"], data["longitude"], data["recorded_at"])
            weather_id = weather_id_map.get(key)
            if weather_id is None:
                  logger.warning(f"[LOOKUP FAIL] Tried key: {key}, Available keys: {list(weather_id_map.keys())}", extra={"stage": "weather_id_lookup"})

            logger.info(f"weather_id of {key},,,,,{(weather_id)} into database.", extra={"stage": "bulk_insert_into_traffic_Data_Table"})

            values.append((
                data["road_id"],
                data["road_name"],
                data["latitude"],
                data["longitude"],
                data["current_speed"],
                data["free_flow_speed"],
                data["current_travel_time"],
                data["free_flow_travel_time"],
                data["mapurl"],
                data["traffic_condition"],
                weather_id,
                data["recorded_at"]
            ))

        logger.info(f"Preparing to insert {(values)} records into database.", extra={"stage": "bulk_insert_into_traffic_Data_Table"})
        with conn.cursor() as cur:  # Automatically closes cursor after execution
            extras.execute_values(cur, query, values)
            conn.commit()
        logger.info(f"Successfully inserted {len(values)} / {len(traffic_data_list)}records into database.", extra={"stage": "bulk_insert_into_traffic_Data_Table"})

    except psycopg2.Error as db_err:
        logger.exception(f"Database error during bulk insert :{db_err}", extra={"stage": "bulk_insert_into_traffic_Data_Table"})
        conn.rollback()  # Rollback on error
    except Exception as e:
        logger.exception(f"Unexpected error: {e}", extra={"stage": "bulk_insert_into_traffic_Data_Table"})
        conn.rollback()  # Rollback on error

def bulk_insert_into_weather_Data_Table(weather_data_list,conn):
    logger.info("bulk_insert_into_weather_Data_Table function called", extra={"stage": "bulk_insert_into_weather_Data_Table"})

    if not weather_data_list:
        logger.warning("No data provided for insertion in weaather_data_list", extra={"stage": "bulk_insert_into_weather_Data_Table"})
        return {}
   
    
    query = f"""
                 INSERT INTO roads_traffic.weather_data 
                (latitude, longitude, weather_conditions, temperature, humidity, recorded_at)
                 VALUES %s
                 ON CONFLICT (latitude, longitude, recorded_at) DO NOTHING
           """   
    try:
        values = [
                    (
                    data["latitude"], data["longitude"],
                    data['weather_conditions'],data['temperature'], 
                    data['humidity'],data['recorded_at']
                   )
                   for data in weather_data_list
                ]
        logger.info(f"Preparing to insert {len(values)} records into database.", extra={"stage": "bulk_insert_into_weather_Data_Table"})
        with conn.cursor() as cur:  # Automatically closes cursor after execution
            extras.execute_values(cur, query, values)
            conn.commit()
            logger.info(f"Successfully inserted {len(values)} / {len(weather_data_list)}records into database.", extra={"stage": "bulk_insert_into_weather_Data_Table"})
            
            # Step 2: Fetch weather_ids for all inserted/known rows
            cur.execute(f"""
                SELECT weather_id, latitude, longitude, recorded_at
                FROM roads_traffic.weather_data
                WHERE (latitude, longitude, recorded_at) IN %s
            """, (tuple((d['latitude'], d['longitude'], d['recorded_at']) for d in weather_data_list),))

            result = cur.fetchall()
            # Return mapping: (lat, lon, recorded_at) => weather_id
            weather_id_map = {
                (row[1], row[2], row[3]): row[0] for row in result

            }
            logger.info(f"weather_id_map: {weather_id_map}", extra={"stage": "bulk_insert_into_weather_Data_Table"})

            return weather_id_map
            
            
    except psycopg2.Error as db_err:
        logger.exception(f"Database error during bulk insert :{db_err}", extra={"stage": "bulk_insert_into_weather_Data_Table"})
        conn.rollback()  # Rollback on error
        return {}
    except Exception as e:
        logger.exception(f"Unexpected error: {e}", extra={"stage": "bulk_insert_into_weather_Data_Table"})
        conn.rollback()  # Rollback on error
        return {}

def bulk_insert_into_road_Table(road_list, conn):

    logger.info("bulk_insert_into_road_Table function called", extra={"stage": "start"})
    logger.info("Preparing road data for bulk insertion", extra={"stage": "processing"})
    logger.info(f"Messages received for insertion: {road_list}")
    try:
        cur = conn.cursor()
        # logger.debug("Cursor created successfully", extra={"stage": "processing"})

        query = """
                   INSERT INTO roads_traffic.roads (road_name, start_lat,start_lon,end_lat,end_lon)
                   VALUES %s
                   RETURNING road_id;  
               """
        values = [(road["name"], road["start_lat"], road["start_lon"], road["end_lat"], road["end_lon"]) for road in
                  road_list]
        logger.info(f"query: {query} ,values: {values} ", extra={"stage": "start"})

        extras.execute_values(cur, query, values)  # Use extras.execute_values
        inserted_ids = cur.fetchall()  # Fetch all returned IDs
        road_id = [row[0] for row in inserted_ids] if inserted_ids else []
        conn.commit()
        logger.info(f"Inserted {len(road_list)} roads into database ,Returning road_id :{road_id}",
                       extra={"stage": "processing"})
        return road_id

    except Exception as e:
        logger.critical(f"exception in bulk_insert_into_road_Table() : {e}", extra={"stage": "processing"})
        conn.rollback()
        return None
