# Smart PlaceTrack – Placement Tracker

A lightweight full-stack web app that helps students track campus placement applications, stages, deadlines and offers.

## Objective
Keep every application (company, role, package, deadline, stage) in one place and show a clear summary of placement progress.

## Features
- Register / login with hashed passwords (Werkzeug)
- Add, update stage, search, filter and delete applications
- Dashboard: total applications, shortlisted/interview count, offer rate, next deadline, stage chart
- Server-side and client-side validation; data stored per user in SQLite

## Technologies
HTML5, CSS3, JavaScript (fetch API, canvas chart) · Python + Flask · SQLite · Werkzeug

## Run locally
```bash
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000, create an account and start adding applications.

## Repository structure
```
app.py            Flask backend, REST routes, SQLite schema
static/index.html Frontend (HTML, CSS, JavaScript)
requirements.txt  Python dependency
screenshots/      Output screenshots
```

## Output
| Login | Dashboard | History |
|---|---|---|
| ![](screenshots/01_login.png) | ![](screenshots/02_dashboard.png) | ![](screenshots/03_history_filtered.png) |
