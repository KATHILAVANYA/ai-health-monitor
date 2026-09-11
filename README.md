# AI Health Monitor

## Run locally
1. Install Python 3.10+.
2. Open terminal in this folder.
3. `python -m venv venv`
4. Activate the environment.
5. `pip install -r requirements.txt`
6. `python app.py`
7. Open `http://127.0.0.1:5000`.

This prototype uses SQLite so it runs immediately. The scoring layer is a transparent screening heuristic and is **not a medical diagnosis**. For a production project, replace password storage with secure password hashing, use MySQL, add CSRF protection, authorization/doctor roles, audit logs, encryption, and a validated ML model.
