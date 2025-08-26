from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import os

# Flask app setup
app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///birthdays.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Database setup
db = SQLAlchemy(app)

class Birthday(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    dob = db.Column(db.Date, nullable=False)
    tob = db.Column(db.String(50), nullable=True)
    pob = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<Birthday {self.name}>'

def calculate_birthday_details(birthday, today):
    """Helper function to calculate days left, age, etc."""
    age = today.year - birthday.dob.year - ((today.month, today.day) < (birthday.dob.month, birthday.dob.day))
    
    birthday_this_year = birthday.dob.replace(year=today.year)
    if birthday_this_year < today:
        next_birthday_date = birthday.dob.replace(year=today.year + 1)
        age_turning = age + 1
    else:
        next_birthday_date = birthday_this_year
        age_turning = age if (birthday.dob.month, birthday.dob.day) == (today.month, today.day) else age + 1

    days_left = (next_birthday_date - today).days
    return days_left, age_turning

@app.route('/', methods=['GET','POST'])
def index():
    if request.method == 'POST':
        try:
            name = request.form['name']
            dob_str = request.form['dob']
            tob = request.form['tob']
            pob = request.form['pob']
            notes = request.form['notes']
            dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
            
            new_birthday = Birthday(name=name, dob=dob, tob=tob, pob=pob, notes=notes)
            db.session.add(new_birthday)
            db.session.commit()
            flash(f"🎉 Birthday for {name} added!", "success")
        except ValueError:
            flash("⚠️ Invalid date format. Use YYYY-MM-DD.", "error")
        return redirect(url_for('index'))

    today = date.today()
    birthdays = Birthday.query.all()
    
    birthdays_with_details = []
    for b in birthdays:
        days_left, age_turning = calculate_birthday_details(b, today)
        birthdays_with_details.append((b, days_left, age_turning))
        
    sorted_birthdays = sorted(birthdays_with_details, key=lambda x: x[1])
    
    # **BUG FIX:** Find all birthdays with the minimum days_left
    upcoming_birthdays = []
    if sorted_birthdays:
        min_days_left = sorted_birthdays[0][1]
        upcoming_birthdays = [b for b in sorted_birthdays if b[1] == min_days_left]

    return render_template('index.html', 
                           sorted_birthdays=sorted_birthdays, 
                           upcoming_birthdays=upcoming_birthdays)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    birthday_to_edit = Birthday.query.get_or_404(id)
    if request.method == 'POST':
        try:
            birthday_to_edit.name = request.form['name']
            birthday_to_edit.dob = datetime.strptime(request.form['dob'], '%Y-%m-%d').date()
            birthday_to_edit.tob = request.form['tob']
            birthday_to_edit.pob = request.form['pob']
            birthday_to_edit.notes = request.form['notes']
            db.session.commit()
            flash(f"✅ Updated {birthday_to_edit.name}'s birthday!", "success")
            return redirect(url_for('index'))
        except:
            flash("⚠️ Problem updating the birthday.", "error")
            return redirect(url_for('edit', id=id))
    else:
        return render_template('edit.html', birthday=birthday_to_edit)


@app.route('/delete/<int:id>')
def delete(id):
    birthday_to_delete = Birthday.query.get_or_404(id)
    try:
        db.session.delete(birthday_to_delete)
        db.session.commit()
        flash(f"🗑️ Deleted {birthday_to_delete.name}'s birthday", "success")
    except:
        flash("⚠️ Problem deleting the birthday", "error")
    return redirect(url_for('index'))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    os.system("pip install -q flask flask_sqlalchemy") 
    print("🎂 Birthday Reminder running on http://127.0.0.1:5000")
    app.run(debug=True)