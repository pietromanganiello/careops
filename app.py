from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

CATEGORY_MAP = {
    "Medication": [
        "missed dose",
        "wrong dose",
        "prescribing error",
        "delayed supply",
        "administration error"
    ],
    "Skin / wound": [
        "skin tear",
        "pressure sore",
        "bruise",
        "wound deterioration"
    ],
    "Falls": [
        "unwitnessed fall",
        "fall from chair / bed",
        "fall from height"
    ],
    "Patient flow delay": [
        "awaiting package of care",
        "awaiting nursing bed",
        "awaiting off-island transfer",
        "awaiting social review"
    ]
}

STATUS_OPTIONS = ["Open", "In review", "Closed", "Duplicated"]

def get_db_connection():
    conn = sqlite3.connect("incidents.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def is_admin():
    return session.get("is_admin", False)

@app.route("/", methods=["GET", "POST"])
def home():
    demo_message = None

    if request.method == "POST":
        if not is_admin():
            demo_message = "Demo mode only. Public submissions are disabled."
            return render_template(
                "index.html",
                category_map=CATEGORY_MAP,
                is_admin=is_admin(),
                demo_message=demo_message
            )

        patient_name = request.form.get("patient_name")
        category = request.form.get("category")
        subcategory = request.form.get("subcategory")
        description = request.form.get("description")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO incidents (
                patient_name,
                category,
                subcategory,
                description,
                status,
                created_at,
                updated_at,
                archived
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            patient_name,
            category,
            subcategory,
            description,
            "Open",
            now,
            now,
            0
        ))
        conn.commit()
        conn.close()

        return redirect("/incidents")

    return render_template(
        "index.html",
        category_map=CATEGORY_MAP,
        is_admin=is_admin(),
        demo_message=demo_message
    )

@app.route("/incidents")
def incidents():
    status_filter = request.args.get("status", "All")
    category_filter = request.args.get("category", "All")
    archived_filter = request.args.get("archived", "hide")

    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT id, patient_name, category, subcategory, description, status, created_at, updated_at, archived
        FROM incidents
        WHERE 1=1
    """
    params = []

    if status_filter != "All":
        query += " AND status = ?"
        params.append(status_filter)

    if category_filter != "All":
        query += " AND category = ?"
        params.append(category_filter)

    if archived_filter == "hide":
        query += " AND archived = 0"
    elif archived_filter == "only":
        query += " AND archived = 1"

    query += " ORDER BY created_at DESC"

    cursor.execute(query, params)
    all_incidents = cursor.fetchall()
    conn.close()

    return render_template(
        "incidents.html",
        incidents=all_incidents,
        status_filter=status_filter,
        category_filter=category_filter,
        archived_filter=archived_filter,
        is_admin=is_admin()
    )

@app.route("/edit/<int:incident_id>", methods=["GET", "POST"])
def edit_incident(incident_id):
    if not is_admin():
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        patient_name = request.form.get("patient_name")
        category = request.form.get("category")
        subcategory = request.form.get("subcategory")
        description = request.form.get("description")
        status = request.form.get("status")

        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            UPDATE incidents
            SET patient_name = ?,
                category = ?,
                subcategory = ?,
                description = ?,
                status = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            patient_name,
            category,
            subcategory,
            description,
            status,
            updated_at,
            incident_id
        ))
        conn.commit()
        conn.close()

        return redirect("/incidents")

    cursor.execute("""
        SELECT id, patient_name, category, subcategory, description, status, created_at, updated_at, archived
        FROM incidents
        WHERE id = ?
    """, (incident_id,))
    incident = cursor.fetchone()
    conn.close()

    if incident is None:
        return "Incident not found", 404

    return render_template(
        "edit_incident.html",
        incident=incident,
        category_map=CATEGORY_MAP,
        status_options=STATUS_OPTIONS,
        is_admin=is_admin()
    )

@app.route("/archive/<int:incident_id>", methods=["POST"])
def archive_incident(incident_id):
    if not is_admin():
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        UPDATE incidents
        SET archived = 1,
            updated_at = ?
        WHERE id = ?
    """, (updated_at, incident_id))

    conn.commit()
    conn.close()

    return redirect("/incidents")

@app.route("/unarchive/<int:incident_id>", methods=["POST"])
def unarchive_incident(incident_id):
    if not is_admin():
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        UPDATE incidents
        SET archived = 0,
            updated_at = ?
        WHERE id = ?
    """, (updated_at, incident_id))

    conn.commit()
    conn.close()

    return redirect("/incidents?archived=all")

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        password = request.form.get("password")

        if password == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect("/incidents")
        else:
            error = "Incorrect password."

    return render_template("login.html", error=error, is_admin=is_admin())

@app.route("/logout")
def logout():
    session.pop("is_admin", None)
    return redirect("/incidents")

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5001)
