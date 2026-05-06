import os
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/rms_db")

pool = ConnectionPool(DATABASE_URL, min_size=2, max_size=10, open=False)


NEW_TABLES_DDL = """
ALTER TABLE students ADD COLUMN IF NOT EXISTS course VARCHAR(50);

CREATE TABLE IF NOT EXISTS academic_faculties (
    faculty_id   SERIAL PRIMARY KEY,
    faculty_code VARCHAR(20)  UNIQUE NOT NULL,
    faculty_name VARCHAR(100) NOT NULL,
    created_by   INTEGER REFERENCES users(user_id),
    created_at   TIMESTAMP DEFAULT NOW()
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS faculty_type VARCHAR(50);

CREATE TABLE IF NOT EXISTS departments (
    dept_id      SERIAL PRIMARY KEY,
    dept_code    VARCHAR(20)  UNIQUE NOT NULL,
    dept_name    VARCHAR(100) NOT NULL,
    faculty_code VARCHAR(20)  REFERENCES academic_faculties(faculty_code) ON DELETE SET NULL,
    created_by   INTEGER REFERENCES users(user_id),
    created_at   TIMESTAMP DEFAULT NOW()
);

ALTER TABLE departments ADD COLUMN IF NOT EXISTS faculty_code VARCHAR(20) REFERENCES academic_faculties(faculty_code) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS courses (
    course_id   SERIAL PRIMARY KEY,
    course_code VARCHAR(20)  UNIQUE NOT NULL,
    course_name VARCHAR(100) NOT NULL,
    dept_code   VARCHAR(20)  REFERENCES departments(dept_code) ON DELETE SET NULL,
    created_by  INTEGER REFERENCES users(user_id),
    created_at  TIMESTAMP DEFAULT NOW()
);

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'courses' AND column_name = 'semester'
  ) THEN
    ALTER TABLE courses ALTER COLUMN semester DROP NOT NULL;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS subjects (
    subject_id   SERIAL PRIMARY KEY,
    subject_code VARCHAR(20)  UNIQUE NOT NULL,
    subject_name VARCHAR(100) NOT NULL,
    course_code  VARCHAR(20)  REFERENCES courses(course_code) ON DELETE CASCADE,
    semester     INTEGER      NOT NULL,
    credits      INTEGER      DEFAULT 4,
    created_by   INTEGER REFERENCES users(user_id),
    created_at   TIMESTAMP DEFAULT NOW()
);

ALTER TABLE marks ADD COLUMN IF NOT EXISTS is_submitted BOOLEAN DEFAULT FALSE;
"""


def init_pool():
    pool.open()


def run_migrations():
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(NEW_TABLES_DDL)
        conn.commit()


def get_db():
    with pool.connection() as conn:
        yield conn
