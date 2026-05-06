"""
Run once to create tables and seed demo data.
Usage: python init_db.py
"""
import os
import psycopg
from dotenv import load_dotenv
from auth import get_password_hash

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/rms_db")

DDL = """
CREATE TABLE IF NOT EXISTS users (
    user_id       SERIAL PRIMARY KEY,
    username      VARCHAR(50)  UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20)  NOT NULL
                  CHECK (role IN ('student','faculty','dept_admin','office_staff','coe','hod','dean','registrar','vc')),
    full_name     VARCHAR(100) NOT NULL,
    email         VARCHAR(100),
    department    VARCHAR(50),
    created_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS students (
    student_id       SERIAL PRIMARY KEY,
    user_id          INTEGER UNIQUE REFERENCES users(user_id),
    enrollment_no    VARCHAR(20) UNIQUE NOT NULL,
    full_name        VARCHAR(100) NOT NULL,
    department       VARCHAR(50) NOT NULL,
    current_semester INTEGER DEFAULT 4,
    session          VARCHAR(10) DEFAULT '2025-26',
    cgpa             NUMERIC(4,2) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS datesheets (
    sheet_id    SERIAL PRIMARY KEY,
    exam_type   VARCHAR(20) NOT NULL CHECK (exam_type IN ('sessional','end_semester')),
    session     VARCHAR(10) NOT NULL,
    semester    INTEGER     NOT NULL,
    department  VARCHAR(50) NOT NULL,
    created_by  INTEGER REFERENCES users(user_id),
    is_published BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS exam_entries (
    entry_id     SERIAL PRIMARY KEY,
    sheet_id     INTEGER REFERENCES datesheets(sheet_id) ON DELETE CASCADE,
    subject_code VARCHAR(20)  NOT NULL,
    subject_name VARCHAR(100) NOT NULL,
    exam_date    DATE         NOT NULL,
    time_slot    VARCHAR(30)  NOT NULL
);

CREATE TABLE IF NOT EXISTS marks (
    mark_id       SERIAL PRIMARY KEY,
    exam_entry_id INTEGER REFERENCES exam_entries(entry_id),
    student_id    INTEGER REFERENCES students(student_id),
    raw_marks     NUMERIC(5,2) NOT NULL,
    exam_type     VARCHAR(20)  NOT NULL,
    session       VARCHAR(10)  NOT NULL,
    semester      INTEGER      NOT NULL,
    is_verified   BOOLEAN DEFAULT FALSE,
    uploaded_by   INTEGER REFERENCES users(user_id),
    verified_by   INTEGER REFERENCES users(user_id),
    uploaded_at   TIMESTAMP DEFAULT NOW(),
    UNIQUE (exam_entry_id, student_id)
);

CREATE TABLE IF NOT EXISTS results (
    result_id       SERIAL PRIMARY KEY,
    student_id      INTEGER REFERENCES students(student_id),
    session         VARCHAR(10)  NOT NULL,
    semester        INTEGER      NOT NULL,
    subject_code    VARCHAR(20)  NOT NULL,
    sessional_marks NUMERIC(5,2),
    end_sem_marks   NUMERIC(5,2),
    total_marks     NUMERIC(5,2),
    grade           VARCHAR(3),
    grade_point     INTEGER,
    status          VARCHAR(10),
    published_by    INTEGER REFERENCES users(user_id),
    published_at    TIMESTAMP DEFAULT NOW(),
    UNIQUE (student_id, session, semester, subject_code)
);

CREATE TABLE IF NOT EXISTS departments (
    dept_id    SERIAL PRIMARY KEY,
    dept_code  VARCHAR(20)  UNIQUE NOT NULL,
    dept_name  VARCHAR(100) NOT NULL,
    created_by INTEGER REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS courses (
    course_id   SERIAL PRIMARY KEY,
    course_code VARCHAR(20)  UNIQUE NOT NULL,
    course_name VARCHAR(100) NOT NULL,
    dept_code   VARCHAR(20)  REFERENCES departments(dept_code) ON DELETE SET NULL,
    semester    INTEGER      NOT NULL,
    credits     INTEGER      DEFAULT 4,
    created_by  INTEGER REFERENCES users(user_id),
    created_at  TIMESTAMP DEFAULT NOW()
);
"""





def main():
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            print("Creating tables…")
            cur.execute(DDL)

            print("Seeding staff users…")
            staff_ids = {}
            for username, password, role, full_name, dept in SEED_USERS:
                cur.execute(
                    """INSERT INTO users (username, password_hash, role, full_name, department)
                       VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (username) DO NOTHING
                       RETURNING user_id""",
                    (username, get_password_hash(password), role, full_name, dept),
                )
                row = cur.fetchone()
                if row:
                    staff_ids[username] = row[0]
                    print(f"  Created {role}: {username} / {password}")

            print("Seeding student users & student records…")
            for enroll, name, dept, sem, session in SEED_STUDENTS:
                uname = enroll.lower().replace("-", "")
                cur.execute(
                    """INSERT INTO users (username, password_hash, role, full_name, department)
                       VALUES (%s, %s, 'student', %s, %s)
                       ON CONFLICT (username) DO NOTHING
                       RETURNING user_id""",
                    (uname, get_password_hash("student123"), name, dept),
                )
                row = cur.fetchone()
                if row:
                    uid = row[0]
                    cur.execute(
                        """INSERT INTO students (user_id, enrollment_no, full_name, department, current_semester, session)
                           VALUES (%s, %s, %s, %s, %s, %s)
                           ON CONFLICT (enrollment_no) DO NOTHING""",
                        (uid, enroll, name, dept, sem, session),
                    )
                    print(f"  Student: {uname} / student123  ({enroll})")

            print("Seeding departments…")
            for dept_code, dept_name in SEED_DEPARTMENTS:
                cur.execute(
                    """INSERT INTO departments (dept_code, dept_name)
                       VALUES (%s, %s)
                       ON CONFLICT (dept_code) DO NOTHING""",
                    (dept_code, dept_name),
                )
                print(f"  Department: {dept_code} — {dept_name}")

        conn.commit()
    print("\nDatabase initialised successfully!")
    print("\nDemo logins:")
    print("  faculty1 / password123   → Faculty")
    print("  dept_admin / password123 → Department Admin")
    print("  office1 / password123    → Office Staff")
    print("  coe1 / password123       → Controller of Examinations")
    print("  hod1 / password123       → Head of Department")
    print("  dean1 / password123      → Dean")
    print("  22mca01 / student123     → Student (Amit Kumar)")


if __name__ == "__main__":
    main()
