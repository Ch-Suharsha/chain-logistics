import unittest

from src.agent_tools import validate_telemetry_query


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


if __name__ == "__main__":
    unittest.main()
