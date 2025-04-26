import requests
import uuid
import os
from graphviz import Digraph

# Adzuna API keys
app_id = "fd38abaf"
app_key = "96d2f7ae247220ba889a8ea897de2565"

# Hugging Face API key (Replace with your own key)
HF_API_KEY = "hf_your_huggingface_api_key"

# Suggest jobs based on skills
def suggest_jobs(skills):
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
        jobs = response.json().get('results', [])
        job_list = []

        for job in jobs:
            job_info = {
                'title': job.get('title'),
                'company': job.get('company', {}).get('display_name'),
                'location': job.get('location', {}).get('display_name'),
                'description': job.get('description'),
                'url': job.get('redirect_url')
            }
            job_list.append(job_info)

        return job_list
    else:
        return []

# Suggest courses for skills
def suggest_courses(skills):
    query = "+".join(skills)
    return {
        "YouTube": f"https://www.youtube.com/results?search_query={query}+course",
        "Coursera": f"https://www.coursera.org/search?query={query}",
        "Udemy": f"https://www.udemy.com/courses/search/?q={query}"
    }

# Generate learning roadmap using Hugging Face
def generate_roadmap(skills):
    prompt = (
        f"Create a detailed roadmap to upgrade these skills: {', '.join(skills)}.\n"
        "Divide into 4 stages: Beginner, Intermediate, Advanced, Job-ready.\n"
        "Use bullet points, emojis, and short explanations."
    )

    url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 500}
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        output = response.json()
        if isinstance(output, list) and 'generated_text' in output[0]:
            return output[0]['generated_text']
        else:
            return "Roadmap generation failed. Please try again later."
    else:
        return "Roadmap generation failed due to API error."

# Generate skill flowchart
def generate_flowchart(skills):
    steps = ["Beginner", "Intermediate", "Advanced", "Job-Ready"]
    dot = Digraph()
    previous = None
    for i, step in enumerate(steps):
        label = f"{step}\nFocus: {', '.join(skills)}"
        node_id = f"step{i}_{uuid.uuid4().hex[:5]}"
        dot.node(node_id, label, shape='box', style='filled', fillcolor='lightblue')
        if previous:
            dot.edge(previous, node_id)
        previous = node_id

    filename = f"roadmap_{uuid.uuid4().hex}.png"
    path = os.path.join('static', 'roadmaps', filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    dot.render(path, format='png', cleanup=True)
    return "/" + path
