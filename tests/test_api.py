import unittest
from fastapi.testclient import TestClient
from backend.api import app, longest_outage


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.payload = dict(site=dict(id="test", latitude=-89, longitude=0),
                            date="2026-11-14", durationDays=2, filters={})

    def test_real_ephemeris_and_custom_rules(self):
        self.payload["customFilters"] = [dict(id="sun", label="Sun", metric="sunlightPercent", operator="gte", threshold=100)]
        response = self.client.post("/api/analyze", json=self.payload)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        for key in ["sunlightPercent", "earthVisibilityPercent"]:
            self.assertTrue(0 <= result[key] <= 100)
        self.assertTrue(0 <= result["maxDarknessHours"] <= 48)
        self.assertEqual(result["customFilterResults"][0]["passed"], result["sunlightPercent"] >= 100)
        timeline = result["timeline"]
        self.assertEqual(timeline["sampleCount"], 288)
        self.assertEqual(timeline["endUtc"], "2026-11-16T00:00:00Z")
        for channel, metric in [("sun", "sunlightPercent"), ("earth", "earthVisibilityPercent")]:
            runs = timeline[channel]
            self.assertEqual(runs[0]["start"], 0)
            self.assertEqual(runs[-1]["end"], 288)
            for left, right in zip(runs, runs[1:]):
                self.assertEqual(left["end"], right["start"])
                self.assertNotEqual(left["visible"], right["visible"])
            visible = sum(s["end"] - s["start"] for s in runs if s["visible"])
            self.assertEqual(round(visible / 288 * 100, 2), result[metric])

    def test_instant_does_not_invent_outage_duration(self):
        self.payload["filters"] = dict(analysisMode="instant")
        result = self.client.post("/api/analyze", json=self.payload).json()
        self.assertIn(result["sunlightPercent"], [0, 100])
        self.assertNotIn("maxDarknessHours", result)
        self.assertTrue(result["timeline"]["instant"])
        self.assertEqual(result["timeline"]["sampleCount"], 1)

    def test_invalid_requests(self):
        for field, value in [("date", "2200-01-01"), ("durationDays", 0), ("durationDays", 1.5), ("filters", {"sunElevation": 91})]:
            with self.subTest(field=field, value=value):
                self.assertEqual(self.client.post("/api/analyze", json={**self.payload, field: value}).status_code, 422)

    def test_outages_include_window_edges(self):
        self.assertEqual(longest_outage([False, False, True, False], .5), 1)
        self.assertEqual(longest_outage([True, True], .5), 0)

    def test_visibility_uses_terrain_horizon(self):
        import numpy as np
        from backend.horizon import body_visibility
        vectors = self.client.get("/api/positions?date=2026-11-14").json()
        result = self.client.post("/api/analyze", json={**self.payload, "filters": {"analysisMode": "instant"}}).json()
        for body, metric in [("sun", "sunlightPercent"), ("earth", "earthVisibilityPercent")]:
            expected = body_visibility(np.array([vectors[body]]), -89, 0)[0]
            self.assertEqual(result[metric], 100 if expected else 0)
        horizon = self.client.get("/api/horizon?latitude=-89&longitude=0").json()
        self.assertEqual(len(horizon["horizonRadians"]), 720)
        self.assertTrue(np.ptp(horizon["horizonRadians"]) > 0)

    def test_position_timeline_matches_daily_positions(self):
        import numpy as np
        response = self.client.get("/api/position-timeline?date=2026-11-14&durationDays=2")
        self.assertEqual(response.status_code, 200, response.text)
        series = response.json()
        self.assertEqual(len(series["times"]), 49)
        self.assertEqual(series["times"][1], "2026-11-14T01:00:00Z")
        self.assertEqual(series["times"][-1], "2026-11-16T00:00:00Z")
        for index, date in [(0, "2026-11-14"), (24, "2026-11-15"), (48, "2026-11-16")]:
            instant = self.client.get(f"/api/positions?date={date}").json()
            for body in ["sun", "earth"]:
                self.assertEqual(len(series[body]), 49)
                np.testing.assert_allclose(series[body][index], instant[body])
        self.assertFalse(np.allclose(series["sun"][0], series["sun"][12]))

    def test_position_timeline_rejects_invalid_windows(self):
        for query in ["date=2026-11-14&durationDays=0", "date=2026-11-14&durationDays=366",
                      "date=2149-12-31&durationDays=2", "date=1849-12-31", "date=invalid"]:
            self.assertEqual(self.client.get("/api/position-timeline?" + query).status_code, 422)


if __name__ == "__main__":
    unittest.main()
