from fastapi import APIRouter, Depends, HTTPException
import psycopg.rows
from database import get_db
from auth import get_current_user, require_roles
from schemas import PublishResultsRequest

router = APIRouter()

ADMIN_ROLES = ("hod", "dean", "registrar", "vc", "dept_admin", "coe")


def _grade_from_total(total: float):
    if total >= 90:
        return "O", 10
    if total >= 80:
        return "A+", 9
    if total >= 70:
        return "A", 8
    if total >= 60:
        return "B+", 7
    if total >= 50:
        return "B", 6
    if total >= 40:
        return "C", 5
    return "F", 0


@router.post("/publish")
def publish_results(
    data: PublishResultsRequest,
    db=Depends(get_db),
    current_user=Depends(require_roles("coe")),
):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            "SELECT student_id, enrollment_no, full_name FROM students WHERE department = %s AND current_semester = %s",
            (data.department, data.semester),
        )
        students = cur.fetchall()
        if not students:
            raise HTTPException(404, "No students found for given department/semester")

        inserted = 0
        for student in students:
            sid = student["student_id"]

            cur.execute(
                """SELECT m.raw_marks, ee.subject_code, ee.subject_name
                   FROM marks m
                   JOIN exam_entries ee ON m.exam_entry_id = ee.entry_id
                   WHERE m.student_id = %s AND m.session = %s AND m.semester = %s
                     AND m.exam_type = 'end_semester' AND m.is_verified = TRUE""",
                (sid, data.session, data.semester),
            )
            end_sem = {r["subject_code"]: r for r in cur.fetchall()}

            cur.execute(
                """SELECT m.raw_marks, ee.subject_code
                   FROM marks m
                   JOIN exam_entries ee ON m.exam_entry_id = ee.entry_id
                   WHERE m.student_id = %s AND m.session = %s AND m.semester = %s
                     AND m.exam_type = 'sessional' AND m.is_verified = TRUE""",
                (sid, data.session, data.semester),
            )
            sessional = {r["subject_code"]: float(r["raw_marks"]) for r in cur.fetchall()}

            grade_points = []
            for subj_code, end_data in end_sem.items():
                sess_marks = sessional.get(subj_code, 0.0)
                end_marks = float(end_data["raw_marks"])
                total = sess_marks + end_marks
                grade, gp = _grade_from_total(total)

                cur.execute(
                    """INSERT INTO results
                           (student_id, session, semester, subject_code,
                            sessional_marks, end_sem_marks, total_marks,
                            grade, grade_point, status, published_by)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (student_id, session, semester, subject_code)
                       DO UPDATE SET
                           sessional_marks = EXCLUDED.sessional_marks,
                           end_sem_marks   = EXCLUDED.end_sem_marks,
                           total_marks     = EXCLUDED.total_marks,
                           grade           = EXCLUDED.grade,
                           grade_point     = EXCLUDED.grade_point,
                           status          = EXCLUDED.status,
                           published_by    = EXCLUDED.published_by,
                           published_at    = NOW()""",
                    (
                        sid, data.session, data.semester, subj_code,
                        sess_marks, end_marks, total,
                        grade, gp, "Pass" if gp > 0 else "Fail",
                        current_user["user_id"],
                    ),
                )
                grade_points.append(gp)
                inserted += 1

            if grade_points:
                cgpa = round(sum(grade_points) / len(grade_points), 2)
                cur.execute(
                    "UPDATE students SET cgpa = %s WHERE student_id = %s",
                    (cgpa, sid),
                )

        db.commit()

    if inserted == 0:
        raise HTTPException(
            400,
            "No results were published. Make sure end-semester marks exist and are verified "
            f"for session={data.session}, semester={data.semester}, department={data.department}."
        )
    return {
        "message": f"Results published for {len(students)} students ({inserted} subject results)"
    }


