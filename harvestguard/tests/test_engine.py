import os, sys, unittest
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import risk_engine as re_
import recovery as rc

TODAY = date(2026, 10, 14)
WET = {"rain": [5, 10, 30, 40, 25, 8, 2], "tmax": [24] * 7, "live": True}
DRY = {"rain": [0, 0, 1, 0, 0, 2, 0], "tmax": [30] * 7, "live": True}
CALM = {"rain": [5, 6, 7, 5, 4, 6, 5], "tmax": [24] * 7, "live": True}


def planted(days): return TODAY - timedelta(days=days)


class RiskTests(unittest.TestCase):
    def test_stage_detection(self):
        s, d, past = re_.get_stage("Maize", planted(60), TODAY)
        self.assertEqual(s["name"], "Tasselling and silking"); self.assertEqual(d, 60); self.assertFalse(past)

    def test_future_date_rejected(self):
        with self.assertRaises(ValueError): re_.get_stage("Maize", TODAY + timedelta(days=2), TODAY)

    def test_unknown_crop_rejected(self):
        with self.assertRaises(ValueError): re_.get_stage("Avocado", planted(10), TODAY)

    def test_waterlogging_high_when_poor_drainage_clay_sensitive_stage(self):
        r = re_.assess("Tomatoes", planted(50), "clay", "poor", "standing_water", False, WET, TODAY)
        wl = next(h for h in r["hazards"] if h["key"] == "waterlogging")
        self.assertEqual(wl["level"], "high"); self.assertTrue(r["contact_extension"])

    def test_good_drainage_sandy_lowers_risk(self):
        a = re_.assess("Maize", planted(20), "sandy", "good", "healthy", False, WET, TODAY)
        b = re_.assess("Maize", planted(20), "clay", "poor", "healthy", False, WET, TODAY)
        sa = next(h for h in a["hazards"] if h["key"] == "waterlogging")["score"]
        sb = next(h for h in b["hazards"] if h["key"] == "waterlogging")["score"]
        self.assertLess(sa, sb)

    def test_irrigation_lowers_drought_risk(self):
        a = re_.assess("Beans", planted(40), "loam", "moderate", "healthy", True, DRY, TODAY)
        b = re_.assess("Beans", planted(40), "loam", "moderate", "healthy", False, DRY, TODAY)
        f = lambda r: next(h for h in r["hazards"] if h["key"] == "drought")["score"]
        self.assertLess(f(a), f(b))

    def test_calm_weather_all_low(self):
        r = re_.assess("Maize", planted(30), "loam", "good", "healthy", False, CALM, TODAY)
        self.assertTrue(all(h["level"] == "low" for h in r["hazards"])); self.assertFalse(r["contact_extension"])

    def test_missing_data_is_reported(self):
        c = dict(CALM, live=False)
        r = re_.assess("Maize", planted(30), "loam", "unknown", "unknown", False, c, TODAY)
        text = " ".join(r["missing"])
        self.assertIn("DEMONSTRATION", text); self.assertIn("drainage", text); self.assertIn("condition", text)


MAIZE = {"name": "Maize", "days_to_harvest": 120}
ALL = [MAIZE, {"name": "Beans", "days_to_harvest": 90}, {"name": "Kale", "days_to_harvest": 60}]


class RecoveryTests(unittest.TestCase):
    def run_it(self, **kw):
        a = dict(crop=MAIZE, candidates=ALL, acres=2, damage_pct=60, days_left=100, seed=3000, labour=2000,
                 inputs=4000, maintain=2500, sunk=20000); a.update(kw)
        return rc.compare_options(**a)

    def test_replant_not_feasible_when_too_late(self):
        o = {x["key"]: x for x in self.run_it()}
        self.assertFalse(o["replant"]["feasible"]); self.assertTrue(o["switch"]["feasible"])

    def test_cost_range_is_plus_minus_20_percent(self):
        o = {x["key"]: x for x in self.run_it(days_left=130)}
        self.assertEqual(o["replant"]["cost_low"], 14400); self.assertEqual(o["replant"]["cost_high"], 21600)

    def test_exposure_uses_damage_share(self):
        o = {x["key"]: x for x in self.run_it()}
        self.assertEqual(o["protect"]["exposure"], 12000)

    def test_no_switch_option_when_nothing_fits(self):
        o = {x["key"]: x for x in self.run_it(days_left=30)}
        self.assertFalse(o["switch"]["feasible"])

    def test_invalid_inputs_rejected(self):
        for bad in ({"acres": 0}, {"damage_pct": 120}, {"seed": -5}, {"days_left": -1}):
            with self.assertRaises(ValueError): self.run_it(**bad)


if __name__ == "__main__":
    unittest.main()
