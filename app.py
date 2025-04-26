from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import openai, pandas as pd
from graphviz import Digraph
import uuid
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)

openai.api_key = "YOUR_OPENAI_API_KEY"

# User model (MISSING in original)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))

class SavedData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))  # foreign key reference
    matched_jobs = db.Column(db.Text)
    roadmap_text = db.Column(db.Text)
    roadmap_img = db.Column(db.String(300))

@app.route('/')
def home():
    if 'user' in session:
        return render_template('index.html', username=session['user'])
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = request.form['username']
        pwd = generate_password_hash(request.form['password'])
        if User.query.filter_by(username=user).first():
            flash("User already exists")
            return redirect(url_for('register'))
        db.session.add(User(username=user, password=pwd))
        db.session.commit()
        flash("Registered!")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']
        found = User.query.filter_by(username=user).first()
        if found and check_password_hash(found.password, pwd):
            session['user'] = user
            return redirect(url_for('home'))
        flash("Invalid creds!")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/match', methods=['POST'])
def match():
    skills = request.form.get('skills', '').lower().split(',')
    jobs = pd.read_csv('jobs.csv')
    matched = []

    for _, row in jobs.iterrows():
        required = row['required_skills'].lower().split(',')
        if all(skill.strip() in skills for skill in required):
            matched.append(row['job_title'])

    if matched:
        # Save to DB
        saved = SavedData(
            username=session['user'],
            matched_jobs=",".join(matched),
            roadmap_text="",
            roadmap_img=""
        )
        db.session.add(saved)
        db.session.commit()
        return render_template('result.html', jobs=matched)
    else:
        # If no jobs matched → get missing skills
        missing = set()
        for _, row in jobs.iterrows():
            required = row['required_skills'].lower().split(',')
            missing.update(set(required) - set(skills))

        roadmap = generate_roadmap(missing)
        courses = suggest_courses(missing)
        roadmap_img = generate_flowchart_from_skills(missing)

        # Save to DB
        saved = SavedData(
            username=session['user'],
            matched_jobs="",
            roadmap_text=roadmap,
            roadmap_img=roadmap_img
        )
        db.session.add(saved)
        db.session.commit()

        return render_template('result.html', roadmap=roadmap, courses=courses, roadmap_img=roadmap_img)

def generate_roadmap(missing_skills):
    prompt = (
        f"Create a roadmap to learn the following skills: {', '.join(missing_skills)}.\n"
        "Break it into 4 stages: Beginner, Intermediate, Advanced, Job-ready.\n"
        "Use markdown with bullets and emojis to make it engaging. Return only the content."
    )
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response['choices'][0]['message']['content']




def suggest_courses(skills):
    query = "+".join(skills)
    youtube = f"https://www.youtube.com/results?search_query={query}+course"
    coursera = f"https://www.coursera.org/search?query={query}"
    udemy = f"https://www.udemy.com/courses/search/?q={query}"
    return {"YouTube": youtube, "Coursera": coursera, "Udemy": udemy}

def generate_flowchart_from_skills(skills):
    steps = ["Beginner", "Intermediate", "Advanced", "Job-Ready"]
    dot = Digraph()
    previous = None
    for i, step in enumerate(steps):
        label = f"{step}\nLearn: {', '.join(skills)}"
        node_id = f"step{i}_{uuid.uuid4().hex[:5]}"
        dot.node(node_id, label, shape='box', style='filled', fillcolor='lightblue')
        if previous:
            dot.edge(previous, node_id)
        previous = node_id

    path = f"static/roadmaps/roadmap_{uuid.uuid4().hex}.png"
    dot.render(path, format='png', cleanup=True)
    return "/" + path

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    data = SavedData.query.filter_by(username=session['user']).all()
    return render_template('dashboard.html', data=data)
@app.route('/ping')
def ping():
    return "Ping received"



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