@router.get("/published")
def get_published_results(
    session: str = None,
    semester: int = None,
    department: str = None,
    faculty: str = None,
    course_code: str = None,
    subject_code: str = None,
    enrollment_no: str = None,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        query = """
            SELECT s.enrollment_no, s.full_name, s.department,
                   r.session, r.semester, r.subject_code,
                   r.sessional_marks, r.end_sem_marks, r.total_marks,
                   r.grade, r.grade_point, r.status, r.published_at
            FROM results r
            JOIN students s ON r.student_id = s.student_id
            LEFT JOIN departments d ON s.department = d.dept_code
            LEFT JOIN subjects sub ON r.subject_code = sub.subject_code
            WHERE r.published_at IS NOT NULL
        """
        params = []
        if session:
            query += " AND r.session = %s"
            params.append(session)
        if semester:
            query += " AND r.semester = %s"
            params.append(semester)
        if department:
            query += " AND s.department = %s"
            params.append(department)
        if faculty:
            query += " AND d.faculty_code = %s"
            params.append(faculty)
        if course_code:
            query += " AND sub.course_code = %s"
            params.append(course_code)
        if subject_code:
            query += " AND r.subject_code = %s"
            params.append(subject_code)
        if enrollment_no:
            query += " AND s.enrollment_no = %s"
            params.append(enrollment_no)

        query += " ORDER BY r.session DESC, s.department, r.semester, s.enrollment_no, r.subject_code"
        cur.execute(query, params)
        rows = cur.fetchall()

    total  = len(rows)
    passed = sum(1 for r in rows if r["status"] == "Pass")
    return {
        "total":   total,
        "passed":  passed,
        "failed":  total - passed,
        "results": rows,
    }


@router.get("/me")
def get_my_results(db=Depends(get_db), current_user=Depends(require_roles("student"))):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("SELECT * FROM students WHERE user_id = %s", (current_user["user_id"],))
        student = cur.fetchone()
        if not student:
            raise HTTPException(404, "Student record not found")

        cur.execute(
            """SELECT * FROM results WHERE student_id = %s
               ORDER BY session, semester, subject_code""",
            (student["student_id"],),
        )
        results = cur.fetchall()

    return {"student": student, "results": results, "cgpa": student["cgpa"]}


@router.get("/department")
def get_department_results(
    session: str = None,
    semester: int = None,
    department: str = None,
    db=Depends(get_db),
    current_user=Depends(require_roles(*ADMIN_ROLES)),
):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        query = """
            SELECT s.student_id, s.enrollment_no, s.full_name, s.department,
                   s.current_semester, s.cgpa,
                   COUNT(r.result_id) AS total_subjects,
                   COUNT(CASE WHEN r.status = 'Pass' THEN 1 END) AS passed_subjects,
                   COUNT(CASE WHEN r.status = 'Fail' THEN 1 END) AS failed_subjects
            FROM students s
            LEFT JOIN results r ON s.student_id = r.student_id
        """
        conditions, params = [], []
        if session:
            conditions.append("r.session = %s")
            params.append(session)
        if semester:
            conditions.append("r.semester = %s")
            params.append(semester)
        if department:
            conditions.append("s.department = %s")
            params.append(department)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " GROUP BY s.student_id ORDER BY s.cgpa DESC NULLS LAST"

        cur.execute(query, params)
        rows = cur.fetchall()

    for r in rows:
        r["overall_status"] = "Pass" if (r["failed_subjects"] or 0) == 0 and (r["total_subjects"] or 0) > 0 else "Fail"

    total = len(rows)
    passed = sum(1 for r in rows if r["overall_status"] == "Pass")
    avg_cgpa = round(sum(r["cgpa"] or 0 for r in rows) / total, 2) if total else 0

    return {
        "summary": {
            "total": total,
            "passed": passed,
            "pass_percentage": round(passed / total * 100, 1) if total else 0,
            "avg_cgpa": avg_cgpa,
        },
        "students": rows,
    }
