import psycopg2
import os

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_db():
    return psycopg2.connect(
        DATABASE_URL,
        sslmode="require"
    )


def init_db():
    db = get_db()
    cur = db.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS semesters (
        id SERIAL PRIMARY KEY,
        name TEXT,
        is_active BOOLEAN DEFAULT FALSE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        name TEXT,
        roll_no TEXT,
        semester_id INTEGER REFERENCES semesters(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS subjects (
        id SERIAL PRIMARY KEY,
        name TEXT,
        semester_id INTEGER REFERENCES semesters(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS class_log (
        id SERIAL PRIMARY KEY,
        date DATE,
        subject_id INTEGER REFERENCES subjects(id),
        hours INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id SERIAL PRIMARY KEY,
        class_id INTEGER REFERENCES class_log(id) ON DELETE CASCADE,
        student_id INTEGER REFERENCES students(id) ON DELETE CASCADE,
        attended BOOLEAN
    )
    """)

    db.commit()
    cur.close()
    db.close()

