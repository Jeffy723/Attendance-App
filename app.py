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

        # PostgreSQL uses %s instead of ?
        cur.execute(
            "SELECT id, password, role FROM users WHERE email = %s",
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

        try:
            cur.execute(
                "INSERT INTO users (email, password, role) VALUES (%s, %s, %s)",
                (email, password, role)
            )
            db.commit()
        except Exception as e:
            db.rollback()
            return "Email already registered"

        return redirect("/")

    return render_template("register.html")


@app.route("/dashboard")
def dashboard():
    role = session.get("role")
    user_id = session.get("user_id")

    if not role or not user_id:
        return redirect("/")

    if role == "owner":
        return render_template("owner_dashboard.html")

    if role == "editor":
        return redirect("/editor_dashboard")

    # STUDENT
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT id, name FROM students WHERE user_id=%s",
        (user_id,)
    )
    student = cur.fetchone()

    if not student:
        return redirect("/profile")

    return render_template("student_dashboard.html", student=student)



@app.route("/profile", methods=["GET", "POST"])
def profile():
    db = get_db()
    cur = db.cursor()

    cur.execute("SELECT id FROM semesters WHERE is_active=TRUE")
    sem = cur.fetchone()

    if request.method == "POST":
        name = request.form["name"]
        roll = request.form["roll"]

        cur.execute("""
        INSERT INTO students (user_id,name,roll_no,semester_id)
        VALUES (%s,%s,%s,%s)
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
        "UPDATE users SET role='editor' WHERE id=%s",
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
        "UPDATE users SET role='student' WHERE id=%s",
        (uid,)
    )
    db.commit()
    return redirect("/manage_users")


@app.route("/editor_dashboard")
def editor_dashboard():
    if session.get("role") != "editor":
        return redirect("/")

    return "<h2>Editor Dashboard (coming soon)</h2>"


@app.route("/add_semester", methods=["GET", "POST"])
def add_semester():
    if session.get("role") != "owner":
        return "Unauthorized"

    db = get_db()
    cur = db.cursor()

    if request.method == "POST":
        sem_name = request.form["semester"]

        # deactivate all semesters
        cur.execute("UPDATE semesters SET is_active = FALSE")

        # add new active semester
        cur.execute(
            "INSERT INTO semesters (name, is_active) VALUES (%s, TRUE)",
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
    cur.execute("SELECT id, name FROM semesters WHERE is_active = TRUE")
    semester = cur.fetchone()

    if not semester:
        return "No active semester. Add a semester first."

    if request.method == "POST":
        subject_name = request.form["subject"]

        cur.execute(
            "INSERT INTO subjects (name, semester_id) VALUES (%s, %s)",
            (subject_name, semester[0])
        )
        db.commit()
        return redirect("/add_subject")

    # fetch subjects of active semester
    cur.execute(
        "SELECT name FROM subjects WHERE semester_id = %s",
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
    cur.execute("SELECT id, name FROM semesters WHERE is_active = TRUE")
    semester = cur.fetchone()

    if not semester:
        return "No active semester. Add semester first."

    # get subjects of active semester
    cur.execute(
        "SELECT id, name FROM subjects WHERE semester_id = %s",
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
        VALUES (%s, %s, %s)
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
        "SELECT id FROM students WHERE user_id = %s",
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
        WHERE class_log.date = %s
        """, (date,))
        classes = cur.fetchall()

    # If attendance form is submitted
    if request.method == "POST" and "submit_attendance" in request.form:
        selected_classes = request.form.getlist("class_id")

        for class_id in selected_classes:
            # Prevent duplicate attendance
            cur.execute("""
            SELECT id FROM attendance
            WHERE class_id = %s AND student_id = %s
            """, (class_id, student_id))

            if not cur.fetchone():
                cur.execute("""
                INSERT INTO attendance (class_id, student_id, attended)
                VALUES (%s, %s, TRUE)
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

    cur.execute("SELECT id FROM students WHERE user_id=%s", (session["user_id"],))
    student_id = cur.fetchone()[0]

    cur.execute("""
        SELECT
            subjects.name,
            COALESCE(SUM(class_log.hours), 0),
            COALESCE(SUM(
                CASE WHEN attendance.attended = TRUE
                THEN class_log.hours ELSE 0 END
            ), 0)
        FROM subjects
        JOIN class_log ON class_log.subject_id = subjects.id
        LEFT JOIN attendance
          ON attendance.class_id = class_log.id
          AND attendance.student_id = %s
        GROUP BY subjects.id
    """, (student_id,))

    data = cur.fetchall()

    total = sum(d[1] for d in data)
    attended = sum(d[2] for d in data)
    pct = (attended / total * 100) if total > 0 else 0

    return render_template(
        "view_attendance.html",
        data=data,
        total_all=total,
        attended_all=attended,
        overall_pct=pct
    )


@app.route("/edit_attendance", methods=["GET", "POST"])
def edit_attendance():
    if session.get("role") != "student":
        return "Unauthorized"

    db = get_db()
    cur = db.cursor()

    # Get student id
    cur.execute(
        "SELECT id FROM students WHERE user_id=%s",
        (session["user_id"],)
    )
    student_id = cur.fetchone()[0]

    date = request.form.get("date")
    records = []

    # Handle update
    if request.method == "POST" and "att_id" in request.form:
        att_id = request.form["att_id"]
        status = request.form["status"] == "1"

        cur.execute(
            "UPDATE attendance SET attended=%s WHERE id=%s",
            (status, att_id)
        )
        db.commit()

    # Load records for selected date
    if date:
        cur.execute("""
            SELECT attendance.id,
                   subjects.name,
                   class_log.hours,
                   attendance.attended
            FROM attendance
            JOIN class_log ON attendance.class_id = class_log.id
            JOIN subjects ON class_log.subject_id = subjects.id
            WHERE attendance.student_id = %s
              AND class_log.date = %s
            ORDER BY subjects.name
        """, (student_id, date))

        records = cur.fetchall()

    return render_template(
        "edit_attendance.html",
        records=records,
        date=date
    )



@app.route("/delete_attendance/<int:att_id>")
def delete_attendance(att_id):
    if session.get("role") != "student":
        return "Unauthorized"

    db = get_db()
    cur = db.cursor()

    cur.execute("DELETE FROM attendance WHERE id=%s", (att_id,))
    db.commit()

    return redirect("/edit_attendance")



@app.route("/manage_classes", methods=["GET", "POST"])
def manage_classes():
    if session.get("role") not in ["owner", "editor"]:
        return "Unauthorized"

    db = get_db()
    cur = db.cursor()

    date = request.form.get("date")
    classes = []

    if date:
        cur.execute("""
            SELECT class_log.id,
                   class_log.date,
                   subjects.name,
                   class_log.hours
            FROM class_log
            JOIN subjects ON class_log.subject_id = subjects.id
            WHERE class_log.date = %s
            ORDER BY subjects.name
        """, (date,))
        classes = cur.fetchall()

    return render_template(
        "manage_classes.html",
        classes=classes,
        date=date
    )


@app.route("/edit_class/<int:cid>", methods=["GET", "POST"])
def edit_class(cid):
    if session.get("role") not in ["owner", "editor"]:
        return "Unauthorized"

    db = get_db()
    cur = db.cursor()

    if request.method == "POST":
        date = request.form["date"]
        subject_id = request.form["subject_id"]
        hours = request.form["hours"]

        cur.execute("""
            UPDATE class_log
            SET date=%s, subject_id=%s, hours=%s
            WHERE id=%s
        """, (date, subject_id, hours, cid))

        db.commit()
        return redirect("/manage_classes")

    cur.execute("""
        SELECT date, subject_id, hours
        FROM class_log
        WHERE id=%s
    """, (cid,))
    class_data = cur.fetchone()

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

    cur.execute("DELETE FROM attendance WHERE class_id=%s", (cid,))
    cur.execute("DELETE FROM class_log WHERE id=%s", (cid,))
    db.commit()

    return redirect("/manage_classes")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)




