import requests

COUNTIES = {
    "Baringo": (0.4919, 35.7430), "Bomet": (-0.7813, 35.3416), "Bungoma": (0.5635, 34.5606),
    "Busia": (0.4608, 34.1115), "Elgeyo-Marakwet": (0.6703, 35.5081), "Embu": (-0.5389, 37.4596),
    "Garissa": (-0.4532, 39.6461), "Homa Bay": (-0.5273, 34.4571), "Isiolo": (0.3546, 37.5822),
    "Kajiado": (-1.8520, 36.7820), "Kakamega": (0.2827, 34.7519), "Kericho": (-0.3689, 35.2863),
    "Kiambu": (-1.1714, 36.8356), "Kilifi": (-3.6305, 39.8499), "Kirinyaga": (-0.4989, 37.2803),
    "Kisii": (-0.6817, 34.7667), "Kisumu": (-0.0917, 34.7680), "Kitui": (-1.3667, 38.0106),
    "Kwale": (-4.1816, 39.4606), "Laikipia": (0.2667, 36.5333), "Lamu": (-2.2717, 40.9020),
    "Machakos": (-1.5177, 37.2634), "Makueni": (-1.8039, 37.6208), "Mandera": (3.9366, 41.8670),
    "Marsabit": (2.3284, 37.9899), "Meru": (0.0480, 37.6559), "Migori": (-1.0634, 34.4731),
    "Mombasa": (-4.0435, 39.6682), "Murang'a": (-0.7210, 37.1526), "Nairobi": (-1.2921, 36.8219),
    "Nakuru": (-0.3031, 36.0800), "Nandi": (0.2046, 35.1050), "Narok": (-1.0783, 35.8600),
    "Nyamira": (-0.5633, 34.9358), "Nyandarua": (-0.2667, 36.3833), "Nyeri": (-0.4201, 36.9476),
    "Samburu": (1.0966, 36.6984), "Siaya": (0.0607, 34.2881), "Taita-Taveta": (-3.3960, 38.5560),
    "Tana River": (-1.5167, 40.0333), "Tharaka-Nithi": (-0.3333, 37.6500), "Trans Nzoia": (1.0157, 35.0062),
    "Turkana": (3.1191, 35.5973), "Uasin Gishu": (0.5143, 35.2698), "Vihiga": (0.0500, 34.7167),
    "Wajir": (1.7471, 40.0573), "West Pokot": (1.2389, 35.1119),
}
LOCATIONS = COUNTIES  # kept so other files keep working
SOIL_OK = {"Maize": ["loam", "clay"], "Beans": ["loam", "sandy"], "Tomatoes": ["loam", "sandy"],
           "Potatoes": ["loam", "sandy"], "Kale": ["loam", "clay"], "Avocado": ["loam", "sandy"]}
WINDOWS = {"long rains": "Mid March to April", "short rains": "Mid October to November",
           "dry season": "Only with irrigation; plant when water is secure"}
TIPS = {
    "Maize": ["Use certified seed and top-dress with CAN at knee height", "Weed twice in the first 6 weeks", "Dry grain to 13% moisture before storing"],
    "Beans": ["Plant in rows with DAP at planting", "Scout for aphids and bean rust", "Harvest when pods turn yellow and dry"],
    "Tomatoes": ["Stake plants and mulch to hold moisture", "Water steadily; uneven watering splits fruit", "Harvest at the pink stage for transport"],
    "Potatoes": ["Earth up twice to protect tubers from light", "Rotate away from potato or tomato fields", "Cure tubers in shade for a few days"],
    "Kale": ["Pick lower leaves regularly to keep plants producing", "Feed with manure or CAN every 3 weeks", "Pick in the early morning and keep shaded"],
    "Avocado": ["Mulch young trees and prune for light", "Harvest only mature fruit", "Handle gently; bruising ruins grade"],
}


