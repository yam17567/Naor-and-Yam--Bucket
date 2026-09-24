import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_socketio import SocketIO, emit
from supabase import create_client, Client
from models import db, Group, Member

app = Flask('Naor&Yam-Bucket', template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = '050426_Love'

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

# פונקציית עזר להצעת קוד משתמש פנוי (1-1000)
def get_suggested_pin():
    used_pins = {m.pin for m in Member.query.all() if m.pin}
    for i in range(1, 1001):
        if str(i) not in used_pins:
            return str(i)
    return "1001"

# ------------------------------------------------------
# HTTP (Routes)
# ------------------------------------------------------

@app.get("/")
def home():
    return render_template("login.html")

@app.get("/baseScreen")
def base_screen_dashboard():
    return render_template("base_screen.html")

@app.route('/updates')
def updates():
    return render_template('updates_screen.html')

@app.route('/calendar')
def calendar():
    return render_template('calendar.html')

CATEGORY_NAMES = {
    'restaurants': 'מסעדות',
    'trips': 'טיולים',
    'attractions': 'אטרקציות'
}

@app.route('/ideas')
def ideas():
    return render_template('ideas.html')

@app.route('/ideas/<category_key>')
def show_category(category_key):
    category_name = CATEGORY_NAMES.get(category_key, 'רעיונות')
    return render_template('category_list.html', category_key=category_key, category_name=category_name)

@app.get("/settings")
def settings_page():
    first_group = Group.query.first()
    if first_group:
        return redirect(url_for("edit_group", group_id=first_group.id))
    flash("לא נמצאה קבוצה במערכת")
    return redirect(url_for("base_screen_dashboard"))

@app.get("/show_data")
def show_data():
    groups = Group.query.all()
    members = Member.query.all()

    html = "<h1>📋 נתונים במערכת</h1><h2>קבוצות:</h2><ul>"
    for g in groups:
        html += f"<li><b>ID:</b> {g.id} | <b>שם:</b> {g.name} | <b>קוד:</b> {getattr(g, 'pin', '—')} <a href='/delete_group/{g.id}' onclick=\"return confirm('בטוח?');\" style='color: red;'>[❌ מחק]</a></li>"
    html += "</ul><h2>משתתפים:</h2><ul>"
    for m in members:
        html += f"<li><b>ID:</b> {m.id} | <b>שם:</b> {m.name} | <b>Group ID:</b> {m.group_id} | <b>PIN:</b> {m.pin}</li>"
    html += "</ul><br><a href='/'>🔙 חזרה</a>"
    return html

@app.post("/login")
def login():
    member_pin = request.form.get("member_pin", "").strip()
    member = Member.query.filter_by(pin=member_pin).first()
    if not member:
        flash("קוד משתמש לא קיים או שגוי 💔")
        return redirect(url_for("home"))
    return redirect(url_for("base_screen_dashboard"))

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
        flash(f"נרשמת בהצלחה ל-{group.name}! 🎉")
        return redirect(url_for("home"))

    return redirect(url_for("create_group_form"))

@app.route('/delete_group/<int:group_id>', methods=['POST', 'GET'])
def delete_group(group_id):
    group = Group.query.get_or_404(group_id)
    Member.query.filter_by(group_id=group.id).delete()
    db.session.delete(group)
    db.session.commit()
    flash(f"הקבוצה '{group.name}' נמחקה בהצלחה! 🗑️")
    return redirect(url_for('show_data'))

@app.get("/group/<int:group_id>/edit")
def edit_group(group_id):
    group = Group.query.get_or_404(group_id)
    members = Member.query.filter_by(group_id=group_id).all()
    return render_template("setting.html", group=group, members=members)

# ------------------------------------------------------
# SocketIO Events
# ------------------------------------------------------

@socketio.on('add_idea')
def handle_add_idea(data):
    try:
        supabase.table('date_ideas').insert({"category": data['category'], "content": data['content']}).execute()
    except Exception as e:
        print("שגיאה בשמירת רעיון:", e)
    emit('receive_idea', data, broadcast=True)

@socketio.on('connect')
def handle_connect():
    try:
        response = supabase.table('Latest_updates').select('*').execute()
        emit('load_history', response.data)
    except Exception as e:
        print("שגיאה בטעינת עדכונים:", e)

    try:
        events_resp = supabase.table('calendar_events').select('*').execute()
        emit('load_calendar_events', events_resp.data)
    except Exception as e:
        print("שגיאה בטעינת יומן:", e)

@socketio.on('send_update')
def handle_update(data):
    try:
        supabase.table('Latest_updates').insert({"content": data['message']}).execute()
    except Exception as e:
        print("שגיאה ב-Supabase:", e)
    emit('receive_update', data, broadcast=True)

@socketio.on('add_calendar_event')
def handle_calendar_event(event_data):
    try:
        supabase.table('calendar_events').insert({"title": event_data['title'], "start": event_data['start']}).execute()
    except Exception as e:
        print("שגיאה בשמירת אירוע ביומן:", e)
    emit('receive_calendar_event', event_data, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='127.0.0.1', port=5000, debug=False)