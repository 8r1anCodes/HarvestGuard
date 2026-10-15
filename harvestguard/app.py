import os
import re
import secrets
from datetime import date, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, Farmer, Farm, Crop, PlantingRecord, HarvestRecord, Prediction
from logic import COUNTIES, WINDOWS, TIPS, recommend_crops, get_climate, assess_spoilage
from seed import seed_if_empty
import risk_engine
import recovery as recovery_calc

app = Flask(__name__)
BASE = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE, "harvestguard.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-before-production")
db.init_app(app)

with app.app_context():
    db.create_all()
    seed_if_empty()


# ---------- helpers ----------
def current_farmer():
    fid = session.get("farmer_id")
    return db.session.get(Farmer, fid) if fid else None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_farmer():
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def my_farm():
    return Farm.query.filter_by(farmer_id=session["farmer_id"]).first()


def clean_phone(raw):
    p = re.sub(r"[\s\-()]", "", raw or "")
    if p.startswith("+254"):
        p = "0" + p[4:]
    elif p.startswith("254"):
        p = "0" + p[3:]
    elif len(p) == 9 and p[0] in "17":
        p = "0" + p
    return p


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return session["csrf_token"]


@app.before_request
def csrf_protect():
    if request.method == "POST":
        sent, real = request.form.get("csrf_token", ""), session.get("csrf_token", "")
        if not real or not secrets.compare_digest(sent, real):
            abort(400, "Security check failed. Go back, refresh the page and try again.")


@app.context_processor
def inject_user():
    return {"current_farmer": current_farmer(), "csrf_token": csrf_token}