def recommend_crops(crops, soil, water, rainfall):
    out = []
    for c in crops:
        score, notes = 0, []
        if c.min_rain_mm <= rainfall <= c.max_rain_mm:
            score += 50; notes.append("Rainfall suits it")
        elif rainfall < c.min_rain_mm:
            if water in ("borehole", "irrigation"):
                score += 30; notes.append("Rain is low, so irrigate")
            else:
                notes.append("Too dry without irrigation")
        else:
            score += 15; notes.append("Rain may be too high; watch drainage")
        if soil in SOIL_OK[c.name]:
            score += 30; notes.append(f"Does well in {soil} soil")
        else:
            notes.append(f"{soil.title()} soil is not ideal")
        if c.days_to_harvest <= 100:
            score += 10; notes.append("Quick to harvest")
        if c.shelf_life_days >= 30:
            score += 10; notes.append("Keeps well after harvest")
        out.append({"crop": c, "score": score, "notes": notes})
    return sorted(out, key=lambda x: -x["score"])


def get_climate(place):
    lat, lon = COUNTIES.get(place, COUNTIES["Uasin Gishu"])
    live = True
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", timeout=5, params={
            "latitude": lat, "longitude": lon, "timezone": "Africa/Nairobi", "forecast_days": 7,
            "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min"})
        d = r.json()["daily"]
        days, rain = d["time"], [x or 0 for x in d["precipitation_sum"]]
        tmax, tmin = [x or 0 for x in d["temperature_2m_max"]], [x or 0 for x in d["temperature_2m_min"]]
    except Exception:
        live = False
        days = ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5", "Day 6", "Day 7"]
        rain, tmax, tmin = [4, 8, 28, 42, 31, 10, 3], [24] * 7, [11] * 7
    total, avg_max = sum(rain), sum(tmax) / len(tmax)
    alerts = []
    if max(rain) >= 20 or total >= 60:
        alerts.append(("high", "Heavy rain risk", "Harvest ripe crops early, cover produce, and avoid transporting on bad roads."))
    if total < 5 and avg_max >= 28:
        alerts.append(("high", "Drought risk", "Irrigate early in the morning, mulch, and delay planting until rain returns."))
    elif total < 10:
        alerts.append(("medium", "Dry week", "Check soil moisture and plan watering."))
    if avg_max >= 32:
        alerts.append(("medium", "Heat stress", "Shade fresh produce and harvest in the cool of the morning."))
    if not alerts:
        alerts.append(("low", "Conditions look normal", "Good week for routine field work."))
    return {"place": place, "live": live, "days": days, "rain": rain, "tmax": tmax, "tmin": tmin,
            "total": round(total, 1), "avg_max": round(avg_max, 1), "alerts": alerts,
            "heavy": any(a[1] == "Heavy rain risk" for a in alerts)}


def assess_spoilage(crop, qty, cold, distance_km, days_to_sell, rain):
    shelf = crop.shelf_life_days * (2.5 if cold else 1) / (1.4 if rain else 1)
    exposed = days_to_sell + distance_km / 200
    risk = round(max(5, min(95, exposed / shelf * 100)), 1)
    level = "high" if risk >= 60 else "medium" if risk >= 30 else "low"
    at_risk = round(qty * risk / 100, 1)
    loss = round(at_risk * crop.price_kes_per_kg)
    if level == "high":
        rec = "sell"
    elif level == "medium":
        rec = "transport"
    else:
        rec = "store" if crop.shelf_life_days >= 30 else "transport"
    reasons = []
    if crop.shelf_life_days <= 10: reasons.append("Short shelf life")
    if not cold: reasons.append("No cold storage")
    if rain: reasons.append("Wet weather speeds spoilage")
    if distance_km >= 100: reasons.append("Long distance to market")
    if days_to_sell >= 3: reasons.append("Several days before sale")
    return {"risk": risk, "level": level, "at_risk": at_risk, "loss": loss, "rec": rec,
            "reasons": reasons or ["Conditions are favourable"]}
