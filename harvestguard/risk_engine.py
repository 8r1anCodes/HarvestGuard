"""Transparent, rule-based crop-stage risk engine.
All agronomic numbers live in rules/crop_rules.json so experts can review them.
This is NOT a validated scientific prediction."""
import json
import os
from datetime import date

RULES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules", "crop_rules.json")
with open(RULES_PATH, encoding="utf-8") as fh:
    RULES = json.load(fh)

DISCLAIMER = ("This is a rule-based guide using a 7-day forecast. Forecasts can be wrong, and the rules "
              "are drafts awaiting expert review. It is not a validated prediction. Check your field and "
              "ask an extension officer before spending money.")


def supported_crops():
    return list(RULES["crops"])


def get_stage(crop, planting_date, today=None):
    if crop not in RULES["crops"]:
        raise ValueError(f"No stage rules for {crop} yet.")
    today = today or date.today()
    day = (today - planting_date).days
    if day < 0:
        raise ValueError("Planting date cannot be in the future.")
    stages = RULES["crops"][crop]["stages"]
    for s in stages:
        if s["from"] <= day <= s["to"]:
            return s, day, False
    return stages[-1], day, True  # beyond the last stage


def _level(score):
    return "high" if score >= 6 else "medium" if score >= 4 else "low"


def assess(crop, planting_date, soil, drainage, condition, irrigation, climate, today=None):
    stage, day, past_end = get_stage(crop, planting_date, today)
    th = RULES["thresholds"]
    rain, tmax = climate["rain"], climate["tmax"]
    total, peak, hottest = sum(rain), max(rain), max(tmax)

    triggers = {
        "waterlogging": (peak >= th["heavy_day_mm"] or total >= th["heavy_week_mm"],
                         f"Forecast: {total:.0f} mm this week, up to {peak:.0f} mm in one day"),
        "drought": (total <= th["dry_week_mm"], f"Forecast: only {total:.0f} mm this week"),
        "heat": (hottest >= th["hot_day_c"], f"Forecast: highs up to {hottest:.0f}°C"),
    }
    hazards = []
    for key, (hit, trigger_text) in triggers.items():
        info = RULES["hazards"][key]
        if not hit:
            hazards.append({"key": key, "title": info["title"], "level": "low", "score": 0,
                            "factors": ["No trigger in the 7-day forecast"], "inspect": [], "actions": []})
            continue
        sens = stage[key]
        score = sens * 2
        factors = [trigger_text, f"{stage['name']} stage is sensitivity {sens} of 3 for this hazard (+{sens * 2})"]

        def adj(points, text):
            nonlocal score
            score += points
            factors.append(f"{text} ({'+' if points > 0 else ''}{points:g})")

        if key == "waterlogging":
            if drainage == "poor": adj(1.5, "Poor drainage raises the risk")
            if drainage == "good": adj(-1, "Good drainage lowers the risk")
            if soil == "clay": adj(1, "Clay soil holds water")
            if soil == "sandy": adj(-1, "Sandy soil drains quickly")
            if condition == "standing_water": adj(2, "You report standing water")
        elif key == "drought":
            if soil == "sandy": adj(1, "Sandy soil dries out fast")
            if soil == "clay": adj(-0.5, "Clay soil holds moisture")
            if irrigation: adj(-2, "You have irrigation")
            if condition == "wilting": adj(1.5, "You report wilting")
        else:
            if irrigation: adj(-1, "Irrigation can cool the crop")
            if condition == "wilting": adj(1, "You report wilting")
        hazards.append({"key": key, "title": info["title"], "level": _level(score), "score": round(score, 1),
                        "factors": factors, "inspect": info["inspect"], "actions": info["actions"]})

    worst = [h for h in hazards if h["level"] != "low"]
    contact = any(h["level"] == "high" for h in hazards) or (
        bool(worst) and condition in ("wilting", "standing_water", "yellowing"))
    missing = ["Crop variety is not recorded; sensitivity differs between varieties",
               "Forecasts are uncertain; check again tomorrow"]
    if not climate.get("live", True):
        missing.insert(0, "Live forecast unavailable. Showing DEMONSTRATION weather data")
    if drainage == "unknown": missing.append("Field drainage is unknown")
    if condition == "unknown": missing.append("Current crop condition not reported")
    if past_end: missing.append("The crop is past its expected growing period; assess for harvest")
    return {"crop": crop, "day": day, "stage": stage["name"], "hazards": hazards,
            "contact_extension": contact, "missing": missing, "disclaimer": DISCLAIMER}
