from flask import Flask, render_template, request, redirect, session, make_response, jsonify
import os
from datetime import datetime
import sqlite3
import json
import csv
from io import StringIO, BytesIO
import re
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from utils.detector import process_image
from utils.db import init_db
from utils.notifier import notify_high_severity

app = Flask(__name__)
app.secret_key = "secret123"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "static", "outputs")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
app.config["PI_API_TOKEN"] = os.getenv("PI_API_TOKEN", "changeme-token")
app.config["FRONTEND_ORIGIN"] = os.getenv("FRONTEND_ORIGIN", "*")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

# Ensure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

init_db()


def get_db():
    return sqlite3.connect(os.path.join(BASE_DIR, "database.db"))


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_ts(ts):
    if not ts:
        return "-"
    return datetime.strptime(ts, "%Y%m%d_%H%M%S").strftime("%d %b %Y, %I:%M %p")


def parse_coordinates(raw_location):
    if not raw_location:
        return None, None
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)", raw_location)
    if not match:
        return None, None
    lat = float(match.group(1))
    lon = float(match.group(2))
    if lat < -90 or lat > 90 or lon < -180 or lon > 180:
        return None, None
    return lat, lon


def to_map_url(raw_location):
    lat, lon = parse_coordinates(raw_location)
    if lat is None:
        return None
    return f"https://www.google.com/maps?q={lat},{lon}"


def can_manage_users():
    return session.get("role") == "admin"


