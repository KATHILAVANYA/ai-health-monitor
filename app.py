from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3, os, math
from datetime import datetime

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
DB = os.path.join(os.path.dirname(__file__), "health_monitor.db")

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
      age INTEGER, medical_history TEXT, allergies TEXT, medications TEXT
    );
    CREATE TABLE IF NOT EXISTS readings(
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
      created_at TEXT NOT NULL, temperature REAL, systolic INTEGER, diastolic INTEGER,
      heart_rate INTEGER, spo2 REAL, blood_sugar REAL, symptoms TEXT, risk TEXT, advice TEXT
    );
    CREATE TABLE IF NOT EXISTS reminders(
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
      medicine TEXT NOT NULL, schedule TEXT NOT NULL
    );
    """)
    con.commit(); con.close()

def assess(r):
    score = 0
    flags = []
    if r["temperature"] is not None and r["temperature"] >= 39: score += 2; flags.append("High temperature")
    elif r["temperature"] is not None and r["temperature"] >= 37.5: score += 1; flags.append("Elevated temperature")
    if r["spo2"] is not None and r["spo2"] < 92: score += 3; flags.append("Low SpO₂")
    elif r["spo2"] is not None and r["spo2"] < 95: score += 1; flags.append("Borderline SpO₂")
    if r["heart_rate"] is not None and (r["heart_rate"] < 50 or r["heart_rate"] > 120): score += 2; flags.append("Abnormal heart rate")
    if r["systolic"] is not None and r["diastolic"] is not None:
        if r["systolic"] >= 180 or r["diastolic"] >= 120: score += 3; flags.append("Very high blood pressure")
        elif r["systolic"] >= 140 or r["diastolic"] >= 90: score += 1; flags.append("High blood pressure")
        elif r["systolic"] < 90 or r["diastolic"] < 60: score += 1; flags.append("Low blood pressure")
    if r["blood_sugar"] is not None and r["blood_sugar"] >= 300: score += 2; flags.append("Very high blood sugar")
    risk = "High Risk" if score >= 4 else ("Moderate Risk" if score >= 2 else "Low Risk")
    advice = ("Seek prompt medical evaluation, especially if symptoms are severe or worsening."
              if risk == "High Risk" else
              "Recheck concerning values and consider medical advice if they persist."
              if risk == "Moderate Risk" else
              "Continue monitoring and maintain your usual care plan.")
    if flags: advice = "; ".join(flags) + ". " + advice
    return risk, advice

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        f=request.form
        try:
            con=db(); con.execute("""INSERT INTO users(name,email,password,age,medical_history,allergies,medications)
              VALUES(?,?,?,?,?,?,?)""",(f["name"],f["email"],f["password"],f.get("age") or None,
              f.get("medical_history",""),f.get("allergies",""),f.get("medications","")))
            con.commit(); con.close()
            flash("Registration successful. Please log in.","success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already registered.","danger")
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        con=db(); u=con.execute("SELECT * FROM users WHERE email=? AND password=?",
                                  (request.form["email"],request.form["password"])).fetchone(); con.close()
        if u:
            session["uid"]=u["id"]; session["name"]=u["name"]; return redirect(url_for("dashboard"))
        flash("Invalid email or password.","danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("index"))

@app.route("/dashboard")
def dashboard():
    if "uid" not in session: return redirect(url_for("login"))
    con=db(); rows=con.execute("SELECT * FROM readings WHERE user_id=? ORDER BY id DESC",(session["uid"],)).fetchall()
    meds=con.execute("SELECT * FROM reminders WHERE user_id=? ORDER BY id DESC",(session["uid"],)).fetchall()
    con.close()
    latest=rows[0] if rows else None
    return render_template("dashboard.html", rows=rows, meds=meds, latest=latest)

@app.route("/reading", methods=["POST"])
def reading():
    if "uid" not in session: return redirect(url_for("login"))
    def num(k, cast=float):
        x=request.form.get(k,"").strip()
        return cast(x) if x else None
    r={"temperature":num("temperature"),"systolic":num("systolic",int),
       "diastolic":num("diastolic",int),"heart_rate":num("heart_rate",int),
       "spo2":num("spo2"),"blood_sugar":num("blood_sugar"),
       "symptoms":request.form.get("symptoms","")}
    risk, advice=assess(r)
    con=db(); con.execute("""INSERT INTO readings(user_id,created_at,temperature,systolic,diastolic,heart_rate,spo2,blood_sugar,symptoms,risk,advice)
      VALUES(?,?,?,?,?,?,?,?,?,?,?)""",(session["uid"],datetime.now().strftime("%Y-%m-%d %H:%M"),
      r["temperature"],r["systolic"],r["diastolic"],r["heart_rate"],r["spo2"],r["blood_sugar"],r["symptoms"],risk,advice))
    con.commit(); con.close()
    return redirect(url_for("dashboard"))

@app.route("/reminder", methods=["POST"])
def reminder():
    if "uid" not in session: return redirect(url_for("login"))
    con=db(); con.execute("INSERT INTO reminders(user_id,medicine,schedule) VALUES(?,?,?)",
                          (session["uid"],request.form["medicine"],request.form["schedule"]))
    con.commit(); con.close(); return redirect(url_for("dashboard"))

@app.route("/chat", methods=["POST"])
def chat():
    msg=request.json.get("message","").lower()
    if any(x in msg for x in ["fever","temperature"]):
        ans="For a fever, rest and stay hydrated. Recheck your temperature. Seek medical care for severe symptoms, persistent/worsening fever, breathing difficulty, confusion, or other emergency warning signs."
    elif "spo2" in msg or "oxygen" in msg:
        ans="SpO₂ readings can vary with device and technique. Sit still, warm your finger, and recheck. Persistently low readings or breathing difficulty warrant medical attention."
    elif "blood pressure" in msg or "bp" in msg:
        ans="Rest for a few minutes and repeat the blood-pressure measurement using correct technique. Repeated high or low readings should be discussed with a healthcare professional."
    elif "medicine" in msg:
        ans="Take medicines only according to the prescribed instructions. Do not change dose or stop a prescribed medicine based only on this chatbot."
    else:
        ans="I can provide general health information and help interpret the monitoring features. I cannot diagnose conditions. For urgent or severe symptoms, contact a qualified healthcare professional or emergency service."
    return jsonify({"answer":ans})

init_db()
if __name__=="__main__":
    app.run(debug=True)
