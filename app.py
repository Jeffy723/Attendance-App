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


def get_next_class_log_no(db):
    counter = db.counters.find_one_and_update(
        {"_id": "class_log_no"},
        {"$inc": {"seq": 1}},
        return_document=True
    )
    return counter["seq"]


@app.route("/add_class", methods=["GET", "POST"])
def add_class():
    if session.get("role") not in ["owner", "editor"]:
        return "Unauthorized"

    db = get_db()

    # 🔹 get active semester
    semester = db.semesters.find_one({"is_active": True})
    if not semester:
        return "No active semester. Add semester first."

    # 🔹 get subjects of active semester
    subjects = list(
        db.subjects.find(
            {"semester_id": semester["_id"]},
            {"name": 1}
        )
    )

    if request.method == "POST":
        class_date = request.form["date"]
        subject_id = ObjectId(request.form["subject"])
        hours = int(request.form["hours"])
        note = request.form.get("note", "").strip()

        # 🔴 validate subject belongs to active semester
        subject = db.subjects.find_one({
            "_id": subject_id,
            "semester_id": semester["_id"]
        })
        if not subject:
            return "Invalid subject for active semester"

        # 🔴 atomic class_log_no generation
        next_no = get_next_class_log_no(db)

        db.class_log.insert_one({
            "date": class_date,
            "subject_id": subject_id,
            "hours": hours,
            "note": note,
            "semester_id": semester["_id"],   # ✅ REQUIRED
            "class_log_no": next_no           # ✅ REQUIRED
        })

        return redirect("/add_class")

    # 🔹 fetch class logs (latest class_log_no first)
    class_logs = list(
        db.class_log.find(
            {"semester_id": semester["_id"]}
        ).sort("class_log_no", -1)
    )

    classes = []
    for log in class_logs:
        subject = db.subjects.find_one(
            {"_id": log["subject_id"]},
            {"name": 1}
        )
        classes.append({
            "date": log["date"],
            "subject": subject["name"] if subject else "Unknown",
            "hours": log["hours"],
            "class_log_no": log["class_log_no"]
        })

    return render_template(
        "add_class.html",
        semester=semester,
        subjects=subjects,
        classes=classes
    )


