📊 Attendance Management System

A role-based web application to manage class attendance efficiently, built using Flask, PostgreSQL, and Bootstrap.
Designed for students, editors, and an owner (admin) with clean UI and real-world logic.

🚀 Features

👤 Authentication
User registration & login
Secure password hashing
Role-based access control

🎓 Student Features

Complete profile (name, roll number, semester)
Mark attendance (date-based)
View attendance summary (subject-wise & overall)
Edit / delete attendance records
Attendance shortage indication

🧑‍🏫 Editor Features

Dashboard with:
Total class hours logged
Today’s class hours
Add class hours
Manage class hours (edit / delete)
Date-based filtering to avoid large tables

👑 Owner Features
Manage semesters (activate one at a time)
Add subjects for active semester
Manage users:
Promote/demote editors
Delete users safely
Full control over the system

✨ UI & UX

Responsive Bootstrap 5 UI
Card-based dashboards
Auto-dismiss flash messages
Confirmation dialogs for destructive actions
Clean navigation for all roles

🛠 Tech Stack

Backend: Flask (Python)
Database: PostgreSQL
Frontend: HTML, Jinja2, Bootstrap 5
Deployment: Render
Version Control: Git & GitHub

⚙️ Setup Instructions (Local)

1️⃣ Clone the repository
git clone https://github.com/Jeffy723/Attendance-App.git
cd Attendance-App

2️⃣ Create virtual environment
python -m venv venv
source venv/bin/activate (Linux / macOS)
venv\Scripts\activate (Windows)

3️⃣ Install dependencies
pip install -r requirements.txt

4️⃣ Configure database
Set your PostgreSQL database URL:
export DATABASE_URL=postgresql://user:password@host/dbname
(Use set instead of export on Windows CMD.)

5️⃣ Run the application
python app.py

🌐 Deployment

The application is deployed using Render with a managed PostgreSQL database.
SQLite was avoided to prevent data loss on redeploy.

🔒 Notes

Only one semester can be active at a time
Editors can manage class hours
Owners have full administrative control
Intended for personal & academic use

📌 Future Enhancements
Attendance export (CSV / Excel)
Monthly analytics & charts
Email notifications
Role-based audit logs
Dark mode UI

👨‍💻 Author

Jeffy K Jose
B.Tech CSE Student
Mar Athanasius College of Engineering, Kerala

⭐ Acknowledgements

Built as a personal learning & productivity project using Flask.