# ---------- auth ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if current_farmer():
        return redirect(url_for("dashboard"))
    f = request.form
    if request.method == "POST":
        name, phone, county, pw = f["full_name"].strip(), clean_phone(f["phone"]), f["county"], f["password"]
        error = None
        if len(name) < 2:
            error = "Please enter your full name."
        elif not re.fullmatch(r"0[17]\d{8}", phone):
            error = "Enter a valid Kenyan phone number, like 0712345678."
        elif county not in COUNTIES:
            error = "Please choose your county."
        elif len(pw) < 6:
            error = "Password must be at least 6 characters."
        elif Farmer.query.filter_by(phone=phone).first():
            error = "That phone number is already registered. Try logging in."
        if error:
            flash(error, "error")
        else:
            farmer = Farmer(full_name=name, phone=phone,
                            password_hash=generate_password_hash(pw, method="pbkdf2:sha256"))
            db.session.add(farmer)
            db.session.flush()
            lat, lon = COUNTIES[county]
            db.session.add(Farm(farmer_id=farmer.id, name=f"{name.split()[0]}'s Farm", county=county,
                                latitude=lat, longitude=lon, soil_type="loam", water_source="rain-fed", size_acres=1))
            db.session.commit()
            session["farmer_id"] = farmer.id
            flash(f"Welcome, {name.split()[0]}! Your account is ready.", "ok")
            return redirect(url_for("dashboard"))
    return render_template("register.html", counties=COUNTIES, f=f)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_farmer():
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        farmer = Farmer.query.filter_by(phone=clean_phone(request.form["phone"])).first()
        if farmer and check_password_hash(farmer.password_hash, request.form["password"]):
            session["farmer_id"] = farmer.id
            flash(f"Welcome back, {farmer.full_name.split()[0]}.", "ok")
            return redirect(url_for("dashboard"))
        flash("Wrong phone number or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "ok")
    return redirect(url_for("index"))


# ---------- pages ----------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/planner", methods=["GET", "POST"])
@login_required
def planner():
    result = None
    if request.method == "POST":
        f = request.form
        picks = recommend_crops(Crop.query.all(), f["soil"], f["water"], float(f["rainfall"]))
        result = {"picks": picks, "window": WINDOWS[f["season"]], "season": f["season"], "place": f["place"]}
    return render_template("planner.html", places=COUNTIES, result=result, default_place=my_farm().county)


@app.route("/climate")
def climate():
    farmer = current_farmer()
    default = my_farm().county if farmer else "Uasin Gishu"
    place = request.args.get("place", default)
    return render_template("climate.html", places=COUNTIES, c=get_climate(place))


@app.route("/advisor", methods=["GET", "POST"])
@login_required
def advisor():
    result = None
    farm = my_farm()
    if request.method == "POST":
        crop = db.session.get(Crop, int(request.form["crop_id"]))
        planted = date.fromisoformat(request.form["planting_date"])
        ready = planted + timedelta(days=crop.days_to_harvest)
        db.session.add(PlantingRecord(farm_id=farm.id, crop_id=crop.id, planting_date=planted,
                                      area_acres=1, expected_harvest_date=ready))
        db.session.commit()
        c = get_climate(request.form["place"])
        result = {"crop": crop, "start": ready - timedelta(days=7), "end": ready + timedelta(days=7),
                  "tips": TIPS[crop.name], "warnings": [a for a in c["alerts"] if a[0] != "low"]}
    return render_template("advisor.html", crops=Crop.query.all(), places=COUNTIES, result=result,
                           today=date.today(), default_place=farm.county)


@app.route("/guard", methods=["GET", "POST"])
@login_required
def guard():
    result = None
    if request.method == "POST":
        f = request.form
        crop = db.session.get(Crop, int(f["crop_id"]))
        qty, dist, days = float(f["quantity"]), float(f["distance"]), float(f["days_to_sell"])
        r = assess_spoilage(crop, qty, "cold" in f, dist, days, "rain" in f)
        p = PlantingRecord(farm_id=my_farm().id, crop_id=crop.id,
                           planting_date=date.today() - timedelta(days=crop.days_to_harvest),
                           area_acres=1, expected_harvest_date=date.today())
        db.session.add(p); db.session.flush()
        h = HarvestRecord(planting_id=p.id, harvest_date=date.today(), quantity_kg=qty,
                          has_cold_storage="cold" in f, distance_to_market_km=dist)
        db.session.add(h); db.session.flush()
        db.session.add(Prediction(harvest_id=h.id, spoilage_risk_pct=r["risk"], risk_level=r["level"],
                                  quantity_at_risk_kg=r["at_risk"], estimated_loss_kes=r["loss"],
                                  recommendation=r["rec"], reasons="; ".join(r["reasons"])))
        db.session.commit()
        result = {**r, "crop": crop, "qty": qty}
    return render_template("guard.html", crops=Crop.query.all(), result=result)


@app.route("/risk", methods=["GET", "POST"])
@login_required
def risk():
    farm, result, error = my_farm(), None, None
    if request.method == "POST":
        f = request.form
        try:
            c = get_climate(farm.county)
            result = risk_engine.assess(f["crop"], date.fromisoformat(f["planting_date"]), f["soil"],
                                        f["drainage"], f["condition"], "irrigation" in f, c)
            result["county"], result["live"] = farm.county, c["live"]
        except (ValueError, KeyError) as e:
            error = str(e)
    return render_template("risk.html", crops=risk_engine.supported_crops(), farm=farm, result=result,
                           error=error, today=date.today(), meta=risk_engine.RULES["meta"])


@app.route("/recovery", methods=["GET", "POST"])
@login_required
def recovery():
    result, error = None, None
    crops = Crop.query.all()
    if request.method == "POST":
        f = request.form
        try:
            crop = db.session.get(Crop, int(f["crop_id"]))
            cands = [{"name": c.name, "days_to_harvest": c.days_to_harvest} for c in crops]
            num = lambda k: float(f.get(k) or 0)
            result = recovery_calc.compare_options(
                {"name": crop.name, "days_to_harvest": crop.days_to_harvest}, cands, num("acres"),
                num("damage"), num("days_left"), num("seed"), num("labour"), num("inputs"),
                num("maintain"), num("sunk"))
            result = {"crop": crop.name, "options": result}
        except (ValueError, TypeError) as e:
            error = str(e)
    return render_template("recovery.html", crops=crops, result=result, error=error)


@app.route("/dashboard")
@login_required
def dashboard():
    farmer, farm = current_farmer(), my_farm()
    preds = (Prediction.query
             .join(HarvestRecord, Prediction.harvest_id == HarvestRecord.id)
             .join(PlantingRecord, HarvestRecord.planting_id == PlantingRecord.id)
             .filter(PlantingRecord.farm_id == farm.id)
             .order_by(Prediction.created_at.desc()).limit(8).all())
    rows = [{"crop": p.harvest.planting.crop.name, "qty": p.harvest.quantity_kg, "p": p} for p in preds]
    plantings = PlantingRecord.query.filter_by(farm_id=farm.id).order_by(PlantingRecord.id.desc()).limit(3).all()
    return render_template("dashboard.html", farmer=farmer, farm=farm, rows=rows,
                           total_loss=sum(p.estimated_loss_kes for p in preds),
                           high=sum(1 for p in preds if p.risk_level == "high"),
                           c=get_climate(farm.county), plantings=plantings)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("FLASK_DEBUG") == "1")