@app.route("/mark_attendance", methods=["GET", "POST"])
def mark_attendance():
    if session.get("role") != "student":
        return "Unauthorized"

    db = get_db()

    # 🔹 get student
    student = db.students.find_one(
        {"user_id": ObjectId(session["user_id"])}
    )
    if not student:
        return redirect("/profile")

    student_id = student["_id"]

    # 🔹 active semester
    active_sem = db.semesters.find_one({"is_active": True})
    if not active_sem:
        return "No active semester"

    semester_id = active_sem["_id"]
    classes = []

    # ---------------------------
    # SUBMIT ATTENDANCE (POST)
    # ---------------------------
    if request.method == "POST" and "submit_attendance" in request.form:
        selected = request.form.getlist("class_log_no")

        if not selected:
            flash("No classes selected", "warning")
            return redirect(request.url)

        added, skipped = 0, 0

        for cl_no in selected:
            cl_no = int(cl_no)

            # 🔹 verify class exists
            class_log = db.class_log.find_one({
                "class_log_no": cl_no,
                "semester_id": semester_id
            })
            if not class_log:
                continue

            # 🔹 prevent duplicates
            exists = db.attendance.find_one({
                "student_id": student_id,
                "class_log_no": cl_no,
                "semester_id": semester_id
            })

            if exists:
                skipped += 1
            else:
                db.attendance.insert_one({
                    "student_id": student_id,
                    "class_log_no": cl_no,
                    "semester_id": semester_id,
                    "present": True
                })
                added += 1

        flash(f"{added} added, {skipped} skipped", "success")
        return redirect("/view_attendance")

    # ---------------------------
    # LOAD CLASSES (GET)
    # ---------------------------
    selected_date = request.args.get("date")
    if selected_date:
        class_logs = list(
            db.class_log.find({
                "date": selected_date,
                "semester_id": semester_id
            }).sort("class_log_no", 1)
        )

        for log in class_logs:
            subject = db.subjects.find_one(
                {"_id": log["subject_id"]},
                {"name": 1}
            )

            classes.append({
                "class_log_no": log["class_log_no"],
                "subject": subject["name"] if subject else "Unknown",
                "hours": log["hours"]
            })

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

    student = db.students.find_one(
        {"user_id": ObjectId(session["user_id"])}
    )
    if not student:
        return redirect("/profile")

    student_id = student["_id"]

    active_sem = db.semesters.find_one({"is_active": True})
    if not active_sem:
        return "No active semester"

    semester_id = active_sem["_id"]

    # 🔹 load class logs
    class_logs = list(db.class_log.find({"semester_id": semester_id}))

    class_log_map = {}
    subject_hours = {}

    for cls in class_logs:
        cl_no = cls.get("class_log_no")
        if cl_no is None:
            continue

        class_log_map[cl_no] = cls
        subj_id = cls["subject_id"]
        subject_hours[subj_id] = subject_hours.get(subj_id, 0) + cls.get("hours", 1)

    # 🔹 load attendance
    attendance = list(db.attendance.find({
        "student_id": student_id,
        "semester_id": semester_id,
        "present": True
    }))

    subject_attended = {}

    for att in attendance:
        cl_no = att["class_log_no"]
        if cl_no not in class_log_map:
            continue

        cls = class_log_map[cl_no]
        subj_id = cls["subject_id"]
        subject_attended[subj_id] = subject_attended.get(subj_id, 0) + cls.get("hours", 1)

    # 🔹 prepare view data
    data = []
    subjects = list(db.subjects.find({"semester_id": semester_id}))

    for subject in subjects:
        total = subject_hours.get(subject["_id"], 0)
        attended = subject_attended.get(subject["_id"], 0)
        data.append((subject["name"], total, attended))

    total_all = sum(d[1] for d in data)
    attended_all = sum(d[2] for d in data)
    overall_pct = (attended_all / total_all * 100) if total_all else 0

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

    student = db.students.find_one(
        {"user_id": ObjectId(session["user_id"])}
    )
    if not student:
        return redirect("/profile")

    student_id = student["_id"]

    # 🔹 ACTIVE SEMESTER
    semester = db.semesters.find_one({"is_active": True})
    if not semester:
        return "No active semester"

    semester_id = semester["_id"]

    selected_date = request.args.get("date") or request.form.get("date")
    records = []

    # ---------------------------
    # UPDATE ATTENDANCE (POST)
    # ---------------------------
    if request.method == "POST" and "class_log_no" in request.form:
        class_log_no = int(request.form["class_log_no"])
        status = request.form["status"] == "1"

        existing = db.attendance.find_one({
            "student_id": student_id,
            "class_log_no": class_log_no,
            "semester_id": semester_id
        })

        if existing:
            db.attendance.update_one(
                {"_id": existing["_id"]},
                {"$set": {"present": status}}
            )
        else:
            db.attendance.insert_one({
                "student_id": student_id,
                "class_log_no": class_log_no,
                "semester_id": semester_id,
                "present": status
            })

        flash("Attendance updated successfully.", "success")
        return redirect(f"/edit_attendance?date={selected_date}")

    # ---------------------------
    # LOAD CLASSES (LEFT JOIN)
    # ---------------------------
    if selected_date:
        class_logs = list(
            db.class_log.find({
                "date": selected_date,
                "semester_id": semester_id
            }).sort("class_log_no", 1)
        )

        for cls in class_logs:
            attendance = db.attendance.find_one({
                "student_id": student_id,
                "class_log_no": cls["class_log_no"],
                "semester_id": semester_id
            })

            subject = db.subjects.find_one(
                {"_id": cls["subject_id"]},
                {"name": 1}
            )

            records.append({
                "class_log_no": cls["class_log_no"],
                "subject": subject["name"] if subject else "Unknown",
                "hours": cls.get("hours", 1),
                "present": attendance["present"] if attendance else None
            })

    return render_template(
        "edit_attendance.html",
        records=records,
        date=selected_date
    )


@app.route("/manage_classes", methods=["GET", "POST"])
def manage_classes():
    if session.get("role") not in ["owner", "editor"]:
        return "Unauthorized"

    db = get_db()

    semester = db.semesters.find_one({"is_active": True})
    if not semester:
        return "No active semester"

    selected_date = request.form.get("date")
    classes = []

    if selected_date:
        class_logs = list(
            db.class_log.find({
                "date": selected_date,
                "semester_id": semester["_id"]
            })
        )

        for log in class_logs:
            subject = db.subjects.find_one(
                {"_id": log["subject_id"]},
                {"name": 1}
            )

            classes.append({
                "id": str(log["_id"]),
                "date": log["date"],
                "subject": subject["name"] if subject else "Unknown",
                "hours": log["hours"],
                "class_log_no": log.get("class_log_no")
            })

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

    class_data = db.class_log.find_one({"_id": ObjectId(cid)})
    if not class_data:
        return redirect("/manage_classes")

    subjects = list(db.subjects.find({}, {"name": 1}))

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

    cls = db.class_log.find_one({"_id": ObjectId(cid)})
    if not cls:
        return redirect("/manage_classes")

    cl_no = cls.get("class_log_no")

    # 🔴 Delete attendance linked via class_log_no
    if cl_no is not None:
        db.attendance.delete_many(
            {"class_log_no": cl_no}
        )

    # Delete class itself
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




