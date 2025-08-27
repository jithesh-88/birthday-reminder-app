import os
import requests
import google.generativeai as genai
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from sqlalchemy import extract
from dotenv import load_dotenv
from flask_migrate import Migrate # Add this import

load_dotenv()

# --- App and Database Setup ---
app = Flask(__name__)
app.secret_key = "a-very-secret-key-for-production"
# Use DATABASE_URL from environment if available (for Render), otherwise use local SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///birthdays_users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db) # Add this line to initialize migrations
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'welcome'

# --- Gemini API Configuration ---
try:
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    print(f"Could not configure Gemini API. Fun facts will be disabled. Error: {e}")
    model = None

# --- Admin Configuration ---
ADMIN_EMAIL = "jithesh882006@gmail.com"

# --- Database Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    birthdays = db.relationship('Birthday', backref='creator', lazy=True)

class Birthday(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    dob = db.Column(db.Date, nullable=False)
    tob = db.Column(db.String(50), nullable=True)
    pob = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- Helper Functions ---
def get_coords(place_name):
    if not place_name: return None, None
    url = f"https://nominatim.openstreetmap.org/search"; params = {'q': place_name, 'format': 'json', 'limit': 1}; headers = {'User-Agent': 'BirthdayReminderApp/1.0'}
    try:
        response = requests.get(url, params=params, headers=headers); response.raise_for_status(); data = response.json()
        if data: return float(data[0]['lat']), float(data[0]['lon'])
    except requests.RequestException as e: print(f"Geocoding error: {e}"); return None, None

def calculate_birthday_details(birthday, today):
    age = today.year - birthday.dob.year - ((today.month, today.day) < (birthday.dob.month, birthday.dob.day))
    birthday_this_year = birthday.dob.replace(year=today.year)
    if birthday_this_year < today: next_birthday_date = birthday_this_year.replace(year=today.year + 1)
    else: next_birthday_date = birthday_this_year
    age_turning = next_birthday_date.year - birthday.dob.year
    days_left = (next_birthday_date - today).days
    return days_left, age_turning

def generate_gemini_fun_facts(dob, tob, pob):
    if not model or not tob:
        return ["Provide a time of birth to generate fun facts!"]
    try:
        prompt = f"""
        You are a creative and cheerful fun facts generator for a birthday app. Your main goal is to generate facts based on the **time of birth**, using the date and location as context.
        Generate exactly 3 diverse and interesting fun facts for someone born at {tob} on {dob.strftime('%B %d, %Y')} in {pob}.
        Fact Types to Generate (choose three different types):
        1. A "World Clock" Fact: What was happening in another major city in a different time zone at that exact moment?
        2. A "Sun or Moon" Fact: Describe the position of the sun or moon in their birth city.
        3. A "#1 Song" Fact: What song was #1 on the Billboard charts on that day?
        4. A "Historical Nugget": What minor but interesting historical event happened on that day?
        5. A "Scientific Discovery": Mention a scientific discovery or event related to that year.
        RULES:
        - Output ONLY the facts. No titles, no quotes, no extra text.
        - Separate each fact with a double pipe delimiter (||).
        - The facts must be cheerful and non-astrological.
        """
        response = model.generate_content(prompt)
        if response.text:
            facts = [fact.strip() for fact in response.text.strip().split('||') if fact.strip()]
            return facts
        return ["Could not generate fun facts at this time."]
    except Exception as e:
        print(f"Gemini API call failed: {e}")
        return ["Could not generate fun facts at this time."]

# --- New Welcome Route ---
@app.route('/welcome')
def welcome():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('welcome.html')

# --- Authentication Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user); return redirect(url_for('index'))
        else:
            flash('Login failed. Check your email and password.', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        if User.query.filter_by(email=request.form['email']).first():
            flash('This email is already registered.', 'error'); return redirect(url_for('register'))
        hashed_password = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
        new_user = User(email=request.form['email'], password=hashed_password)
        db.session.add(new_user); db.session.commit()
        login_user(new_user); return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user(); return redirect(url_for('welcome'))

# --- Main Application Routes ---
@app.route('/')
@login_required
def index():
    today = date.today()
    birthdays = Birthday.query.order_by(extract('month', Birthday.dob), extract('day', Birthday.dob)).all()
    birthdays_with_details = [{'birthday': b, 'days_left': d, 'age_turning': a} for d, a, b in [(*calculate_birthday_details(b, today), b) for b in birthdays]]
    sorted_birthdays = sorted(birthdays_with_details, key=lambda x: x['days_left'])
    upcoming_birthdays = []
    if sorted_birthdays:
        min_days_left = sorted_birthdays[0]['days_left']
        upcoming_birthdays = [b for b in sorted_birthdays if b['days_left'] == min_days_left]
    birthdays_json = [{'name': b['birthday'].name, 'lat': b['birthday'].latitude, 'lon': b['birthday'].longitude, 'pob': b['birthday'].pob} for b in sorted_birthdays if b['birthday'].latitude is not None]
    return render_template('index.html', sorted_birthdays=sorted_birthdays, upcoming_birthdays=upcoming_birthdays, birthdays_json=birthdays_json)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_birthday():
    if request.method == 'POST':
        if current_user.email != ADMIN_EMAIL:
            existing_birthday = Birthday.query.filter_by(user_id=current_user.id).first()
            if existing_birthday:
                flash("You can only add one birthday to the board per account.", "error")
                return redirect(url_for('index'))
        pob = request.form['pob']; lat, lon = get_coords(pob)
        new_birthday = Birthday(name=request.form['name'], dob=datetime.strptime(request.form['dob'], '%Y-%m-%d').date(), tob=request.form['tob'], pob=pob, notes=request.form['notes'], latitude=lat, longitude=lon, user_id=current_user.id)
        db.session.add(new_birthday); db.session.commit()
        flash(f"🎉 Birthday for {new_birthday.name} added!", "success")
        return redirect(url_for('index'))
    return render_template('add_birthday.html')

@app.route('/fun-facts/<int:id>')
@login_required
def fun_facts(id):
    birthday = Birthday.query.get_or_404(id)
    if birthday.creator != current_user and current_user.email != ADMIN_EMAIL:
        flash("You can only view fun facts for birthdays you have added.", "error")
        return redirect(url_for('index'))
    facts = generate_gemini_fun_facts(birthday.dob, birthday.tob, birthday.pob)
    return render_template('fun_facts.html', birthday=birthday, fun_facts=facts)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    birthday_to_edit = Birthday.query.get_or_404(id)
    if birthday_to_edit.creator != current_user and current_user.email != ADMIN_EMAIL:
        flash("You can only edit birthdays that you have added.", "error")
        return redirect(url_for('index'))
    if request.method == 'POST':
        birthday_to_edit.name = request.form['name']; birthday_to_edit.dob = datetime.strptime(request.form['dob'], '%Y-%m-%d').date()
        birthday_to_edit.tob = request.form['tob']; birthday_to_edit.pob = request.form['pob']; birthday_to_edit.notes = request.form['notes']
        lat, lon = get_coords(request.form['pob']); birthday_to_edit.latitude = lat; birthday_to_edit.longitude = lon
        db.session.commit()
        flash(f"✅ Updated {birthday_to_edit.name}'s birthday!", "success")
        return redirect(url_for('index'))
    return render_template('edit.html', birthday=birthday_to_edit)

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    birthday_to_delete = Birthday.query.get_or_404(id)
    if birthday_to_delete.creator != current_user and current_user.email != ADMIN_EMAIL:
        flash("You can only delete birthdays that you have added.", "error")
        return redirect(url_for('index'))
    db.session.delete(birthday_to_delete); db.session.commit()
    flash(f"🗑️ Deleted {birthday_to_delete.name}'s birthday", "success")
    return redirect(url_for('index'))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    print("🎂 Birthday Reminder running on http://127.0.0.1:5000")
    app.run(debug=True)