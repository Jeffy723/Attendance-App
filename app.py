from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from db import init_db, get_db

OWNER_EMAIL = "jeffykjose10@gmail.com"

app = Flask(__name__)
app.secret_key = "super-secret-key"

init_db()

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        db = get_db()
        cur = db.cursor()

        cur.execute(
            "SELECT id, password, role FROM users WHERE email=?",
            (email,)
        )
        user = cur.fetchone()

        if user and check_password_hash(user[1], password):
            session["user_id"] = user[0]
            session["role"] = user[2]

            return redirect("/dashboard")

        return "Invalid email or password"

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].lower()
        password = generate_password_hash(request.form["password"])

        role = "owner" if email == OWNER_EMAIL else "student"

        db = get_db()
        cur = db.cursor()

        cur.execute(
            "INSERT INTO users (email, password, role) VALUES (?, ?, ?)",
            (email, password, role)
        )
        db.commit()

        return redirect("/")

    return render_template("register.html")


@app.route("/dashboard")
def dashboard():
    role = session["role"]

    if role == "owner":
        return render_template("owner_dashboard.html")

    if role == "editor":
        return "EDITOR DASHBOARD"

    # STUDENT
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT id, name FROM students WHERE user_id=?",
        (session["user_id"],)
    )
    student = cur.fetchone()

    if not student:
        return redirect("/profile")

    return render_template(
        "student_dashboard.html",
        student=student
    )


@app.route("/profile", methods=["GET", "POST"])
def profile():
    db = get_db()
    cur = db.cursor()

    cur.execute("SELECT id FROM semesters WHERE is_active=1")
    sem = cur.fetchone()

    if request.method == "POST":
        name = request.form["name"]
        roll = request.form["roll"]

        cur.execute("""
        INSERT INTO students (user_id,name,roll_no,semester_id)
        VALUES (?,?,?,?)
        """, (session["user_id"], name, roll, sem[0]))

        db.commit()
        return redirect("/dashboard")

    return """
    <h3>Complete Profile</h3>
    <form method="post">
      Name: <input name="name"><br>
      Roll No: <input name="roll"><br>
      <button>Save</button>
    </form>
    """
    
@app.route("/manage_users")
def manage_users():
    if session.get("role") != "owner":
        return "Unauthorized"

    db = get_db()
    cur = db.cursor()

    cur.execute("SELECT id, email, role FROM users")
    users = cur.fetchall()

    return render_template("manage_users.html", users=users)


@app.route("/make_editor/<int:uid>")
def make_editor(uid):
    if session.get("role") != "owner":
        return "Unauthorized"

    db = get_db()
    cur = db.cursor()

    cur.execute(
        "UPDATE users SET role='editor' WHERE id=?",
        (uid,)
    )
    db.commit()
    return redirect("/manage_users")


@app.route("/remove_editor/<int:uid>")
def remove_editor(uid):
    if session.get("role") != "owner":
        return "Unauthorized"

    db = get_db()
    cur = db.cursor()

    cur.execute(
        "UPDATE users SET role='student' WHERE id=?",
        (uid,)
    )
    db.commit()
    return redirect("/manage_users")


@app.route("/add_semester", methods=["GET", "POST"])
def add_semester():
    if session.get("role") != "owner":
        return "Unauthorized"

    db = get_db()
    cur = db.cursor()

    if request.method == "POST":
        sem_name = request.form["semester"]

        # deactivate all semesters
        cur.execute("UPDATE semesters SET is_active = 0")

        # add new active semester
        cur.execute(
            "INSERT INTO semesters (name, is_active) VALUES (?, 1)",
            (sem_name,)
        )

        db.commit()
        return redirect("/dashboard")

    # fetch existing semesters
    cur.execute("SELECT name, is_active FROM semesters")
    semesters = cur.fetchall()

    return render_template("add_semester.html", semesters=semesters)

