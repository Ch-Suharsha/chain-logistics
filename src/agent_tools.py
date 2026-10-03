import os 
from pathlib import Path

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from langchain_chroma import Chroma
from langchain_core.tools import tool
from langchain_huggingface import HuggingFaceEmbeddings
from sqlalchemy.engine import URL

#part2- finding the project folders
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

ENV_PATH = PROJECT_ROOT/".env"
CHROMA_PATH = PROJECT_ROOT/"data"/"chroma_sop"

#part3 - defining the models and collection settings
MODEL_NAME = "BAAI/bge-m3"
HF_CACHE_DIR = Path.home() / ".cache" / "huggingface"
COLLECTION_NAME = "chain_logistics_sop"

#part4 - loading the environment variables

load_dotenv(ENV_PATH)

DB_HOST = os.getenv("MYSQL_HOST", "localhost")
DB_PORT = int(os.getenv("MYSQL_PORT", "3306"))
DB_NAME = os.getenv("MYSQL_DATABASE", "cold_chain")

DB_USER = os.getenv("MYSQL_AGENT_USER")
DB_PASSWORD = os.getenv("MYSQL_AGENT_PASSWORD")

#part-5: validating the settings which are required

required_settings = {
    "MYSQL_AGENT_USER": DB_USER,
    "MYSQL_AGENT_PASSWORD": DB_PASSWORD,
}

missing_settings = [
    name
    for name, value in required_settings.items()
    if not value
]

if missing_settings:
    raise ValueError(
        f"missing the required environment variables: {missing_settings}"
    )

#part6: creating the engine that connects to MYSQL
DATABASE_URL = URL.create(
    drivername = "mysql+pymysql",
    username = DB_USER,
    password = DB_PASSWORD,
    host = DB_HOST,
    port = DB_PORT,
    database = DB_NAME,
)

db_engine = create_engine(
    DATABASE_URL,
    pool_pre_ping = True,
)

#part-7: Load the BGE-M3 model and ChromaDB
embeddings = HuggingFaceEmbeddings(
    model_name =MODEL_NAME,
    cache_folder = str(
        HF_CACHE_DIR/ "sentence-transformers"
    ),
    model_kwargs = {
        "device" : "cpu",
    },
    encode_kwargs = {
        "normalize_embeddings": True,
    },
)

vector_store = Chroma(
    collection_name = COLLECTION_NAME,
    embedding_function = embeddings,
    persist_directory=str(CHROMA_PATH),
)

sop_retriever = vector_store.as_retriever(
    search_kwargs={
        "k":3,
    }
)

#part8: adding a safety check to the telemetry queries
def validate_telemetry_query(sql_query:str) -> str| None:
    cleaned_query = sql_query.strip()

    if not cleaned_query:
        return "The SQL query is empty"

    normalized_query =" ".join(
        cleaned_query.upper().split()
    )

    if not normalized_query.startswith("SELECT "):
        return "Security block: only SELECT queries are allowed."

    if "--" in cleaned_query or "/*" in cleaned_query:
        return "Security block: SQL comments are not allowed"

    if ";" in cleaned_query[:-1]:
        return "security block: multiple SQL statements are not allowed"

    forbidden_keywords =(
        "INSERT", "UPDATE","DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "GRANT",
        "REVOKE",
        "CALL",
        "SET",
        "LOAD",
        "INTO",
    )

    for keyword in forbidden_keywords:
        if f"{keyword}" in f"{normalized_query}":
            return(
                f"Security block: the keyword"
                f"{keyword} is not allowed."
            )

    if "V_AGENT_FLEET" not in normalized_query:
        return (
            "Security block: queries must use "
            "the approved v_agent_fleet view."
        )

    return None

#part9: create the telmetry datbase tool

