from fastapi import APIRouter, Depends, HTTPException
import psycopg.rows
from database import get_db
from auth import get_current_user, require_roles, get_password_hash
from schemas import DepartmentCreate, CourseCreate, SubjectCreate, FacultyCreate, StudentCreate, AcademicFacultyCreate, StaffCreate

router = APIRouter()


# ── Departments (CoE manages) ────────────────────────────────────────────────

@router.post("/departments", status_code=201)
def create_department(
    data: DepartmentCreate,
    db=Depends(get_db),
    current_user=Depends(require_roles("coe")),
):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("SELECT dept_id FROM departments WHERE dept_code = %s", (data.dept_code.upper(),))
        if cur.fetchone():
            raise HTTPException(409, "Department code already exists")
        faculty_code = data.faculty_code.upper() if data.faculty_code else None
        cur.execute(
            """INSERT INTO departments (dept_code, dept_name, faculty_code, created_by)
               VALUES (%s, %s, %s, %s) RETURNING dept_id""",
            (data.dept_code.upper(), data.dept_name, faculty_code, current_user["user_id"]),
        )
        dept_id = cur.fetchone()["dept_id"]
        db.commit()
    return {"dept_id": dept_id, "message": "Department created"}


@router.get("/departments")
def list_departments(
    faculty_code: str = None,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        query = """
            SELECT d.*, u.full_name AS created_by_name, af.faculty_name
            FROM departments d
            LEFT JOIN users u ON d.created_by = u.user_id
            LEFT JOIN academic_faculties af ON d.faculty_code = af.faculty_code
            WHERE 1=1
        """
        params = []
        if faculty_code:
            query += " AND d.faculty_code = %s"
            params.append(faculty_code.upper())
        cur.execute(query + " ORDER BY d.faculty_code NULLS LAST, d.dept_code", params)
        return cur.fetchall()


# ── Courses (CoE + dept_admin manage) ────────────────────────────────────────

@router.post("/courses", status_code=201)
def create_course(
    data: CourseCreate,
    db=Depends(get_db),
    current_user=Depends(require_roles("coe", "dept_admin")),
):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("SELECT course_id FROM courses WHERE course_code = %s", (data.course_code.upper(),))
        if cur.fetchone():
            raise HTTPException(409, "Course code already exists")
        cur.execute("SELECT dept_id FROM departments WHERE dept_code = %s", (data.dept_code.upper(),))
        if not cur.fetchone():
            raise HTTPException(404, f"Department '{data.dept_code}' not found. Create it first.")
        cur.execute(
            """INSERT INTO courses (course_code, course_name, dept_code, created_by)
               VALUES (%s, %s, %s, %s) RETURNING course_id""",
            (data.course_code.upper(), data.course_name, data.dept_code.upper(),
             current_user["user_id"]),
        )
        course_id = cur.fetchone()["course_id"]
        db.commit()
    return {"course_id": course_id, "message": "Course created"}


@router.get("/courses")
def list_courses(
    dept_code: str = None,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        query = """
            SELECT c.*, d.dept_name
            FROM courses c
            LEFT JOIN departments d ON c.dept_code = d.dept_code
            WHERE 1=1
        """
        params = []
        if dept_code:
            query += " AND c.dept_code = %s"
            params.append(dept_code.upper())
        cur.execute(query + " ORDER BY c.dept_code, c.course_code", params)
        return cur.fetchall()


# ── Subjects (CoE + dept_admin manage) ───────────────────────────────────────

@router.post("/subjects", status_code=201)
def create_subject(
    data: SubjectCreate,
    db=Depends(get_db),
    current_user=Depends(require_roles("coe", "dept_admin")),
):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("SELECT subject_id FROM subjects WHERE subject_code = %s", (data.subject_code.upper(),))
        if cur.fetchone():
            raise HTTPException(409, "Subject code already exists")
        cur.execute("SELECT course_id FROM courses WHERE course_code = %s", (data.course_code.upper(),))
        if not cur.fetchone():
            raise HTTPException(404, f"Course '{data.course_code}' not found. Create it first.")
        cur.execute(
            """INSERT INTO subjects (subject_code, subject_name, course_code, semester, credits, created_by)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING subject_id""",
            (data.subject_code.upper(), data.subject_name, data.course_code.upper(),
             data.semester, data.credits, current_user["user_id"]),
        )
        subject_id = cur.fetchone()["subject_id"]
        db.commit()
    return {"subject_id": subject_id, "message": "Subject created"}


@router.get("/subjects")
def list_subjects(
    course_code: str = None,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        query = "SELECT * FROM subjects WHERE 1=1"
        params = []
        if course_code:
            query += " AND course_code = %s"
            params.append(course_code.upper())
        cur.execute(query + " ORDER BY semester, subject_code", params)
        return cur.fetchall()


@router.delete("/departments/{dept_code}", status_code=204)
def delete_department(
    dept_code: str,
    db=Depends(get_db),
    current_user=Depends(require_roles("coe")),
):
    with db.cursor() as cur:
        cur.execute("DELETE FROM departments WHERE dept_code = %s", (dept_code.upper(),))
        if cur.rowcount == 0:
            raise HTTPException(404, "Department not found")
        db.commit()


@router.delete("/courses/{course_id}", status_code=204)
def delete_course(
    course_id: int,
    db=Depends(get_db),
    current_user=Depends(require_roles("coe", "dept_admin")),
):
    with db.cursor() as cur:
        cur.execute("DELETE FROM courses WHERE course_id = %s", (course_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Course not found")
        db.commit()


@router.delete("/subjects/{subject_id}", status_code=204)
def delete_subject(
    subject_id: int,
    db=Depends(get_db),
    current_user=Depends(require_roles("coe", "dept_admin")),
):
    with db.cursor() as cur:
        cur.execute("DELETE FROM subjects WHERE subject_id = %s", (subject_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Subject not found")
        db.commit()


@router.delete("/faculty/{user_id}", status_code=204)
def delete_faculty(
    user_id: int,
    db=Depends(get_db),
    current_user=Depends(require_roles("coe")),
):
    with db.cursor() as cur:
        cur.execute("DELETE FROM users WHERE user_id = %s AND role = 'faculty'", (user_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Faculty member not found")
        db.commit()


@router.delete("/students/{student_id}", status_code=204)
def delete_student(
    student_id: int,
    db=Depends(get_db),
    current_user=Depends(require_roles("office_staff", "coe", "dept_admin")),
):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("SELECT user_id, department FROM students WHERE student_id = %s", (student_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Student not found")
        # office_staff and dept_admin can only remove students from their own department
        if current_user["role"] in ("dept_admin", "office_staff"):
            if (row["department"] or "").upper() != (current_user.get("department") or "").upper():
                raise HTTPException(403, "You can only remove students from your own department")
        user_id = row["user_id"]
        cur.execute("DELETE FROM marks WHERE student_id = %s", (student_id,))
        cur.execute("DELETE FROM results WHERE student_id = %s", (student_id,))
        cur.execute("DELETE FROM students WHERE student_id = %s", (student_id,))
        cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        db.commit()


# ── Academic Faculties (CoE manages) ─────────────────────────────────────────

@router.post("/academic-faculties", status_code=201)
def create_academic_faculty(
    data: AcademicFacultyCreate,
    db=Depends(get_db),
    current_user=Depends(require_roles("coe")),
):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("SELECT faculty_id FROM academic_faculties WHERE faculty_code = %s", (data.faculty_code.upper(),))
        if cur.fetchone():
            raise HTTPException(409, "Faculty code already exists")
        cur.execute(
            """INSERT INTO academic_faculties (faculty_code, faculty_name, created_by)
               VALUES (%s, %s, %s) RETURNING faculty_id""",
            (data.faculty_code.upper(), data.faculty_name, current_user["user_id"]),
        )
        faculty_id = cur.fetchone()["faculty_id"]
        db.commit()
    return {"faculty_id": faculty_id, "message": "Academic faculty created"}


@router.get("/academic-faculties")
def list_academic_faculties(db=Depends(get_db), current_user=Depends(get_current_user)):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            """SELECT af.*, u.full_name AS created_by_name
               FROM academic_faculties af
               LEFT JOIN users u ON af.created_by = u.user_id
               ORDER BY af.faculty_code"""
        )
        return cur.fetchall()


@router.delete("/academic-faculties/{faculty_code}", status_code=204)
def delete_academic_faculty(
    faculty_code: str,
    db=Depends(get_db),
    current_user=Depends(require_roles("coe")),
):
    with db.cursor() as cur:
        cur.execute("DELETE FROM academic_faculties WHERE faculty_code = %s", (faculty_code.upper(),))
        if cur.rowcount == 0:
            raise HTTPException(404, "Academic faculty not found")
        db.commit()


# ── Faculty (CoE creates) ────────────────────────────────────────────────────

@router.post("/faculty", status_code=201)
def create_faculty(
    data: FacultyCreate,
    db=Depends(get_db),
    current_user=Depends(require_roles("coe")),
):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("SELECT user_id FROM users WHERE username = %s", (data.username,))
        if cur.fetchone():
            raise HTTPException(409, "Username already exists")
        cur.execute(
            """INSERT INTO users (username, password_hash, role, full_name, email, department, faculty_type)
               VALUES (%s, %s, 'faculty', %s, %s, %s, %s) RETURNING user_id""",
            (data.username, get_password_hash(data.password),
             data.full_name, data.email, data.department, data.faculty_type),
        )
        user_id = cur.fetchone()["user_id"]
        db.commit()
    return {"user_id": user_id, "message": "Faculty created"}


@router.get("/faculty")
def list_faculty(
    db=Depends(get_db),
    current_user=Depends(require_roles("coe", "dept_admin", "hod")),
):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            """SELECT user_id, username, full_name, email, department, faculty_type, created_at
               FROM users WHERE role = 'faculty'
               ORDER BY faculty_type NULLS LAST, department, full_name"""
        )
        return cur.fetchall()


# ── Students (office_staff + coe create) ─────────────────────────────────────

@router.post("/students", status_code=201)
def create_student(
    data: StudentCreate,
    db=Depends(get_db),
    current_user=Depends(require_roles("office_staff", "coe", "dept_admin")),
):
    # office_staff and dept_admin can only add students to their own department
    if current_user["role"] in ("dept_admin", "office_staff"):
        if data.department.upper() != (current_user.get("department") or "").upper():
            raise HTTPException(403, "You can only add students to your own department")

    username = data.enrollment_no.lower().replace("-", "")
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            raise HTTPException(409, "A student with this enrollment number already exists")
        cur.execute(
            """INSERT INTO users (username, password_hash, role, full_name, department)
               VALUES (%s, %s, 'student', %s, %s) RETURNING user_id""",
            (username, get_password_hash("student123"), data.full_name, data.department),
        )
        user_id = cur.fetchone()["user_id"]
        cur.execute(
            """INSERT INTO students (user_id, enrollment_no, full_name, department, course, current_semester, session)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING student_id""",
            (user_id, data.enrollment_no, data.full_name,
             data.department, data.course, data.current_semester, data.session),
        )
        student_id = cur.fetchone()["student_id"]
        db.commit()
    return {
        "student_id": student_id,
        "username": username,
        "message": f"Student created. Login: {username} / student123",
    }


# ── Office Staff & Dept Admin (CoE manages) ──────────────────────────────────

@router.post("/staff", status_code=201)
def create_staff(
    data: StaffCreate,
    db=Depends(get_db),
    current_user=Depends(require_roles("coe")),
):
    if data.role not in ("office_staff", "dept_admin"):
        raise HTTPException(400, "Role must be 'office_staff' or 'dept_admin'")
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("SELECT user_id FROM users WHERE username = %s", (data.username,))
        if cur.fetchone():
            raise HTTPException(409, "Username already exists")
        cur.execute("SELECT dept_id FROM departments WHERE dept_code = %s", (data.department.upper(),))
        if not cur.fetchone():
            raise HTTPException(404, f"Department '{data.department}' not found")
        cur.execute(
            """INSERT INTO users (username, password_hash, role, full_name, email, department)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING user_id""",
            (data.username, get_password_hash(data.password),
             data.role, data.full_name, data.email, data.department.upper()),
        )
        user_id = cur.fetchone()["user_id"]
        db.commit()
    return {"user_id": user_id, "message": f"{data.role} account created"}


@router.get("/staff")
def list_staff(
    role: str = None,
    faculty_code: str = None,
    dept_code: str = None,
    db=Depends(get_db),
    current_user=Depends(require_roles("coe")),
):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        query = """
            SELECT u.user_id, u.username, u.full_name, u.email, u.role,
                   u.department, u.created_at,
                   d.dept_name, d.faculty_code,
                   af.faculty_name
            FROM users u
            LEFT JOIN departments d ON u.department = d.dept_code
            LEFT JOIN academic_faculties af ON d.faculty_code = af.faculty_code
            WHERE u.role IN ('office_staff', 'dept_admin')
        """
        params = []
        if role:
            query += " AND u.role = %s"
            params.append(role)
        if dept_code:
            query += " AND u.department = %s"
            params.append(dept_code.upper())
        if faculty_code:
            query += " AND d.faculty_code = %s"
            params.append(faculty_code.upper())
        cur.execute(query + " ORDER BY u.role, d.faculty_code, u.department, u.full_name", params)
        return cur.fetchall()


@router.delete("/staff/{user_id}", status_code=204)
def delete_staff(
    user_id: int,
    db=Depends(get_db),
    current_user=Depends(require_roles("coe")),
):
    with db.cursor() as cur:
        cur.execute(
            "DELETE FROM users WHERE user_id = %s AND role IN ('office_staff', 'dept_admin')",
            (user_id,),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Staff member not found")
        db.commit()


@router.get("/students")
def list_students(
    semester: int = None,
    department: str = None,
    course: str = None,
    db=Depends(get_db),
    current_user=Depends(require_roles("office_staff", "coe", "dept_admin", "hod")),
):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        query = "SELECT * FROM students WHERE 1=1"
        params = []
        if semester:
            query += " AND current_semester = %s"
            params.append(semester)
        # office_staff and dept_admin are always scoped to their own department
        if current_user["role"] in ("dept_admin", "office_staff"):
            query += " AND department = %s"
            params.append(current_user["department"])
        elif department:
            query += " AND department = %s"
            params.append(department)
        if course:
            query += " AND course = %s"
            params.append(course)
        cur.execute(query + " ORDER BY enrollment_no", params)
        return cur.fetchall()
