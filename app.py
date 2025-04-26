from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import pandas as pd
from graphviz import Digraph
import uuid
import os
from datetime import datetime
import secrets

from recommendations.recommendations import suggest_jobs, suggest_courses, generate_flowchart

# Initialize the Flask app
app = Flask(__name__)

# Secure Secret Key
app.secret_key = secrets.token_hex(32)

# Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///new.db'
db = SQLAlchemy(app)

# Adzuna API credentials
app_id = "fd38abaf"
app_key = "96d2f7ae247220ba889a8ea897de2565"

# HuggingFace API Token
HF_API_TOKEN = "your_huggingface_api_token_here"  # replace with your HF token

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    profession = db.Column(db.String(100))
    age = db.Column(db.Integer)
    country = db.Column(db.String(100))

# Saved Data Model
class SavedData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    matched_jobs = db.Column(db.Text)
    roadmap_text = db.Column(db.Text)
    roadmap_img = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Home Route
@app.route('/')
def home():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))

# Register Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = request.form['username']
        pwd = generate_password_hash(request.form['password'])
        profession = request.form['profession']
        age = request.form['age']
        country = request.form['country']

        if User.query.filter_by(username=user).first():
            flash("User already exists", "error")
            return redirect(url_for('register'))

        new_user = User(username=user, password=pwd, profession=profession, age=age, country=country)
        db.session.add(new_user)
        db.session.commit()
        flash("Registered Successfully! 🎉", "success")
        return redirect(url_for('login'))
    
    return render_template('register.html')

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']
        found = User.query.filter_by(username=user).first()
        if found and check_password_hash(found.password, pwd):
            session.permanent = True
            session['user'] = user
            return redirect(url_for('dashboard'))
        flash("Invalid credentials!", "error")
    return render_template('login.html')

# Logout Route
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# Dashboard Route
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    user = User.query.filter_by(username=session['user']).first()
    data = SavedData.query.filter_by(username=session['user']).all()
    return render_template('dashboard.html', user=user, data=data)

# Match Skills Route
@app.route('/match', methods=['POST'])
def match():
    if request.content_type != 'application/json':
        return jsonify({"error": "Invalid Content-Type, expected application/json"}), 415

    try:
        data = request.get_json()
        skills = data.get('skills', '')

        if not skills:
            return jsonify({'error': 'No skills provided'}), 400

        # Fetch jobs from Adzuna
        url = f"https://api.adzuna.com/v1/api/jobs/in/search/1"
        params = {
            'app_id': app_id,
            'app_key': app_key,
            'results_per_page': 10,
            'what': skills,
            'content-type': 'application/json'
        }

        response = requests.get(url, params=params)

        if response.status_code == 200:
            full_response = response.json()
            jobs = full_response.get('results', [])

            if not jobs:
                return jsonify({'error': 'No jobs found for these skills'}), 404

            job_list = []
            for job in jobs:
                job_info = {
                    'title': job.get('title'),
                    'company': job.get('company', {}).get('display_name'),
                    'location': job.get('location', {}).get('display_name'),
                    'description': job.get('description'),
                    'url': job.get('redirect_url'),
                    'skills': job.get('description', 'No description provided')[:200] + "..."
                }
                job_list.append(job_info)

            return jsonify({'jobs': job_list}), 200
        else:
            return jsonify({'error': f'Failed to fetch jobs from Adzuna. Status code: {response.status_code}'}), 500

    except Exception as e:
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

# HuggingFace Roadmap Generation
def generate_roadmap(skills):
    url = "https://api-inference.huggingface.co/models/bigscience/bloomz-560m"
    headers = {
        "Authorization": f"Bearer {HF_API_TOKEN}",
        "Content-Type": "application/json"
    }
    prompt = f"Create a detailed learning roadmap for these skills: {', '.join(skills)}. Break into Beginner, Intermediate, Advanced, and Job-Ready stages with emojis and bullet points."
    
    payload = {
        "inputs": prompt
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        return response.json()[0]['generated_text']
    else:
        return "Could not generate roadmap at this time."

# Suggest Courses
def suggest_courses(skills):
    query = "+".join(skills)
    youtube = f"https://www.youtube.com/results?search_query={query}+course"
    coursera = f"https://www.coursera.org/search?query={query}"
    udemy = f"https://www.udemy.com/courses/search/?q={query}"
    return {"YouTube": youtube, "Coursera": coursera, "Udemy": udemy}

# Enter Skills Page
@app.route('/enter_skills', methods=['GET'])
def enter_skills():
    return render_template('enter_skills.html')

# Recommend Page (fixed fully)
@app.route('/recommend', methods=['GET', 'POST'])
def recommend():
    if 'user' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        skills = request.form['skills'].split(',')
        skills = [skill.strip() for skill in skills]

        jobs = suggest_jobs(skills)
        courses = suggest_courses(skills)
        roadmap = generate_roadmap(skills)
        flowchart = generate_flowchart(skills)

        return render_template('recommend.html', jobs=jobs, courses=courses, roadmap=roadmap, flowchart=flowchart)

    return render_template('enter_skills.html')

# Ping Test
@app.route('/ping')
def ping():
    return "Ping received"

# Run App
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
