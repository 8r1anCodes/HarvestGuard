from datetime import date, timedelta
from werkzeug.security import generate_password_hash
from models import db, Farmer, Farm, Crop, PlantingRecord, HarvestRecord, Prediction


def seed_if_empty():
    if Crop.query.first():
        return
    crops = [
        Crop(name="Maize", swahili_name="Mahindi", min_rain_mm=500, max_rain_mm=1200, days_to_harvest=120, shelf_life_days=180, price_kes_per_kg=55),
        Crop(name="Beans", swahili_name="Maharagwe", min_rain_mm=350, max_rain_mm=800, days_to_harvest=90, shelf_life_days=120, price_kes_per_kg=120),
        Crop(name="Tomatoes", swahili_name="Nyanya", min_rain_mm=400, max_rain_mm=800, days_to_harvest=90, shelf_life_days=7, price_kes_per_kg=60),
        Crop(name="Potatoes", swahili_name="Viazi", min_rain_mm=500, max_rain_mm=1000, days_to_harvest=100, shelf_life_days=60, price_kes_per_kg=45),
        Crop(name="Kale", swahili_name="Sukuma wiki", min_rain_mm=400, max_rain_mm=900, days_to_harvest=60, shelf_life_days=4, price_kes_per_kg=40),
        Crop(name="Avocado", swahili_name="Parachichi", min_rain_mm=800, max_rain_mm=1500, days_to_harvest=240, shelf_life_days=10, price_kes_per_kg=80),
    ]
    db.session.add_all(crops)
    demo = Farmer(full_name="Demo Farmer", phone="0700000000", password_hash=generate_password_hash("demo1234", method="pbkdf2:sha256"))
    db.session.add(demo)
    db.session.flush()
    farm = Farm(farmer_id=demo.id, name="Kapseret Farm", county="Uasin Gishu", ward="Kapseret",
                latitude=0.5143, longitude=35.2698, soil_type="loam", water_source="rain-fed", size_acres=3)
    db.session.add(farm)
    db.session.flush()
    p = PlantingRecord(farm_id=farm.id, crop_id=crops[2].id, planting_date=date.today() - timedelta(days=90),
                       area_acres=1, season="long rains", expected_harvest_date=date.today())
    db.session.add(p)
    db.session.flush()
    h = HarvestRecord(planting_id=p.id, harvest_date=date.today(), quantity_kg=420, has_cold_storage=False, distance_to_market_km=6)
    db.session.add(h)
    db.session.flush()
    db.session.add(Prediction(harvest_id=h.id, spoilage_risk_pct=82, risk_level="high", quantity_at_risk_kg=344,
                              estimated_loss_kes=20640, recommendation="sell",
                              reasons="Heavy rain forecast; no cold storage; short shelf life"))
    db.session.commit()
