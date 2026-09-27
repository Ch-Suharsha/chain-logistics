from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

# finding the project root
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

ENV_PATH = PROJECT_ROOT / ".env"
DATA_PATH = PROJECT_ROOT / "data" / "raw" / "dynamic_supply_chain_logistics_dataset.csv"
load_dotenv(ENV_PATH)

# reading the csv file
print(f"loading the csv from : {DATA_PATH}")

df = pd.read_csv(DATA_PATH)

print(f"loaded {len(df)} rows")
print(f"Loaded {len(df.columns)} columns")

# legacy data mapping

legacy_mapping = {
    "timestamp": "TS_UTC",
    "vehicle_gps_latitude": "V_LAT",
    "vehicle_gps_longitude": "V_LON",
    "iot_temperature": "IOT_TEMP_VAL_C",
    "cargo_condition_status": "CGO_COND_CD",
    "risk_classification": "RISK_CLS_TXT",
    "delay_probability": "DELAY_PROB_DEC",
    "port_congestion_level": "PRT_CNG_LVL",
    "route_risk_level": "RT_RSK_IDX",
}

# column validations
required_columns = list(legacy_mapping.keys())

missing_columns = [column for column in required_columns if column not in df.columns]

if missing_columns:
    raise ValueError(f"Missing columns in csv: {missing_columns}")

# selecting and renaming the columns
df_legacy = df[required_columns].rename(columns=legacy_mapping)

# adding the ingestion flag
df_legacy["SYS_INGEST_FLAG"] = "Y"

# reading the sql connections

db_host = os.getenv("MYSQL_HOST", "localhost")
db_port = int(os.getenv("MYSQL_PORT", "3306"))
db_name = os.getenv("MYSQL_DATABASE", "cold_chain")
db_user = os.getenv("MYSQL_USER")
db_password = os.getenv("MYSQL_PASSWORD")

# validating the database
required_settings = {
    "MYSQL_USER": db_user,
    "MYSQL_PASSWORD": db_password,
}

missing_settings = [name for name, value in required_settings.items() if not value]

if missing_settings:
    raise ValueError(f"Missing database settings: {missing_settings}")

# building the sql alchemy url

database_url = URL.create(
    drivername="mysql+pymysql",
    username=db_user,
    password=db_password,
    host=db_host,
    port=db_port,
    database=db_name,
)
# creating the engine
engine = create_engine(database_url)

# testing the connection
print("testing MYSQL connection....")

with engine.connect() as connection:
    connection.execute(text("SELECT 1"))

print("MySQL connection is successful")

# loading the database into MYSQL
table_name = "tbl_sc_fleet_hist_raw"

print(f"writing the data to the table: {table_name}")

df_legacy.to_sql(
    name=table_name,
    con=engine,
    if_exists="replace",
    index=False,
)

print(f"Successfully loaded {len(df_legacy)} rows into {table_name}")
