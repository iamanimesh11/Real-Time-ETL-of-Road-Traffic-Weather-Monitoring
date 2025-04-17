import os
import sys
import requests
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
import time
# Set up paths
AIRFLOW_HOME = os.getenv("AIRFLOW_HOME", "/opt/airflow")
if AIRFLOW_HOME != "/opt/airflow":
    BASE_DIR = os.path.abspath(os.path.join(AIRFLOW_HOME, "..", ".."))
    AIRFLOW_HOME = BASE_DIR

CREDENTIALS_PATH = os.path.join(AIRFLOW_HOME, "common", "credentials")
COMMON_PATH = os.path.join(AIRFLOW_HOME, "common", "logging_and_monitoring")
LOGS_PATH = os.path.join(COMMON_PATH, "logs")

sys.path.append(COMMON_PATH)
sys.path.append(LOGS_PATH)
Script_logs_path=os.path.join(LOGS_PATH, "firebase_db_api_utils.log")

firebase_config_cache = None
from centralized_logging import setup_logger
logger = setup_logger("Traffic_Data_ETL", "firebase_db_api_utils", "python", Script_logs_path)

def get_firebase_config(retries=3, backoff_factor=1.5, delay=1):
    global firebase_config_cache
    if firebase_config_cache:
        return firebase_config_cache

    url = "https://realtimeetlroadtrafficweather.vercel.app/get_firebase_config"

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers={"X-Docker-Request": "true"},timeout=5)  # Add timeout to prevent hanging
            if response.status_code == 200:
                firebase_config = response.json()
                firebase_config["private_key"] = firebase_config["private_key"].replace("\\n", "\n")
                firebase_config_cache = firebase_config
                return firebase_config_cache
            else:
                logger.info(f"[Attempt {attempt}] Failed with status code: {response.status_code}")
        except requests.RequestException as e:
            logger.error(f"[Attempt {attempt}] Request failed: {e}")

        # Wait before retrying (exponential backoff)
        sleep_time = delay * (backoff_factor ** (attempt - 1))
        logger.warning(f"Retrying in {sleep_time:.1f} seconds...")
        time.sleep(sleep_time)

    raise RuntimeError("Failed to fetch Firebase config after multiple attempts")
    
    
    
class ApiMonitor:
    def __init__(self, collection="api_usage"):
        try:
            if not firebase_admin._apps:
                firebase_config = get_firebase_config()
                cred = credentials.Certificate(firebase_config)
                firebase_admin.initialize_app(cred)
            self.db = firestore.client()
            self.collection = collection
        except Exception as e:
            logger.critical(f"Error initializing Firebase or Firestore: {e}")
            self.db = None
            self.collection = collection


    def _get_today_key(self):
        return datetime.utcnow().strftime("%Y-%m-%d")

    def get_status(self, api_name):
        key = self._get_today_key()
        doc = self.db.collection(self.collection).document(key).get()
        if doc.exists:
            data = doc.to_dict().get(api_name, {})
            return data.get("count", 0), data.get("failures", 0), data.get("is_down", False)
        return 0, 0, False

    def increment_api_count(self, api_name):
        key = self._get_today_key()
        self.db.collection(self.collection).document(key).set(
            {api_name: {"count": firestore.Increment(1)}}, merge=True
        )

    def increment_failure(self, api_name):
        key = self._get_today_key()
        self.db.collection(self.collection).document(key).set(
            {api_name: {"failures": firestore.Increment(1)}}, merge=True
        )

    def reset_failure_count(self, api_name):
        key = self._get_today_key()
        self.db.collection(self.collection).document(key).set(
            {api_name: {"failures": 0}}, merge=True
        )

    def mark_api_status(self, api_name, is_down):
        key = self._get_today_key()
        self.db.collection(self.collection).document(key).set(
            {api_name: {"is_down": is_down}}, merge=True
        )
    def get_api_key(self, api_name):
        try:
            doc = self.db.collection("api_keys").document("keys").get()
            if doc.exists:
                api_key = doc.to_dict().get(api_name)
                if api_key is None:
                    print(f"API key for '{api_name}' not found in document.")
                return api_key
            else:
                print("Document does not exist.")
                return None
        except Exception as e:
            print(f"Error retrieving API key for {api_name}: {e}")
            return str(e)
