from flask import Flask, request, jsonify, session, render_template_string
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
app.secret_key = "your_secret_key_123"
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 3600000  # 1 hour

CORS(app, supports_credentials=True, origins=["http://localhost:5000", "http://127.0.0.1:5000", "http://192.168.1.4:5000"])

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="final_project"
        )
        return connection
    except Error as e:
        print("DB Error:", e)
        return None

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"success": False, "message": "Fill all fields!"})

    if username.lower() == "admin":
        return jsonify({"success": False, "message": "This username is not available."})

    connection = get_db_connection()
    if not connection:
        return jsonify({"success": False, "message": "Database connection failed!"})

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Username already exists!"})

        cursor.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, 'user')",
                       (username, password))
        connection.commit()

        return jsonify({"success": True, "message": "Registered successfully!"})

    except Exception as e:
        print("Registration error:", e)
        return jsonify({"success": False, "message": "Registration failed!"})
    finally:
        cursor.close()
        connection.close()

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    connection = get_db_connection()
    if not connection:
        return jsonify({"success": False, "message": "DB connection failed"})

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s",
                       (username, password))
        user = cursor.fetchone()

        if not user:
            return jsonify({"success": False, "message": "Invalid username or password"})

        # Store session
        session["logged_in"] = True
        session["username"] = user["username"]
        session["role"] = user["role"]

        return jsonify({"success": True, "redirect": "/dashboard"})
    except Exception as e:
        print("Login error:", e)
        return jsonify({"success": False, "message": "Login failed"})
    finally:
        cursor.close()
        connection.close()

@app.route("/check_session")
def check_session():
    if session.get("logged_in"):
        return jsonify({
            "logged_in": True,
            "username": session.get("username"),
            "role": session.get("role")
        })
    return jsonify({"logged_in": False})

@app.route("/logout")
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/get_students")
def get_students():
    if not session.get("logged_in"):
        return jsonify([])

    connection = get_db_connection()
    if not connection:
        return jsonify([])

    cursor = connection.cursor(dictionary=True)

    try:
        if session["role"] == "admin":
            cursor.execute("SELECT * FROM students")
        else:
            cursor.execute("SELECT * FROM students WHERE username=%s", (session["username"],))

        students = cursor.fetchall()
        return jsonify(students)
    except Exception as e:
        print("Get students error:", e)
        return jsonify([])
    finally:
        cursor.close()
        connection.close()

@app.route("/add_student", methods=["POST"])
def add_student():
    if not session.get("logged_in"):
        return jsonify({"success": False, "message": "Login required!"})

    data = request.json

    name = data.get("name")
    age = data.get("age")
    course = data.get("course")
    gwa = data.get("gwa")

    # If admin → use provided username + password
    # If student → use their own logged-in username
    username = data.get("username") if session["role"] == "admin" else session["username"]
    password = data.get("password", "")

    connection = get_db_connection()
    if not connection:
        return jsonify({"success": False, "message": "Database error!"})

    cursor = connection.cursor(dictionary=True)

    try:
        # 🔥 1. Admin inserts a new student → must create an account in users
        if session["role"] == "admin":
            cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
            exists = cursor.fetchone()

            if not exists:
                cursor.execute(
                    "INSERT INTO users (username, password, role) VALUES (%s, %s, 'user')",
                    (username, password)
                )

        # 🔥 2. Insert student record
        cursor.execute(
            "INSERT INTO students (name, age, course, gwa, username) VALUES (%s, %s, %s, %s, %s)",
            (name, age, course, gwa, username)
        )

        connection.commit()

        return jsonify({"success": True, "message": "Student added successfully!"})

    except Exception as e:
        print("ADD STUDENT ERROR:", e)
        return jsonify({"success": False, "message": "Backend error. Check server console."})
    finally:
        cursor.close()
        connection.close()

@app.route("/edit_student", methods=["POST"])
def edit_student():
    if not session.get("logged_in"):
        return jsonify({"success": False, "message": "Login required!"})

    data = request.json
    student_id = data.get("id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # User permission check
        if session["role"] != "admin":
            cursor.execute("SELECT username FROM students WHERE id=%s", (student_id,))
            row = cursor.fetchone()

            if not row or row["username"] != session["username"]:
                return jsonify({"success": False, "message": "Permission denied!"})

        cursor.execute(
            "UPDATE students SET name=%s, age=%s, course=%s, gwa=%s WHERE id=%s",
            (data["name"], data["age"], data["course"], data["gwa"], student_id)
        )

        connection.commit()
        return jsonify({"success": True, "message": "Student updated successfully!"})

    except Exception as e:
        print("EDIT ERROR:", e)
        return jsonify({"success": False, "message": "Backend error!"})
    finally:
        cursor.close()
        connection.close()

@app.route("/delete_student", methods=["POST"])
def delete_student():
    if not session.get("logged_in"):
        return jsonify({"success": False, "message": "Login required!"})

    data = request.json
    student_id = data.get("id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        if session["role"] != "admin":
            cursor.execute("SELECT username FROM students WHERE id=%s", (student_id,))
            row = cursor.fetchone()

            if not row or row["username"] != session["username"]:
                return jsonify({"success": False, "message": "Permission denied!"})

        cursor.execute("DELETE FROM students WHERE id=%s", (student_id,))
        connection.commit()

        return jsonify({"success": True, "message": "Student deleted successfully!"})

    except Exception as e:
        print("DELETE ERROR:", e)
        return jsonify({"success": False, "message": "Backend error!"})
    finally:
        cursor.close()
        connection.close()

@app.route("/")
def login_page():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login</title>
        <meta http-equiv="refresh" content="0; url=/login-page">
    </head>
    <body>
        <p>Redirecting to login page...</p>
    </body>
    </html>
    """)

@app.route("/login-page")
def login_page_actual():
    return render_template_string(open("login.html", encoding="utf-8").read())

@app.route("/dashboard")
def dashboard_page():
    return render_template_string(open("dashboard.html", encoding="utf-8").read())

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
