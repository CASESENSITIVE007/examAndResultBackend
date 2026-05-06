from fastapi import APIRouter, Depends
import psycopg.rows
from database import get_db
from auth import require_roles

router = APIRouter()

ALL_STAFF = ("faculty", "dept_admin", "coe", "office_staff", "hod", "dean", "registrar", "vc")


@router.get("/students")
def get_students(
    semester: int = None,
    department: str = None,
    course: str = None,
    db=Depends(get_db),
    current_user=Depends(require_roles(*ALL_STAFF)),
):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        query = "SELECT * FROM students WHERE 1=1"
        params = []
        if semester:
            query += " AND current_semester = %s"
            params.append(semester)
        if department:
            query += " AND department = %s"
            params.append(department)
        if course:
            query += " AND course = %s"
            params.append(course)
        cur.execute(query + " ORDER BY enrollment_no", params)
        return cur.fetchall()