@app.route("/add_subject", methods=["GET", "POST"])
def add_subject():
    if session.get("role") not in ["owner", "editor"]:
        return "Unauthorized"

    db = get_db()
    cur = db.cursor()

    # get active semester
    cur.execute("SELECT id, name FROM semesters WHERE is_active = 1")
    semester = cur.fetchone()

    if not semester:
        return "No active semester. Add a semester first."

    if request.method == "POST":
        subject_name = request.form["subject"]

        cur.execute(
            "INSERT INTO subjects (name, semester_id) VALUES (?, ?)",
            (subject_name, semester[0])
        )
        db.commit()
        return redirect("/add_subject")

    # fetch subjects of active semester
    cur.execute(
        "SELECT name FROM subjects WHERE semester_id = ?",
        (semester[0],)
    )
    subjects = cur.fetchall()

    return render_template(
        "add_subject.html",
        semester=semester,
        subjects=subjects
    )

@app.route("/add_class", methods=["GET", "POST"])
def add_class():
    if session.get("role") not in ["owner", "editor"]:
        return "Unauthorized"

    db = get_db()
    cur = db.cursor()

    # get active semester
    cur.execute("SELECT id, name FROM semesters WHERE is_active = 1")
    semester = cur.fetchone()

    if not semester:
        return "No active semester. Add semester first."

    # get subjects of active semester
    cur.execute(
        "SELECT id, name FROM subjects WHERE semester_id = ?",
        (semester[0],)
    )
    subjects = cur.fetchall()

    if request.method == "POST":
        date = request.form["date"]
        subject_id = request.form["subject"]
        hours = request.form["hours"]
        note = request.form.get("note", "")

        cur.execute("""
        INSERT INTO class_log (date, subject_id, hours)
        VALUES (?, ?, ?)
        """, (date, subject_id, hours))

        db.commit()
        return redirect("/add_class")

    # fetch class logs
    cur.execute("""
    SELECT class_log.date, subjects.name, class_log.hours
    FROM class_log
    JOIN subjects ON class_log.subject_id = subjects.id
    ORDER BY class_log.date DESC
    """)
    classes = cur.fetchall()

    return render_template(
        "add_class.html",
        semester=semester,
        subjects=subjects,
        classes=classes
    )

@app.route("/mark_attendance", methods=["GET", "POST"])
def mark_attendance():
    # Only students can mark attendance
    if session.get("role") != "student":
        return "Unauthorized"

    db = get_db()
    cur = db.cursor()

    # Get student ID
    cur.execute(
        "SELECT id FROM students WHERE user_id = ?",
        (session["user_id"],)
    )
    student = cur.fetchone()

    if not student:
        return redirect("/profile")

    student_id = student[0]

    date = request.form.get("date")
    classes = []

    # If date is selected, fetch classes for that date
    if date:
        cur.execute("""
        SELECT class_log.id, subjects.name, class_log.hours
        FROM class_log
        JOIN subjects ON class_log.subject_id = subjects.id
        WHERE class_log.date = ?
        """, (date,))
        classes = cur.fetchall()

    # If attendance form is submitted
    if request.method == "POST" and "submit_attendance" in request.form:
        selected_classes = request.form.getlist("class_id")

        for class_id in selected_classes:
            # Prevent duplicate attendance
            cur.execute("""
            SELECT id FROM attendance
            WHERE class_id = ? AND student_id = ?
            """, (class_id, student_id))

            if not cur.fetchone():
                cur.execute("""
                INSERT INTO attendance (class_id, student_id, attended)
                VALUES (?, ?, 1)
                """, (class_id, student_id))

        db.commit()
        return redirect("/dashboard")

    return render_template(
        "mark_attendance.html",
        classes=classes,
        date=date
    )


