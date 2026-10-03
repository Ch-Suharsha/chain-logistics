import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src import agent_tools
from src.agent_tools import validate_telemetry_query
from src.orchestrator import SYSTEM_PROMPT


class TelemetryQueryValidationTests(unittest.TestCase):
    def test_allows_select_from_approved_view(self):
        self.assertIsNone(
            validate_telemetry_query(
                "SELECT TS_UTC, V_LAT FROM v_agent_fleet LIMIT 5"
            )
        )

    def test_rejects_non_select_statements(self):
        self.assertIn(
            "only SELECT queries are allowed",
            validate_telemetry_query("UPDATE v_agent_fleet SET V_LAT = 0"),
        )

    def test_rejects_raw_table_access(self):
        self.assertIn(
            "approved v_agent_fleet view",
            validate_telemetry_query(
                "SELECT * FROM tbl_sc_fleet_hist_raw LIMIT 5"
            ),
        )

    def test_rejects_multiple_statements(self):
        self.assertIn(
            "multiple SQL statements",
            validate_telemetry_query(
                "SELECT * FROM v_agent_fleet LIMIT 1; SELECT * FROM v_agent_fleet"
            ),
        )

    def test_rejects_sql_comments(self):
        self.assertIn(
            "SQL comments are not allowed",
            validate_telemetry_query(
                "SELECT * FROM v_agent_fleet -- inspect data"
            ),
        )

    def test_telemetry_tool_returns_database_rows(self):
        fake_connection = Mock()
        fake_result = Mock()
        fake_result.keys.return_value = ["TS_UTC", "V_LAT"]
        fake_result.fetchmany.return_value = [("2021-01-01 00:00:00", 40.3)]
        fake_connection.execute.return_value = fake_result

        fake_context = Mock()
        fake_context.__enter__ = Mock(return_value=fake_connection)
        fake_context.__exit__ = Mock(return_value=None)

        with patch.object(agent_tools.db_engine, "connect", return_value=fake_context):
            result = agent_tools.query_telemetry_data.invoke(
                "SELECT TS_UTC, V_LAT FROM v_agent_fleet LIMIT 1"
            )

        self.assertIn("Returned 1 row(s)", result)
        self.assertIn("40.3", result)

    def test_sop_tool_returns_retrieved_context(self):
        fake_document = SimpleNamespace(
            metadata={"source_file": "chain_logistics.md", "chunk_id": 1},
            page_content="Keep fresh perishables between 0.0°C and 4.0°C.",
        )

        with patch.object(
            type(agent_tools.sop_retriever),
            "invoke",
            return_value=[fake_document],
        ):
            result = agent_tools.search_compliance_sop.invoke("temperature limits")

        self.assertIn("chain_logistics.md", result)
        self.assertIn("0.0°C and 4.0°C", result)

    def test_weather_tool_formats_current_weather(self):
        fake_response = Mock()
        fake_response.json.return_value = {
            "current": {"temperature_2m": 27.7, "wind_speed_10m": 13.9}
        }
        fake_response.raise_for_status.return_value = None

        with patch.object(agent_tools.requests, "get", return_value=fake_response):
            result = agent_tools.get_corridor_weather.invoke(
                {"latitude": 34.0522, "longitude": -118.2437}
            )

        self.assertIn("temperature=27.7°C", result)
        self.assertIn("wind_speed=13.9 km/h", result)

    def test_out_of_scope_policy_is_present(self):
        self.assertIn(
            "I can only help with cold-chain shipment data",
            SYSTEM_PROMPT,
        )
        self.assertIn("Do not mention Streamlit", SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
