from flask import Flask, render_template, request, redirect, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from db import init_db, get_db
from datetime import date
from bson.objectid import ObjectId

OWNER_EMAIL = "jeffykjose10@gmail.com"

app = Flask(__name__)
app.secret_key = "super-secret-key"

init_db()

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].lower()
        password = request.form["password"]

        db = get_db()

        # MongoDB query
        user = db.users.find_one({"email": email})

        if not user:
            flash("User not found. Please register first.", "danger")
            return redirect("/")

        if not check_password_hash(user["password"], password):
            flash("Incorrect password. Try again.", "danger")
            return redirect("/")

        # SUCCESS
        session["user_id"] = str(user["_id"])
        session["email"] = user["email"] 
        session["role"] = user["role"]

        flash("Login successful!", "success")
        return redirect("/dashboard")

    return render_template("login.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].lower()
        password = generate_password_hash(request.form["password"])

        role = "owner" if email == OWNER_EMAIL else "student"

        db = get_db()

        # Check if user already exists
        if db.users.find_one({"email": email}):
            flash("Email already registered. Try logging in.", "danger")
            return redirect("/register")

        # Insert new user
        db.users.insert_one({
            "email": email,
            "password": password,
            "role": role
        })

        flash("Registration successful! Please log in.", "success")
        return redirect("/")

    return render_template("register.html")


@app.route("/dashboard")
def dashboard():
    role = session.get("role")
    user_id = session.get("user_id")

    if not role or not user_id:
        return redirect("/")

    db = get_db()

    # OWNER
    if role == "owner":
        return render_template("owner_dashboard.html")

    # EDITOR
    if role == "editor":
        # Total hours logged
        total_classes = sum(
            cls.get("hours", 0) for cls in db.class_log.find()
        )

        # Hours logged today
        today_classes = sum(
            cls.get("hours", 0)
            for cls in db.class_log.find({"date": str(date.today())})
        )

        return render_template(
            "editor_dashboard.html",
            total_classes=total_classes,
            today_classes=today_classes
        )

    # STUDENT
    student = db.students.find_one(
    	{"email": session["email"], "active": True}
    )

    if not student:
        return redirect("/profile")

    return render_template("student_dashboard.html", student=student)


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if not session.get("user_id"):
        return redirect("/")

    db = get_db()

    # get active semester
    sem = db.semesters.find_one({"is_active": True})

    if not sem:
        return "No active semester. Contact admin."

    if request.method == "POST":
        name = request.form["name"]
        roll_no = request.form["roll_no"]

        db.students.update_one(
    		{"email": session["email"]},
    		{
        	    "$set": {
           		"name": name,
            		"roll_no": int(roll_no),
            		"active": True
        	    }
    		},
    		upsert=True
	)


        return redirect("/dashboard")

    return render_template("profile.html")


    
@app.route("/manage_users")
def manage_users():
    if session.get("role") != "owner":
        return "Unauthorized"

    db = get_db()

    # Fetch all users (only required fields)
    users = list(
        db.users.find({}, {"email": 1, "role": 1})
    )

    return render_template("manage_users.html", users=users)


@app.route("/make_editor/<uid>")
def make_editor(uid):
    if session.get("role") != "owner":
        return "Unauthorized"

    db = get_db()

    db.users.update_one(
        {"_id": ObjectId(uid)},
        {"$set": {"role": "editor"}}
    )

    return redirect("/manage_users")


@app.route("/remove_editor/<uid>")
def remove_editor(uid):
    if session.get("role") != "owner":
        return "Unauthorized"

    db = get_db()

    db.users.update_one(
        {"_id": ObjectId(uid)},
        {"$set": {"role": "student"}}
    )

    return redirect("/manage_users")


@app.route("/add_semester", methods=["GET", "POST"])
def add_semester():
    if session.get("role") != "owner":
        return "Unauthorized"

    db = get_db()

    if request.method == "POST":
        sem_name = request.form["semester"]

        # deactivate all semesters
        db.semesters.update_many(
            {},
            {"$set": {"is_active": False}}
        )

        # add new active semester
        db.semesters.insert_one({
            "name": sem_name,
            "is_active": True
        })

        return redirect("/dashboard")

    # fetch existing semesters
    semesters = list(
        db.semesters.find({}, {"name": 1, "is_active": 1})
    )

    return render_template("add_semester.html", semesters=semesters)


@app.route("/add_subject", methods=["GET", "POST"])
def add_subject():
    if session.get("role") not in ["owner", "editor"]:
        return "Unauthorized"

    db = get_db()

    # get active semester
    semester = db.semesters.find_one({"is_active": True})

    if not semester:
        return "No active semester. Add a semester first."

    if request.method == "POST":
        subject_name = request.form["subject"]

        db.subjects.insert_one({
            "name": subject_name,
            "semester_id": semester["_id"]
        })

        return redirect("/add_subject")

    # fetch subjects of active semester
    subjects = list(
        db.subjects.find(
            {"semester_id": semester["_id"]},
            {"name": 1}
        )
    )

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

    # get active semester
    semester = db.semesters.find_one({"is_active": True})

    if not semester:
        return "No active semester. Add semester first."

    # get subjects of active semester
    subjects = list(
        db.subjects.find(
            {"semester_id": semester["_id"]},
            {"name": 1}
        )
    )

    if request.method == "POST":
        class_date = request.form["date"]
        subject_id = request.form["subject"]
        hours = int(request.form["hours"])
        note = request.form.get("note", "")

        db.class_log.insert_one({
            "date": class_date,
            "subject_id": ObjectId(subject_id),
            "hours": hours,
            "note": note
        })

        return redirect("/add_class")

    # fetch class logs (latest first)
    class_logs = list(
        db.class_log.find().sort("date", -1)
    )

    # enrich class logs with subject name (manual join)
    classes = []
    for log in class_logs:
        subject = db.subjects.find_one(
            {"_id": log["subject_id"]},
            {"name": 1}
        )
        classes.append({
            "date": log["date"],
            "subject": subject["name"] if subject else "Unknown",
            "hours": log["hours"]
        })

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

    # Get student document
    student = db.students.find_one(
        {"user_id": ObjectId(session["user_id"])}
    )

    if not student:
        return redirect("/profile")

    student_id = student["_id"]

    selected_date = request.form.get("date")
    classes = []

    # Load classes for selected date
    if selected_date:
        class_logs = list(
            db.class_log.find({"date": selected_date})
        )

        # manual join with subjects
        for log in class_logs:
            subject = db.subjects.find_one(
                {"_id": log["subject_id"]},
                {"name": 1}
            )
            classes.append({
                "id": str(log["_id"]),
                "subject": subject["name"] if subject else "Unknown",
                "hours": log["hours"]
            })

    # Handle attendance submission
    if request.method == "POST" and "submit_attendance" in request.form:
        selected_classes = request.form.getlist("class_id")

        if not selected_classes:
            flash("No classes selected.", "warning")
            return redirect("/mark_attendance")

        added = 0
        skipped = 0

        for class_id in selected_classes:
            existing = db.attendance.find_one({
                "class_id": ObjectId(class_id),
                "student_id": student_id
            })

            if existing:
                skipped += 1
            else:
                db.attendance.insert_one({
                    "class_id": ObjectId(class_id),
                    "student_id": student_id,
                    "attended": True
                })
                added += 1

        if added:
            flash(f"Attendance marked for {added} class(es).", "success")
        if skipped:
            flash(f"{skipped} class(es) were already marked.", "info")

        return redirect("/dashboard")

    return render_template(
        "mark_attendance.html",
        classes=classes,
        date=selected_date
    )


@app.route("/view_attendance")
def view_attendance():
    if session.get("role") != "student":
        return "Unauthorized"

    db = get_db()

    # Get student document
    student = db.students.find_one(
        {"user_id": ObjectId(session["user_id"])}
    )

    if not student:
        return redirect("/profile")

    student_id = student["_id"]

    data = []

    # For each subject, calculate total hours and attended hours
    subjects = list(db.subjects.find())

    for subject in subjects:
        # All classes for this subject
        class_logs = list(
            db.class_log.find({"subject_id": subject["_id"]})
        )

        total_hours = sum(
            cls.get("hours", 0) for cls in class_logs
        )

        attended_hours = 0
        for cls in class_logs:
            att = db.attendance.find_one({
                "class_id": cls["_id"],
                "student_id": student_id,
                "attended": True
            })
            if att:
                attended_hours += cls.get("hours", 0)

        data.append((
            subject["name"],
            total_hours,
            attended_hours
        ))

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

    # Get student document
    student = db.students.find_one(
        {"user_id": ObjectId(session["user_id"])}
    )

    if not student:
        return redirect("/profile")

    student_id = student["_id"]

    selected_date = request.form.get("date")
    records = []

    # Handle update
    if request.method == "POST" and "att_id" in request.form:
        att_id = request.form["att_id"]
        status = request.form["status"] == "1"

        db.attendance.update_one(
            {"_id": ObjectId(att_id)},
            {"$set": {"attended": status}}
        )

        flash("Attendance updated successfully.", "success")
        return redirect("/edit_attendance")

    # Load records for selected date
    if selected_date:
        attendance_records = list(
            db.attendance.find(
                {"student_id": student_id}
            )
        )

        for att in attendance_records:
            class_log = db.class_log.find_one(
                {"_id": att["class_id"]}
            )

            if not class_log or class_log.get("date") != selected_date:
                continue

            subject = db.subjects.find_one(
                {"_id": class_log["subject_id"]},
                {"name": 1}
            )

            records.append({
                "id": str(att["_id"]),
                "subject": subject["name"] if subject else "Unknown",
                "hours": class_log.get("hours", 0),
                "attended": att.get("attended", False)
            })

        # sort by subject name (like ORDER BY subjects.name)
        records.sort(key=lambda r: r["subject"])

    return render_template(
        "edit_attendance.html",
        records=records,
        date=selected_date
    )


@app.route("/delete_attendance/<att_id>")
def delete_attendance(att_id):
    if session.get("role") != "student":
        return "Unauthorized"

    db = get_db()

    db.attendance.delete_one(
        {"_id": ObjectId(att_id)}
    )

    flash("Attendance record deleted.", "danger")
    return redirect("/edit_attendance")


@app.route("/manage_classes", methods=["GET", "POST"])
def manage_classes():
    if session.get("role") not in ["owner", "editor"]:
        return "Unauthorized"

    db = get_db()

    selected_date = request.form.get("date")
    classes = []

    if selected_date:
        class_logs = list(
            db.class_log.find({"date": selected_date})
        )

        for log in class_logs:
            subject = db.subjects.find_one(
                {"_id": log["subject_id"]},
                {"name": 1}
            )

            classes.append({
                "id": str(log["_id"]),
                "date": log.get("date"),
                "subject": subject["name"] if subject else "Unknown",
                "hours": log.get("hours", 0)
            })

        # sort by subject name (like ORDER BY subjects.name)
        classes.sort(key=lambda c: c["subject"])

    return render_template(
        "manage_classes.html",
        classes=classes,
        date=selected_date
    )


@app.route("/edit_class/<cid>", methods=["GET", "POST"])
def edit_class(cid):
    if session.get("role") not in ["owner", "editor"]:
        return "Unauthorized"

    db = get_db()

    if request.method == "POST":
        class_date = request.form["date"]
        subject_id = request.form["subject_id"]
        hours = int(request.form["hours"])

        db.class_log.update_one(
            {"_id": ObjectId(cid)},
            {
                "$set": {
                    "date": class_date,
                    "subject_id": ObjectId(subject_id),
                    "hours": hours
                }
            }
        )

        return redirect("/manage_classes")

    # Load class data
    class_data = db.class_log.find_one(
        {"_id": ObjectId(cid)}
    )

    if not class_data:
        return redirect("/manage_classes")

    # Load all subjects
    subjects = list(
        db.subjects.find({}, {"name": 1})
    )

    return render_template(
        "edit_class.html",
        class_data=class_data,
        subjects=subjects,
        cid=cid
    )


@app.route("/delete_class/<cid>")
def delete_class(cid):
    if session.get("role") not in ["owner", "editor"]:
        return "Unauthorized"

    db = get_db()

    # Delete all attendance records for this class
    db.attendance.delete_many(
        {"class_id": ObjectId(cid)}
    )

    # Delete the class itself
    db.class_log.delete_one(
        {"_id": ObjectId(cid)}
    )

    return redirect("/manage_classes")


@app.route("/delete_user/<user_id>")
def delete_user(user_id):
    if session.get("role") != "owner":
        return "Unauthorized"

    db = get_db()

    # Prevent deleting self
    if user_id == session.get("user_id"):
        return "You cannot delete your own account"

    user_obj_id = ObjectId(user_id)

    # Fetch user
    user = db.users.find_one({"_id": user_obj_id})

    if not user:
        return redirect("/manage_users")

    if user.get("role") == "owner":
        return "Cannot delete another owner"

    # If student → clean attendance + student record
    if user.get("role") == "student":
        student = db.students.find_one(
            {"user_id": user_obj_id}
        )

        if student:
            student_id = student["_id"]

            db.attendance.delete_many(
                {"student_id": student_id}
            )

            db.students.delete_one(
                {"_id": student_id}
            )

    # Finally delete user
    db.users.delete_one(
        {"_id": user_obj_id}
    )

    return redirect("/manage_users")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect("/")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)




