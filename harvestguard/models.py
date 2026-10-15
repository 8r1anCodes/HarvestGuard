from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Farmer(db.Model):
    __tablename__ = "farmers"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    language = db.Column(db.String(2), default="en")  # en or sw
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    farms = db.relationship("Farm", backref="farmer", lazy=True)


class Farm(db.Model):
    __tablename__ = "farms"
    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey("farmers.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    county = db.Column(db.String(60), nullable=False)
    ward = db.Column(db.String(60))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    soil_type = db.Column(db.String(30))      # loam, clay, sandy
    water_source = db.Column(db.String(30))   # rain-fed, borehole, irrigation
    size_acres = db.Column(db.Float)
    plantings = db.relationship("PlantingRecord", backref="farm", lazy=True)


class Crop(db.Model):
    __tablename__ = "crops"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    swahili_name = db.Column(db.String(60))
    min_rain_mm = db.Column(db.Integer)       # seasonal rainfall needed
    max_rain_mm = db.Column(db.Integer)
    days_to_harvest = db.Column(db.Integer)
    shelf_life_days = db.Column(db.Integer)   # at ambient temperature
    price_kes_per_kg = db.Column(db.Float)    # sample price


class PlantingRecord(db.Model):
    __tablename__ = "planting_records"
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey("farms.id"), nullable=False)
    crop_id = db.Column(db.Integer, db.ForeignKey("crops.id"), nullable=False)
    planting_date = db.Column(db.Date, nullable=False)
    area_acres = db.Column(db.Float)
    season = db.Column(db.String(20))         # long rains, short rains
    expected_harvest_date = db.Column(db.Date)
    crop = db.relationship("Crop")
    harvests = db.relationship("HarvestRecord", backref="planting", lazy=True)


class HarvestRecord(db.Model):
    __tablename__ = "harvest_records"
    id = db.Column(db.Integer, primary_key=True)
    planting_id = db.Column(db.Integer, db.ForeignKey("planting_records.id"), nullable=False)
    harvest_date = db.Column(db.Date, nullable=False)
    quantity_kg = db.Column(db.Float, nullable=False)
    has_cold_storage = db.Column(db.Boolean, default=False)
    distance_to_market_km = db.Column(db.Float)
    predictions = db.relationship("Prediction", backref="harvest", lazy=True)


class Prediction(db.Model):
    __tablename__ = "predictions"
    id = db.Column(db.Integer, primary_key=True)
    harvest_id = db.Column(db.Integer, db.ForeignKey("harvest_records.id"), nullable=False)
    spoilage_risk_pct = db.Column(db.Float)
    risk_level = db.Column(db.String(10))     # low, medium, high
    quantity_at_risk_kg = db.Column(db.Float)
    estimated_loss_kes = db.Column(db.Float)
    recommendation = db.Column(db.String(20)) # sell, store, transport
    reasons = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
