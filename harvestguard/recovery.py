"""Recovery option comparison. Uses only farmer-entered numbers and shows ranges, never promised profit."""
RANGE = 0.20  # assumption: entered costs may be off by +/-20%


def _check(v, name, low=0, high=None):
    if v is None or v < low or (high is not None and v > high):
        raise ValueError(f"{name} is not valid.")


def compare_options(crop, candidates, acres, damage_pct, days_left, seed, labour, inputs, maintain, sunk):
    """crop and candidates are dicts with name and days_to_harvest."""
    _check(acres, "Acres", 0.01)
    _check(damage_pct, "Damage", 0, 100)
    _check(days_left, "Days left in the planting window")
    for v, n in ((seed, "Seed cost"), (labour, "Labour cost"), (inputs, "Input cost"),
                 (maintain, "Maintenance cost"), (sunk, "Money already spent")):
        _check(v, n)

    def rng(x):
        return round(x * (1 - RANGE)), round(x * (1 + RANGE))

    replant_cost = (seed + labour + inputs) * acres
    exposure = sunk * damage_pct / 100
    opts = []

    lo, hi = rng(0)
    opts.append({"key": "assess", "title": "Ask for a field assessment first", "feasible": True,
                 "cost_low": lo, "cost_high": hi, "exposure": round(exposure),
                 "notes": ["Often free or low cost through your county extension office. Ask before spending more.",
                           "Recommended when damage is large or you are unsure what caused it."]})

    lo, hi = rng(maintain)
    opts.append({"key": "protect", "title": "Protect and maintain the current crop", "feasible": damage_pct < 100,
                 "cost_low": lo, "cost_high": hi, "exposure": round(exposure),
                 "notes": ["Makes most sense if damage is partial and the plants are still growing.",
                           "Your possible loss shown is spending already at risk, not a yield forecast."]})

    lo, hi = rng(replant_cost)
    ok = crop["days_to_harvest"] <= days_left
    opts.append({"key": "replant", "title": f"Replant {crop['name']}", "feasible": ok,
                 "cost_low": lo, "cost_high": hi, "exposure": round(replant_cost),
                 "notes": [f"{crop['name']} needs about {crop['days_to_harvest']} days; you have {days_left}." +
                           ("" if ok else " Too late in the season."),
                           "Confirm the planting window and seed availability with local guidance."]})

    fits = [c["name"] for c in candidates if c["name"] != crop["name"] and c["days_to_harvest"] <= days_left]
    opts.append({"key": "switch", "title": "Switch to a faster crop", "feasible": bool(fits),
                 "cost_low": lo, "cost_high": hi, "exposure": round(replant_cost),
                 "notes": [("Crops that fit your remaining days: " + ", ".join(fits) + ".") if fits
                           else "No supported crop fits the days you have left.",
                           "Cost assumes similar spending as replanting. Replace it with real seed quotes.",
                           "Check soil suitability and local advice before switching."]})
    return opts