@tool
def query_telemetry_data(sql_query: str) -> str:
    """
    Query approved cold-chain telemetry data.

    Use only SELECT statements against the v_agent_fleet view.
    The available columns include TS_UTC, V_LAT, V_LON,
    IOT_TEMP_VAL_C, CGO_COND_CD, RISK_CLS_TXT,
    DELAY_PROB_DEC, PRT_CNG_LVL, RT_RSK_IDX,
    and SYS_INGEST_FLAG.
    Return only the information needed to answer the user.
    """
    security_error = validate_telemetry_query(sql_query)

    if security_error:
        return security_error
    
    try:
        with db_engine.connect() as connection:
            result = connection.execute(
                text(sql_query)
            )

            columns = list(result.keys())
            rows = result.fetchmany(10)

        if not rows:
            return "The query returned no matching telemetry rows."

        formatted_rows = [
            dict(zip(columns, row))
            for row in rows
        ]

        return (
            f"Returned {len(formatted_rows)} row(s):\n"
            f"{formatted_rows}"
        )

    except Exception as error:
        return f"Database query failed: {error}"

#part-10: creating the weather tool

@tool
def get_corridor_weather(
    latitude: float,
    longitude: float,
) -> str:
    """
    Get current weather conditions for a shipment location.

    Use this tool when the user asks about current weather,
    temperature, or wind conditions at a latitude and longitude.
    """

    weather_url = "https://api.open-meteo.com/v1/forecast"

    parameters = {
        "latitude": latitude,
        "longitude": longitude,
        "current": (
            "temperature_2m,"
            "wind_speed_10m"
        ),
    }

    try:
        response = requests.get(
            weather_url,
            params=parameters,
            timeout=6,
        )

        response.raise_for_status()
        payload = response.json()

        current_weather = payload.get("current",{})

        temperature = current_weather.get(
            "temperature_2m"
        )
        wind_speed = current_weather.get(
            "wind_speed_10m"
        )

        if temperature is None or wind_speed is None:
            return (
                "The weather service returned an "
                "incomplete response."
            )

        return (
            f"Weather for latitude {latitude}, "
            f"longitude {longitude}: "
            f"temperature={temperature}°C, "
            f"wind_speed={wind_speed} km/h."
        )

    except requests.RequestException as error:
        return f"Weather service request failed: {error}"

    except ValueError:
        return "The weather service returned invalid JSON data."

#part11: creating the SOP search tool
@tool
def search_compliance_sop(query: str) -> str:
    """
    Search the cold-chain SOP for compliance guidance.

    Use this tool when the user asks about policies,
    procedures, escalation rules, cargo conditions,
    temperature requirements, or operational instructions.
    """

    if not query.strip():
        return "the SOP search query is empty."

    try:
        matching_documents = sop_retriever.invoke(query)

        if not matching_documents:
            return "No matching SOP section was found."

        formatted_results = []

        for document_number, document in enumerate(
            matching_documents,
            start=1,
        ):
            source_file = document.metadata.get(
                "source_file",
                "unknown",
            )

            chunk_id = document.metadata.get(
                "chunk_id",
                "unknown",
            )

            formatted_results.append(
                "\n".join(
                    [
                        f"Result {document_number}",
                        f"Source file: {source_file}",
                        f"Chunk ID: {chunk_id}",
                        "Content:",
                        document.page_content,
                    ]
                )
            )

        return (
            "Relevant compliance SOP context:\n\n"
            + "\n\n".join(formatted_results)
        )

    except Exception as error:
        return f"SOP search failed: {error}"

# Part 12: Register the tools and test them

AVAILABLE_TOOLS = [
    query_telemetry_data,
    get_corridor_weather,
    search_compliance_sop,
]


if __name__ == "__main__":
    print("Testing telemetry tool...")

    telemetry_result = query_telemetry_data.invoke(
        {
            "sql_query": (
                "SELECT TS_UTC, V_LAT, V_LON, "
                "IOT_TEMP_VAL_C "
                "FROM v_agent_fleet "
                "LIMIT 3"
            )
        }
    )

    print(telemetry_result)

    print("\nTesting weather tool...")

    weather_result = get_corridor_weather.invoke(
        {
            "latitude": 34.0522,
            "longitude": -118.2437,
        }
    )

    print(weather_result)

    print("\nTesting SOP search tool...")

    sop_result = search_compliance_sop.invoke(
        {
            "query": (
                "What should we do when a shipment "
                "is delayed?"
            )
        }
    )

    print(sop_result)
