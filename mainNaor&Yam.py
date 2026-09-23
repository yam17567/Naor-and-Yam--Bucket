import os
# from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_socketio import SocketIO, emit
from supabase import create_client, Client
from models import db, Group, Member

# פונקציית עזר למציאת הקוד הפנוי הקטן ביותר (בין 1 ל-1000)
def get_suggested_pin():
    used_pins = {m.pin for m in Member.query.all() if m.pin}
    for i in range(1, 1001):
        pin_str = str(i)
        if pin_str not in used_pins:
            return pin_str
    return "1001"

# 1. יצירת האפליקציה והגדרות בסיס
app = Flask('Naor&Yam-Bucket', template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = '050426_Love'

# הגדרות SQLite / SQLAlchemy
os.makedirs(app.instance_path, exist_ok=True)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(app.instance_path, "couple_list.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
with app.app_context():
    db.create_all()

# 2. SocketIO & Supabase
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

SUPABASE_URL = "https://hjpqmbufbzjkfetfetmx.supabase.co"
SUPABASE_KEY = "sb_publishable_B6JpVap4JAiDzziiSVE0yA_3CV6aV7T"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ------------------------------------------------------
# 🌸 נתיבי HTTP (Routes)
# ------------------------------------------------------

@app.get("/")
def home():
    return render_template("login.html")

def base_screen():
    return render_template("login.html")

# דף הבית המרכזי
@app.get("/baseScreen")
def base_screen_dashboard():
    return render_template("base_screen.html")

# דף העדכונים בזמן אמת
@app.route('/updates')
def updates():
    return render_template('updates_screen.html')
# דף היומן המשותף
@app.route('/calendar')
def calendar():
    return render_template('calendar.html')
# תרגום מפתח קטגוריה לשם מוצג בעברית
CATEGORY_NAMES = {
    'restaurants': 'מסעדות',
    'trips': 'טיולים',
    'attractions': 'אטרקציות'
}
# דף הרעיונות הראשי
@app.route('/ideas')
def ideas():
    return render_template('ideas.html')
# דף דינמי לקטגוריה ספציפית
@app.route('/ideas/<category_key>')
def show_category(category_key):
    category_name = CATEGORY_NAMES.get(category_key, 'רעיונות')
    return render_template('category_list.html', category_key=category_key, category_name=category_name)

@socketio.on('add_idea')
def handle_add_idea(data):
    try:
        # שמירה בטבלה ב-Supabase (צריך ליצור טבלה בשם 'date_ideas')
        supabase.table('date_ideas').insert({
            "category": data['category'],
            "content": data['content']
        }).execute()
    except Exception as e:
        print("שגיאה בשמירת רעיון:", e)

    # הפצה בזמן אמת לכל המשתמשים
    emit('receive_idea', data, broadcast=True)

# תצוגת נתונים לבדיקה + כפתורי מחיקה
@app.get("/show_data")
def show_data():
    groups = Group.query.all()
    members = Member.query.all()

    html = "<h1>📋 נתונים במערכת</h1>"
    html += "<h2>קבוצות:</h2><ul>"
    for g in groups:
        html += f"""
        <li>
            <b>ID:</b> {g.id} | <b>שם:</b> {g.name} | <b>קוד:</b> {getattr(g, 'pin', '—')} 
            <a href='/delete_group/{g.id}' onclick="return confirm('בטוח שברצונך למחוק את הקבוצה?');" style="color: red; margin-right: 10px;">[❌ מחק קבוצה]</a>
        </li>
        """
    html += "</ul><h2>משתתפים:</h2><ul>"
    for m in members:
        html += f"<li><b>ID:</b> {m.id} | <b>שם:</b> {m.name} | <b>Group ID:</b> {m.group_id}</li>"
    html += "</ul><br><a href='/'>🔙 חזרה לדף הראשי</a>"
    return html

# התחברות לפי קוד קבוצה + קוד משתמש
@app.post("/login")
def login():
    member_pin = request.form.get("member_pin", "").strip()
    # חיפוש המשתמש לפי הקוד האישי הייחודי שלו
    member = Member.query.filter_by(pin=member_pin).first()
    if not member:
        flash("קוד משתמש לא קיים או שגוי 💔")
        return redirect(url_for("home"))
    # שמירת המשתתף והקבוצה בסשן/העברה לדף הבית
    return redirect(url_for("base_screen_dashboard"))
    # מעבר לעמוד הבית הראשי לאחר התחברות בהצלחה!
    return redirect(url_for("base_screen_dashboard"))

# ------------------------------------------------------
# 🌸 יצירת קבוצה והתחברות (עם שמירה קבועה ב-SQLite)
# ------------------------------------------------------

# טופס יצירת קבוצה חדשה (GET)
@app.get("/create_group")
def create_group_form():
    suggested_pin = get_suggested_pin()
    return render_template("sign_up.html", suggested_pin=suggested_pin)


# 3. קליטת קבוצה ומשתמשים עם בדיקת קודים תפוסים
@app.post("/create_group")
def create_group():
    group_name = request.form.get("group_name", "").strip()

    # איסוף השמות והקודים שהוזנו בטופס
    member_names = request.form.getlist("member_name")
    member_pins = request.form.getlist("member_pin")

    # בדיקת תקינות: האם אחד הקודים שהוזנו כבר תפוס במערכת?
    existing_pins = {m.pin for m in Member.query.all() if m.pin}
    requested_pins = [p.strip() for p in member_pins if p.strip()]

    # בדיקה אם יש כפילות בתוך הטופס עצמו
    if len(requested_pins) != len(set(requested_pins)):
        flash("אי אפשר לבחור את אותו קוד עבור שני משתתפים בטופס 💔")
        return redirect(url_for("create_group_form"))

    # בדיקה אם קוד כבר תפוס במסד הנתונים
    for pin in requested_pins:
        if pin in existing_pins:
            flash(f"הקוד {pin} כבר תפוס במערכת! אנא בחרו קוד אחר 💔")
            return redirect(url_for("create_group_form"))

    # יצירת הקבוצה
    new_group = Group(name=group_name, pin=str(Group.query.count() + 1001))
    db.session.add(new_group)
    db.session.commit()

    # שמירת המשתתפים עם הקודים המותאמים אישית שלהם
    created_summary = []
    for name, pin in zip(member_names, member_pins):
        if name.strip() and pin.strip():
            m = Member(name=name.strip(), pin=pin.strip(), group_id=new_group.id)
            db.session.add(m)
            created_summary.append(f"{name.strip()} (קוד: {pin.strip()})")

    db.session.commit()

    flash(f"הקבוצה '{group_name}' נוצרה בהצלחה! 🎉\nפרטי התחברות:\n" + "\n".join(created_summary))
    return redirect(url_for("home"))

# ------------------------------------------------------
# 🗑️ מחיקת קבוצה
# ------------------------------------------------------
@app.route('/delete_group/<int:group_id>', methods=['POST', 'GET'])
def delete_group(group_id):
    group = Group.query.get_or_404(group_id)
    # 1. מחיקת כל המשתתפים של הקבוצה
    Member.query.filter_by(group_id=group.id).delete()
    # 2. מחיקת הקבוצה עצמה
    db.session.delete(group)
    db.session.commit()
    flash(f"הקבוצה '{group.name}' נמחקה בהצלחה! 🗑️")
    return redirect(url_for('show_data'))  # מנתב חזרה לעמוד התצוגה

# עמוד עריכת קבוצה
@app.get("/group/<int:group_id>/edit")
def edit_group(group_id):
    group = Group.query.get_or_404(group_id)
    members = Member.query.filter_by(group_id=group_id).all()
    return render_template("setting.html", group=group, members=members)


# ------------------------------------------------------
# ⚡ אירועי SocketIO (זמן אמת)
# ------------------------------------------------------

@socketio.on('connect')
def handle_connect():
    print('User connected')
    # טעינת עדכונים
    try:
        response = supabase.table('Latest_updates').select('*').execute()
        emit('load_history', response.data)
    except Exception as e:
        print("שגיאה בטעינת עדכונים:", e)

    # טעינת אירועי יומן
    try:
        events_resp = supabase.table('calendar_events').select('*').execute()
        emit('load_calendar_events', events_resp.data)
    except Exception as e:
        print("שגיאה בטעינת יומן:", e)

@socketio.on('send_update')
def handle_update(data):
    print('There a new update!:', data)
    try:
        supabase.table('Latest_updates').insert({"content": data['message']}).execute()
    except Exception as e:
        print("SOMETHING WRONG-Supabase:", e)

    emit('receive_update', data, broadcast=True)

@socketio.on('add_calendar_event')
def handle_calendar_event(event_data):
    try:
        supabase.table('calendar_events').insert({
            "title": event_data['title'],
            "start": event_data['start']
        }).execute()
    except Exception as e:
        print("שגיאה בשמירת אירוע ביומן:", e)

    emit('receive_calendar_event', event_data, broadcast=True)


# ------------------------------------------------------
# 🚀 הרצת השרת
# ------------------------------------------------------
if __name__ == '__main__':
    socketio.run(app, host='127.0.0.1', port=5000, debug=False)