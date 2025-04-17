import os
import sys
import psycopg2
import configparser

# Determine the correct base directory dynamically
AIRFLOW_HOME = os.getenv("AIRFLOW_HOME", "/opt/airflow")  # Default to Airflow's path
if AIRFLOW_HOME != "/opt/airflow":
    BASE_DIR = os.path.abspath(os.path.join(AIRFLOW_HOME, ".."))  # Go one level up from /opt/airflow
    print("BASE_DIR:", BASE_DIR)  # ✅ Debugging: Print to verify inside container
    AIRFLOW_HOME = BASE_DIR
    logging.info("below base_Dir")
    logging.info(BASE_DIR)
    
COMMON_PATH = os.path.join(AIRFLOW_HOME, "common", "logging_and_monitoring")
sys.path.append(COMMON_PATH)

common_PATH = os.path.join(AIRFLOW_HOME, "common","logging_and_monitoring","logs") 
sys.path.append(common_PATH)


from centralized_logging import setup_logger


# Ensure the correct path inside Docker
CONFIG_PATH = os.path.join(AIRFLOW_HOME, "common","credentials", "config.ini")
log_path=os.path.join(AIRFLOW_HOME, "common","logging_and_monitoring", "logs","database_connection.log")


# Load the config file
config = configparser.ConfigParser()
config.read(CONFIG_PATH)

# Ensure the file is loaded correctly
if not config.sections():
    raise FileNotFoundError(f"Config file not found or empty: {CONFIG_PATH}")

config = configparser.ConfigParser()
config.read(CONFIG_PATH)
db_config = config['database']
host = db_config['host']
username = db_config['user']
password = db_config['password']
port = db_config['port']
database_name = db_config['database']
schema_name = "roads_traffic"  # Specify the schema to check

logger = setup_logger("database_logging", "database_connection", "postgres", log_path)


def connect_Database(**kwargs):
    logger.info("Database connection started.", extra={"stage": "start"})
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=database_name,
            user=username,
            password=password,
            host=host,
            port=port
        )
        cursor = conn.cursor()

        cursor.execute("SELECT 1")  # Simple test query
        result = cursor.fetchone()
        if result[0] != 1:
            logger.warning("Test query failed. Connection seems unstable.", extra={"stage": "start"})
            conn.close()
            return None
            # Create schema if it does not exist
            
        logger.info("Successfully connected to PostgreSQL database.", extra={"stage": "success"})

        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
        conn.commit()
        
        
        logger.info(f"Schema '{schema_name}' is ready.", extra={"stage": "schema_setup"})
        query = f"""
               CREATE TABLE IF NOT EXISTS {schema_name}.roads(
                    road_id SERIAL PRIMARY KEY, 
                    road_name VARCHAR(255) NOT NULL UNIQUE,
                    start_lat DOUBLE PRECISION NOT NULL, 
                    start_lon DOUBLE PRECISION NOT NULL, 
                    end_lat DOUBLE PRECISION NOT NULL,  
                    end_lon DOUBLE PRECISION NOT NULL,   
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
               """
        cursor.execute(query=query)
        conn.commit()
        logger.info(f"Table 'roads' is ready.", extra={"stage": "table_setup"})
        # Create index for roads table safely
        try:
            cursor.execute(f"""
                        DO $$ BEGIN
                            IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'roads_road_id_idx') THEN
                                CREATE INDEX roads_road_id_idx ON {schema_name}.roads(road_id);
                            END IF;
                        END $$;
                    """)
            conn.commit()
            logger.info("Index 'roads_road_id_idx' created successfully.", extra={"stage": "index_creation"})
        except Exception as e:
            conn.rollback()
            logger.warning(f"Skipping index creation for 'roads_road_id_idx': {e}", extra={"stage": "index_creation"})
        query = f"""
        CREATE TABLE IF NOT EXISTS {schema_name}.weather_data (
            weather_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION,
            weather_conditions VARCHAR(50) ,
            temperature FLOAT,
            humidity FLOAT,
            recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(latitude,longitude,recorded_at)       
        );
        """
        cursor.execute(query=query) 
        conn.commit()
        logger.info(f"Table 'weather_data' is ready.", extra={"stage": "table_setup"})
        # Create index for traffic_data table safely
        try:
            cursor.execute(f"""
                        DO $$ 
                            BEGIN
                                IF NOT EXISTS (
                                    SELECT 1 FROM pg_indexes WHERE LOWER(indexname) = LOWER('weather_Data_location_time_idx')
                                ) THEN
                                    CREATE INDEX weather_Data_location_time_idx ON roads_traffic.weather_data(latitude,longitude,recorded_at);
                                END IF;
                            END $$;

                    """)
            conn.commit()
            logger.info("Index 'weather_Data_location_time_idx' created successfully.", extra={"stage": "index_creation"})
        except Exception as e:
            conn.rollback()
            logger.warning(f"Skipping index creation for 'weather_Data_location_time_idx': {e}",
                           extra={"stage": "index_creation"})       
        query = f"""
        CREATE TABLE IF NOT EXISTS {schema_name}.traffic_data (
            traffic_id SERIAL PRIMARY KEY,
            road_id INT,
            road_name TEXT,
            latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION,
            current_speed INT,
            free_flow_speed INT,
            current_travel_time INT,
            free_flow_travel_time INT,
            road_closure BOOLEAN DEFAULT FALSE,
            recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            mapurl TEXT,
            traffic_condition VARCHAR(50),
            weather_id UUID REFERENCES {schema_name}.weather_data(weather_id),
            UNIQUE(road_id,recorded_at),
            FOREIGN KEY (road_id) REFERENCES {schema_name}.roads(road_id) ON DELETE CASCADE    
        );
        """
        cursor.execute(query=query) 
        conn.commit()
        logger.info(f"Table 'traffic_data' is ready.", extra={"stage": "table_setup"})
        # Create index for traffic_data table safely
        try:
            cursor.execute(f"""
                        DO $$ 
                            BEGIN
                                IF NOT EXISTS (
                                    SELECT 1 FROM pg_indexes WHERE LOWER(indexname) = LOWER('traffic_Data_road_id_idx')
                                ) THEN
                                    CREATE INDEX traffic_Data_road_id_idx ON roads_traffic.traffic_data(road_id);
                                END IF;
                            END $$;

                    """)
            conn.commit()
            logger.info("Index 'traffic_Data_road_id_idx' created successfully.", extra={"stage": "index_creation"})
        except Exception as e:
            conn.rollback()
            logger.warning(f"Skipping index creation for 'traffic_Data_road_id_idx': {e}",
                           extra={"stage": "index_creation"})

       

        logger.info("Database setup completed successfully.", extra={"stage": "success"})
        
        
        
        db_conn_info = {
            "dbname": database_name,
            "user": username,
            "password": password,
            "host": host,
            "port": port
        }
        
         # Handle Airflow Case
        
        task_instance = kwargs.get('task_instance') or kwargs.get('ti')  # Supports both
        if task_instance:
            logger.info("Running inside Airflow, pushing connection info to XCom.", extra={"stage": "airflow_xcom"})
            task_instance.xcom_push(key="db_connection", value=db_conn_info)
            return True
        else:
            logger.info("Running as a standalone script, skipping XCom push.", extra={"stage": "standalone"})
            return conn


    except psycopg2.Error as e:
        logger.critical(f"Database connection error: {e}", extra={"stage": "start"})
        if conn:
            conn.close()  # Ensure connection is closed if an error occurs
        return None