@app.route("/", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, username, password, role FROM users WHERE username=?", (username,))
        user = c.fetchone()
        conn.close()

        if user and (check_password_hash(user[2], password) or user[2] == password):
            session["user"] = username
            session["role"] = user[3] or "inspector"
            return redirect("/dashboard")
        error = "Invalid username or password."

    return render_template("login.html", error=error)


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")

    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip().upper()
    severity = request.args.get("severity", "").strip().upper()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()

    conn = get_db()
    c = conn.cursor()
    query = """
        SELECT id, image, output, severity, status, created_at, completed_at, completed_by, location, description
        FROM complaints
        WHERE 1=1
    """
    params = []
    if search:
        query += " AND (COALESCE(location, '') LIKE ? OR COALESCE(description, '') LIKE ?)"
        key = f"%{search}%"
        params.extend([key, key])
    if status in {"OPEN", "COMPLETED"}:
        query += " AND status = ?"
        params.append(status)
    if severity in {"LOW", "MEDIUM", "HIGH"}:
        query += " AND severity = ?"
        params.append(severity)
    if start_date:
        query += " AND created_at >= ?"
        params.append(start_date.replace("-", "") + "_000000")
    if end_date:
        query += " AND created_at <= ?"
        params.append(end_date.replace("-", "") + "_235959")

    query += " ORDER BY id DESC"
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()

    data = []
    for row in rows:
        created = datetime.strptime(row[5], "%Y%m%d_%H%M%S").strftime("%d %b %Y, %I:%M %p")
        completed = "-"
        if row[6]:
            completed = datetime.strptime(row[6], "%Y%m%d_%H%M%S").strftime("%d %b %Y, %I:%M %p")
        data.append(
            {
                "id": row[0],
                "image": row[1],
                "output": row[2],
                "severity": row[3],
                "status": row[4],
                "created_at": created,
                "completed_at": completed,
                "completed_by": row[7] or "-",
                "location": row[8] or "-",
                "map_url": to_map_url(row[8] or ""),
                "description": row[9] or "-",
            }
        )

    open_count = sum(1 for item in data if item["status"] == "OPEN")
    completed_count = sum(1 for item in data if item["status"] == "COMPLETED")
    severity_counts = {
        "LOW": sum(1 for item in data if item["severity"] == "LOW"),
        "MEDIUM": sum(1 for item in data if item["severity"] == "MEDIUM"),
        "HIGH": sum(1 for item in data if item["severity"] == "HIGH"),
    }
    can_complete = session.get("role") in {"admin", "supervisor"}
    return render_template(
        "dashboard.html",
        data=data,
        open_count=open_count,
        completed_count=completed_count,
        severity_counts_json=json.dumps(severity_counts),
        filters={
            "search": search,
            "status": status,
            "severity": severity,
            "start_date": start_date,
            "end_date": end_date,
        },
        can_complete=can_complete,
    )


@app.route("/history")
def history():
    if "user" not in session:
        return redirect("/")

    conn = get_db()
    c = conn.cursor()
    c.execute(
        """
        SELECT id, severity, status, location, description, created_at, completed_at, completed_by, output
        FROM complaints
        WHERE status='COMPLETED'
        ORDER BY completed_at DESC
        """
    )
    rows = c.fetchall()
    conn.close()

    data = [
        {
            "id": row[0],
            "severity": row[1],
            "status": row[2],
            "location": row[3] or "-",
            "map_url": to_map_url(row[3] or ""),
            "description": row[4] or "-",
            "created_at": parse_ts(row[5]),
            "completed_at": parse_ts(row[6]),
            "completed_by": row[7] or "-",
            "output": row[8],
        }
        for row in rows
    ]
    return render_template("history.html", data=data)


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = app.config["FRONTEND_ORIGIN"]
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Token"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.route("/history/export/csv")
def export_history_csv():
    if "user" not in session:
        return redirect("/")

    conn = get_db()
    c = conn.cursor()
    c.execute(
        """
        SELECT id, severity, location, description, created_at, completed_at, completed_by
        FROM complaints
        WHERE status='COMPLETED'
        ORDER BY completed_at DESC
        """
    )
    rows = c.fetchall()
    conn.close()

    stream = StringIO()
    writer = csv.writer(stream)
    writer.writerow(["ID", "Severity", "Location", "Description", "Created At", "Completed At", "Completed By"])
    for row in rows:
        writer.writerow(
            [
                row[0],
                row[1],
                row[2] or "-",
                row[3] or "-",
                parse_ts(row[4]),
                parse_ts(row[5]),
                row[6] or "-",
            ]
        )

    response = make_response(stream.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=completed_history.csv"
    response.headers["Content-Type"] = "text/csv"
    return response


@app.route("/history/export/pdf")
def export_history_pdf():
    if "user" not in session:
        return redirect("/")

    conn = get_db()
    c = conn.cursor()
    c.execute(
        """
        SELECT id, severity, location, completed_at, completed_by
        FROM complaints
        WHERE status='COMPLETED'
        ORDER BY completed_at DESC
        """
    )
    rows = c.fetchall()
    conn.close()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, "CrackCare Completed Complaints Report")
    y -= 25
    pdf.setFont("Helvetica", 10)
    for row in rows:
        line = f"#{row[0]} | {row[1]} | {row[2] or '-'} | {parse_ts(row[3])} | By: {row[4] or '-'}"
        pdf.drawString(50, y, line[:110])
        y -= 16
        if y < 50:
            pdf.showPage()
            y = 800
            pdf.setFont("Helvetica", 10)
    pdf.save()
    buffer.seek(0)

    response = make_response(buffer.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=completed_history.pdf"
    response.headers["Content-Type"] = "application/pdf"
    return response


@app.route("/users", methods=["GET", "POST"])
def users():
    if "user" not in session:
        return redirect("/")
    if not can_manage_users():
        return redirect("/dashboard")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "inspector").strip().lower()
        if username and password and role in {"admin", "supervisor", "inspector"}:
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT id FROM users WHERE username=?", (username,))
            existing = c.fetchone()
            if existing:
                c.execute(
                    "UPDATE users SET password=?, role=? WHERE id=?",
                    (generate_password_hash(password), role, existing[0]),
                )
            else:
                c.execute(
                    "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                    (username, generate_password_hash(password), role),
                )
            conn.commit()
            conn.close()
        return redirect("/users")

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, username, role FROM users ORDER BY username ASC")
    all_users = c.fetchall()
    conn.close()
    return render_template("users.html", all_users=all_users)


@app.route("/upload", methods=["POST"])
def upload():
    if "user" not in session:
        return redirect("/")

    location = request.form.get("location", "").strip()
    description = request.form.get("description", "").strip()

    file = request.files["image"]

    if file and allowed_file(file.filename):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = secure_filename(file.filename).rsplit(".", 1)[1].lower()
        filename = f"{timestamp}.{ext}"

        upload_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        output_path = os.path.join(app.config["OUTPUT_FOLDER"], filename)

        file.save(upload_path)

        severity = process_image(upload_path, output_path)

        conn = get_db()
        c = conn.cursor()

        c.execute(
            """
            INSERT INTO complaints
            (image, output, severity, status, created_at, completed_at, completed_by, location, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (filename, filename, severity, "OPEN", timestamp, None, None, location, description),
        )
        complaint_id = c.lastrowid

        conn.commit()
        conn.close()
        notify_high_severity(
            os.path.join(BASE_DIR, "database.db"),
            complaint_id,
            severity,
            location,
        )

    return redirect("/dashboard")


@app.route("/api/pi-capture", methods=["POST", "OPTIONS"])
def api_pi_capture():
    if request.method == "OPTIONS":
        return ("", 204)

    token = request.headers.get("X-API-Token", "").strip()
    if token != app.config["PI_API_TOKEN"]:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    image_file = request.files.get("image")
    if not image_file or not allowed_file(image_file.filename):
        return jsonify({"ok": False, "error": "Valid image is required"}), 400

    ir_triggered_raw = str(request.form.get("ir_triggered", "true")).strip().lower()
    ir_triggered = ir_triggered_raw in {"1", "true", "yes", "on"}
    if not ir_triggered:
        return jsonify({"ok": True, "status": "ignored", "reason": "IR not triggered"}), 200

    lat = request.form.get("latitude", "").strip()
    lon = request.form.get("longitude", "").strip()
    location_text = request.form.get("location", "").strip()
    if lat and lon:
        location = f"{lat},{lon}"
    elif location_text:
        location = location_text
    else:
        location = "Unknown"

    description = request.form.get("description", "IR triggered auto-capture").strip()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = secure_filename(image_file.filename).rsplit(".", 1)[1].lower()
    filename = f"{timestamp}.{ext}"

    upload_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    output_path = os.path.join(app.config["OUTPUT_FOLDER"], filename)
    image_file.save(upload_path)

    severity = process_image(upload_path, output_path)

    conn = get_db()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO complaints
        (image, output, severity, status, created_at, completed_at, completed_by, location, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (filename, filename, severity, "OPEN", timestamp, None, None, location, description),
    )
    complaint_id = c.lastrowid
    conn.commit()
    conn.close()

    notify_high_severity(
        os.path.join(BASE_DIR, "database.db"),
        complaint_id,
        severity,
        location,
    )
    return jsonify(
        {
            "ok": True,
            "complaint_id": complaint_id,
            "severity": severity,
            "location": location,
            "map_url": to_map_url(location),
        }
    )


@app.route("/complete/<int:id>")
def complete(id):
    if session.get("role") not in {"admin", "supervisor"}:
        return redirect("/dashboard")

    if "user" not in session:
        return redirect("/")

    conn = get_db()
    c = conn.cursor()

    completed_time = datetime.now().strftime("%Y%m%d_%H%M%S")

    c.execute(
        """
        UPDATE complaints
        SET status='COMPLETED', completed_at=?, completed_by=?
        WHERE id=? AND status='OPEN'
        """,
        (completed_time, session["user"], id),
    )

    conn.commit()
    conn.close()

    return redirect("/dashboard")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)