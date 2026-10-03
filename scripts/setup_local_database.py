"""Create the local MySQL users, audit table, and approved agent view.

Run this script with the local MySQL container running. It uses the root
credentials from .env and never prints passwords.
"""

from pathlib import Path
import os
import re
import time

import pymysql
from dotenv import load_dotenv


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
ENV_PATH = PROJECT_ROOT / ".env"
VIEW_SQL_PATH = PROJECT_ROOT / "sql" / "create_agent_view.sql"

load_dotenv(ENV_PATH)

DB_HOST = os.getenv("MYSQL_HOST", "localhost")
DB_PORT = int(os.getenv("MYSQL_PORT", "3306"))
DB_NAME = os.getenv("MYSQL_DATABASE", "cold_chain")
ROOT_PASSWORD = os.getenv("MYSQL_ROOT_PASSWORD")
INGEST_PASSWORD = os.getenv("MYSQL_INGEST_PASSWORD")
AGENT_PASSWORD = os.getenv("MYSQL_AGENT_PASSWORD")


def _validate_identifier(value: str, name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", value):
        raise ValueError(f"{name} contains unsupported characters")
    return value


DB_NAME = _validate_identifier(DB_NAME, "MYSQL_DATABASE")

required_settings = {
    "MYSQL_ROOT_PASSWORD": ROOT_PASSWORD,
    "MYSQL_INGEST_PASSWORD": INGEST_PASSWORD,
    "MYSQL_AGENT_PASSWORD": AGENT_PASSWORD,
}
missing_settings = [name for name, value in required_settings.items() if not value]
if missing_settings:
    raise ValueError(f"Missing required environment variables: {missing_settings}")


def connect_as_root():
    last_error = None
    for attempt in range(1, 31):
        try:
            return pymysql.connect(
                host=DB_HOST,
                port=DB_PORT,
                user="root",
                password=ROOT_PASSWORD,
                autocommit=True,
                charset="utf8mb4",
            )
        except pymysql.MySQLError as error:
            last_error = error
            print(f"Waiting for MySQL (attempt {attempt}/30)...")
            time.sleep(2)

    raise RuntimeError(f"Could not connect to MySQL: {last_error}")


def main() -> None:
    print(f"Connecting to MySQL at {DB_HOST}:{DB_PORT}...")
    connection = connect_as_root()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )

            cursor.execute(
                "CREATE USER IF NOT EXISTS 'chain_ingest'@'%%' IDENTIFIED BY %s",
                (INGEST_PASSWORD,),
            )
            cursor.execute(
                "ALTER USER 'chain_ingest'@'%%' IDENTIFIED BY %s",
                (INGEST_PASSWORD,),
            )
            cursor.execute(
                "CREATE USER IF NOT EXISTS 'chain_agent'@'%%' IDENTIFIED BY %s",
                (AGENT_PASSWORD,),
            )
            cursor.execute(
                "ALTER USER 'chain_agent'@'%%' IDENTIFIED BY %s",
                (AGENT_PASSWORD,),
            )
            cursor.execute(
                "CREATE ROLE IF NOT EXISTS 'chain_agent_role'@'%%'",
                (),
            )

            cursor.execute(
                f"GRANT INSERT, CREATE, DROP, ALTER ON `{DB_NAME}`."
                "`tbl_sc_fleet_hist_raw` TO 'chain_ingest'@'%%'",
                (),
            )

            cursor.execute(
                f"CREATE TABLE IF NOT EXISTS `{DB_NAME}`.`agent_audit_log` ("
                "audit_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,"
                "created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),"
                "thread_id VARCHAR(128) NOT NULL,"
                "user_question TEXT NOT NULL,"
                "tools_used VARCHAR(255) NOT NULL DEFAULT '',"
                "status VARCHAR(32) NOT NULL,"
                "error_message TEXT NULL,"
                "PRIMARY KEY (audit_id),"
                "INDEX idx_agent_audit_created_at (created_at),"
                "INDEX idx_agent_audit_thread_id (thread_id)"
                ") ENGINE=InnoDB"
            )

            cursor.execute(
                f"GRANT INSERT ON `{DB_NAME}`.`agent_audit_log` "
                "TO 'chain_agent_role'@'%%'",
                (),
            )

            cursor.execute(
                "GRANT 'chain_agent_role'@'%%' TO 'chain_agent'@'%%'",
                (),
            )
            cursor.execute(
                "SET DEFAULT ROLE 'chain_agent_role'@'%%' TO 'chain_agent'@'%%'",
                (),
            )

            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema=%s AND table_name='tbl_sc_fleet_hist_raw'",
                (DB_NAME,),
            )
            raw_table_exists = cursor.fetchone()[0] == 1

            if raw_table_exists:
                view_sql = VIEW_SQL_PATH.read_text(encoding="utf-8")
                cursor.execute(view_sql)
                cursor.execute(
                    f"GRANT SELECT ON `{DB_NAME}`.`v_agent_fleet` "
                    "TO 'chain_agent_role'@'%%'",
                    (),
                )
                print("Created or refreshed v_agent_fleet.")
            else:
                print(
                    "Raw telemetry table does not exist yet. "
                    "Run scripts/ingest_legacy.py, then run this setup script again."
                )

        print("Local MySQL users, audit logging, and permissions are ready.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
