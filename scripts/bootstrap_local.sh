#!/usr/bin/env bash
set -euo pipefail

echo "Starting the local MySQL service..."
docker compose up -d mysql

echo "Creating local users and database permissions..."
python scripts/setup_local_database.py

echo "Loading telemetry data..."
python scripts/ingest_legacy.py

echo "Creating the restricted agent view..."
python scripts/setup_local_database.py

echo "Indexing the SOP in local ChromaDB..."
python scripts/ingest_sop_chromadb.py

echo "Building and starting the Streamlit container..."
docker compose build streamlit
docker compose up -d streamlit

echo "Local setup complete: http://localhost:8502"