@app.route("/view_attendance")
def view_attendance():
    if session.get("role") != "student":
        return "Unauthorized"

    db = get_db()
    cur = db.cursor()

    # get student id
    cur.execute(
        "SELECT id FROM students WHERE user_id=?",
        (session["user_id"],)
    )
    student_id = cur.fetchone()[0]

    # subject-wise analytics
    cur.execute("""
    SELECT
        subjects.name,
        IFNULL(SUM(class_log.hours), 0) AS total_hours,
        IFNULL(SUM(
            CASE WHEN attendance.attended = 1
            THEN class_log.hours ELSE 0 END
        ), 0) AS attended_hours
    FROM subjects
    JOIN class_log ON class_log.subject_id = subjects.id
    LEFT JOIN attendance
      ON attendance.class_id = class_log.id
      AND attendance.student_id = ?
    GROUP BY subjects.id
    """, (student_id,))

    data = cur.fetchall()

    # overall analytics
    total_all = sum(d[1] for d in data)
    attended_all = sum(d[2] for d in data)

    overall_pct = (attended_all / total_all * 100) if total_all > 0 else 0

    return render_template(
        "view_attendance.html",
        data=data,
        total_all=total_all,
        attended_all=attended_all,
        overall_pct=overall_pct
    )


@app.route("/edit_attendance", methods=["GET", "POST"])
def edit_attendance():
    if session.get("role") != "student":
        return "Unauthorized"

    db = get_db()
    cur = db.cursor()

    # Get student ID
    cur.execute(
        "SELECT id FROM students WHERE user_id=?",
        (session["user_id"],)
    )
    student_id = cur.fetchone()[0]

    # Handle update
    if request.method == "POST":
        att_id = request.form["att_id"]
        status = request.form["status"]

        cur.execute(
            "UPDATE attendance SET attended=? WHERE id=?",
            (status, att_id)
        )
        db.commit()
        return redirect("/edit_attendance")

    # Fetch attendance
    cur.execute("""
    SELECT attendance.id, class_log.date, subjects.name,
           class_log.hours, attendance.attended
    FROM attendance
    JOIN class_log ON attendance.class_id = class_log.id
    JOIN subjects ON class_log.subject_id = subjects.id
    WHERE attendance.student_id = ?
    ORDER BY class_log.date DESC
    """, (student_id,))

    records = cur.fetchall()
    return render_template("edit_attendance.html", records=records)


@app.route("/delete_attendance/<int:att_id>")
def delete_attendance(att_id):
    if session.get("role") != "student":
        return "Unauthorized"

    db = get_db()
    cur = db.cursor()

    cur.execute("DELETE FROM attendance WHERE id=?", (att_id,))
    db.commit()

    return redirect("/edit_attendance")


@app.route("/manage_classes")
def manage_classes():
    if session.get("role") not in ["owner", "editor"]:
        return "Unauthorized"

    db = get_db()
    cur = db.cursor()

    cur.execute("""
    SELECT class_log.id, class_log.date, subjects.name, class_log.hours
    FROM class_log
    JOIN subjects ON class_log.subject_id = subjects.id
    ORDER BY class_log.date DESC
    """)
    classes = cur.fetchall()

    return render_template("manage_classes.html", classes=classes)


@app.route("/edit_class/<int:cid>", methods=["GET", "POST"])
def edit_class(cid):
    if session.get("role") not in ["owner", "editor"]:
        return "Unauthorized"

    db = get_db()
    cur = db.cursor()

    # Handle update
    if request.method == "POST":
        date = request.form["date"]
        subject_id = request.form["subject_id"]
        hours = request.form["hours"]

        cur.execute("""
        UPDATE class_log
        SET date=?, subject_id=?, hours=?
        WHERE id=?
        """, (date, subject_id, hours, cid))

        db.commit()
        return redirect("/manage_classes")

    # Fetch class details
    cur.execute("""
    SELECT date, subject_id, hours
    FROM class_log
    WHERE id=?
    """, (cid,))
    class_data = cur.fetchone()

    # Fetch subjects
    cur.execute("SELECT id, name FROM subjects")
    subjects = cur.fetchall()

    return render_template(
        "edit_class.html",
        class_data=class_data,
        subjects=subjects,
        cid=cid
    )


@app.route("/delete_class/<int:cid>")
def delete_class(cid):
    if session.get("role") not in ["owner", "editor"]:
        return "Unauthorized"

    db = get_db()
    cur = db.cursor()

    cur.execute("DELETE FROM attendance WHERE class_id=?", (cid,))
    cur.execute("DELETE FROM class_log WHERE id=?", (cid,))
    db.commit()

    return redirect("/manage_classes")

if __name__ == "__main__":
    pass




