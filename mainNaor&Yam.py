import os
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_socketio import SocketIO, emit
from supabase import create_client, Client
from models import db, Group, Member

app = Flask('Naor&Yam-Bucket', template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = '050426_Love'

# הגדרת אורך חיים של ה-Session (למשל: 30 ימים של זכירת התחברות)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# SQLite / SQLAlchemy settings
os.makedirs(app.instance_path, exist_ok=True)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(app.instance_path, "couple_list.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
with app.app_context():
    db.create_all()

# SocketIO & Supabase
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')
SUPABASE_URL = "https://hjpqmbufbzjkfetfetmx.supabase.co"
SUPABASE_KEY = "sb_publishable_B6JpVap4JAiDzziiSVE0yA_3CV6aV7T"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_suggested_pin():
    used_pins = {m.pin for m in Member.query.all() if m.pin}
    for i in range(1, 1001):
        if str(i) not in used_pins:
            return str(i)
    return "1001"


# ------------------------------------------------------
# HTTP Routes
# ------------------------------------------------------

# מסך כניסה - בודק אם המשתמש כבר שמור במערכת
@app.get("/")
def home():
    if "member_id" in session:
        # המשתמש כבר מחובר ונזכר במכשיר הזה -> מעבירים ישירות למסך הראשי
        return redirect(url_for("base_screen_dashboard"))
    return render_template("login.html")


@app.get("/baseScreen")
def base_screen_dashboard():
    # אופציונלי: אבטחה שרק מחוברים ייכנסו
    if "member_id" not in session:
        return redirect(url_for("home"))

    # שולפים את פרטי המשתמש המחובר מהסשן
    current_member = Member.query.get(session["member_id"])
    return render_template("base_screen.html", current_member=current_member)


# התחברות
@app.post("/login")
def login():
    member_pin = request.form.get("member_pin", "").strip()
    remember_me = request.form.get("remember_me")  # בדיקה אם התיבה סומנה

    member = Member.query.filter_by(pin=member_pin).first()
    if not member:
        flash("קוד משתמש לא קיים או שגוי 💔")
        return redirect(url_for("home"))

    # שמירת המשתמש בסשן
    session["member_id"] = member.id

    # אם המשתמש סימן "זכור אותי", קובעים שהסשן יישמר ל-30 יום
    if remember_me:
        session.permanent = True
    else:
        session.permanent = False

    return redirect(url_for("base_screen_dashboard"))


# התנתקות (אופציונלי - אם המשתמש ירצה לצאת מהחשבון במכוון)
@app.get("/logout")
def logout():
    session.pop("member_id", None)
    flash("התנתקת בהצלחה 👋")
    return redirect(url_for("home"))


@app.get("/create_group")
def create_group_form():
    suggested_pin = get_suggested_pin()
    return render_template("sign_up.html", suggested_pin=suggested_pin)


@app.post("/create_group")
def create_group():
    action_type = request.form.get("action_type")
    member_name = request.form.get("member_name", "").strip()
    member_pin = request.form.get("member_pin", "").strip()

    if Member.query.filter_by(pin=member_pin).first():
        flash(f"קוד המשתמש האישי {member_pin} כבר תפוס במערכת! 💔")
        return redirect(url_for("create_group_form"))

    group = None
    if action_type == "join":
        group_pin = request.form.get("existing_group_pin", "").strip()
        group = Group.query.filter_by(pin=group_pin).first()
        if not group:
            flash(f"קבוצה עם קוד '{group_pin}' לא נמצאה 💔")
            return redirect(url_for("create_group_form"))

    elif action_type == "create":
        group_name = request.form.get("new_group_name", "").strip()
        group_pin = request.form.get("new_group_pin", "").strip()

        if Group.query.filter_by(pin=group_pin).first():
            flash(f"קוד הקבוצה '{group_pin}' כבר תפוס במערכת! 💔")
            return redirect(url_for("create_group_form"))

        group = Group(name=group_name, pin=group_pin)
        db.session.add(group)
        db.session.commit()

    if group:
        new_member = Member(name=member_name, pin=member_pin, group_id=group.id)
        db.session.add(new_member)
        db.session.commit()

        # חיבור אוטומטי מיד לאחר הרשמה
        session["member_id"] = new_member.id
        session.permanent = True

        flash(f"נרשמת בהצלחה ל-{group.name}! 🎉")
        return redirect(url_for("base_screen_dashboard"))

    return redirect(url_for("create_group_form"))

# (שאר המסלולים והאירועים נשארים ללא שינוי...)