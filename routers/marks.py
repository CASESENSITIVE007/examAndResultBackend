from fastapi import APIRouter, Depends, HTTPException
import psycopg.rows
from database import get_db
from auth import get_current_user, require_roles
from schemas import MarksUpload, VerifyMarksRequest, SubmitForReviewRequest

router = APIRouter()


@router.post("")
def upload_marks(
    data: MarksUpload,
    db=Depends(get_db),
    current_user=Depends(require_roles("faculty")),
):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        # Block re-upload if any marks for this entry are already verified
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM marks WHERE exam_entry_id = %s AND is_verified = TRUE",
            (data.exam_entry_id,),
        )
        if cur.fetchone()["cnt"] > 0:
            raise HTTPException(
                403, "Cannot update marks that have already been verified by the examination office."
            )

        for m in data.marks_list:
            cur.execute(
                """INSERT INTO marks
                       (exam_entry_id, student_id, raw_marks, exam_type, session, semester, uploaded_by)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (exam_entry_id, student_id)
                   DO UPDATE SET raw_marks    = EXCLUDED.raw_marks,
                                 uploaded_by  = EXCLUDED.uploaded_by,
                                 is_verified  = FALSE,
                                 is_submitted = FALSE""",
                (
                    data.exam_entry_id,
                    m.student_id,
                    m.raw_marks,
                    data.exam_type,
                    data.session,
                    data.semester,
                    current_user["user_id"],
                ),
            )
        db.commit()
    return {"message": f"Marks saved for {len(data.marks_list)} students"}


@router.get("/status")
def get_marks_status(
    subject_code: str,
    session: str,
    semester: int,
    db=Depends(get_db),
    current_user=Depends(require_roles("faculty")),
):
    """Return save/submitted/verified counts for both exam types for a subject."""
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            """
            SELECT m.exam_type,
                   COUNT(*)                  AS count,
                   BOOL_AND(m.is_submitted)  AS all_submitted,
                   BOOL_AND(m.is_verified)   AS all_verified
            FROM marks m
            JOIN exam_entries ee ON m.exam_entry_id = ee.entry_id
            WHERE ee.subject_code = %s AND m.session = %s AND m.semester = %s
              AND m.exam_type IN ('sessional', 'end_semester')
            GROUP BY m.exam_type
            """,
            (subject_code, session, semester),
        )
        rows = cur.fetchall()

    result = {
        "sessional":    {"count": 0, "submitted": False, "verified": False},
        "end_semester": {"count": 0, "submitted": False, "verified": False},
    }
    for r in rows:
        result[r["exam_type"]] = {
            "count":     int(r["count"]),
            "submitted": r["all_submitted"] or False,
            "verified":  r["all_verified"]  or False,
        }
    return result


@router.post("/submit-for-review")
def submit_for_review(
    data: SubmitForReviewRequest,
    db=Depends(get_db),
    current_user=Depends(require_roles("faculty")),
):
    """Mark all sessional + end-semester marks for a subject as submitted for office review."""
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            """
            SELECT COUNT(DISTINCT m.exam_type) AS type_count
            FROM marks m
            JOIN exam_entries ee ON m.exam_entry_id = ee.entry_id
            WHERE ee.subject_code = %s AND m.session = %s AND m.semester = %s
              AND m.exam_type IN ('sessional', 'end_semester')
            """,
            (data.subject_code, data.session, data.semester),
        )
        if cur.fetchone()["type_count"] < 2:
            raise HTTPException(
                400,
                "Both sessional and end-semester marks must be saved before submitting for review.",
            )

        cur.execute(
            """
            UPDATE marks SET is_submitted = TRUE
            FROM exam_entries ee
            WHERE marks.exam_entry_id = ee.entry_id
              AND ee.subject_code  = %s
              AND marks.session    = %s
              AND marks.semester   = %s
              AND marks.is_verified = FALSE
            """,
            (data.subject_code, data.session, data.semester),
        )
        db.commit()
    return {"message": "Marks submitted for review. The examination office will verify them shortly."}


@router.get("")
def get_marks(
    session: str = None,
    semester: int = None,
    exam_type: str = None,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        query = """
            SELECT m.*, s.enrollment_no, s.full_name AS student_name,
                   ee.subject_code, ee.subject_name, ee.exam_date
            FROM marks m
            JOIN students s ON m.student_id = s.student_id
            JOIN exam_entries ee ON m.exam_entry_id = ee.entry_id
            WHERE 1=1
        """
        params = []
        if session:
            query += " AND m.session = %s"
            params.append(session)
        if semester:
            query += " AND m.semester = %s"
            params.append(semester)
        if exam_type:
            query += " AND m.exam_type = %s"
            params.append(exam_type)
        cur.execute(query + " ORDER BY ee.exam_date, s.enrollment_no", params)
        return cur.fetchall()


@router.get("/pending")
def get_pending_marks(
    db=Depends(get_db),
    current_user=Depends(require_roles("office_staff", "coe")),
):
    """Return all submitted-but-unverified marks — both sessional and end-semester."""
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        query = """
            SELECT m.*, s.enrollment_no, s.full_name AS student_name, s.department,
                   ee.subject_code, ee.subject_name, ee.exam_date,
                   u.full_name AS uploaded_by_name
            FROM marks m
            JOIN students s ON m.student_id = s.student_id
            JOIN exam_entries ee ON m.exam_entry_id = ee.entry_id
            JOIN users u ON m.uploaded_by = u.user_id
            WHERE m.is_submitted = TRUE AND m.is_verified = FALSE
        """
        params = []
        if current_user["role"] == "office_staff" and current_user.get("department"):
            query += " AND s.department = %s"
            params.append(current_user["department"])
        query += " ORDER BY ee.subject_code, m.exam_type, s.enrollment_no"
        cur.execute(query, params)
        return cur.fetchall()


@router.get("/history")
def get_marks_history(
    session: str = None,
    exam_type: str = None,
    db=Depends(get_db),
    current_user=Depends(require_roles("office_staff", "coe")),
):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        query = """
            SELECT m.mark_id, m.session, m.semester, m.exam_type,
                   m.raw_marks, m.is_verified,
                   s.enrollment_no, s.full_name AS student_name, s.department,
                   ee.subject_code, ee.subject_name, ee.exam_date,
                   u_up.full_name  AS uploaded_by_name,
                   u_ver.full_name AS verified_by_name
            FROM marks m
            JOIN students s      ON m.student_id    = s.student_id
            JOIN exam_entries ee  ON m.exam_entry_id = ee.entry_id
            JOIN users u_up       ON m.uploaded_by   = u_up.user_id
            LEFT JOIN users u_ver ON m.verified_by   = u_ver.user_id
            WHERE m.is_verified = TRUE
        """
        params = []
        if current_user["role"] == "office_staff" and current_user.get("department"):
            query += " AND s.department = %s"
            params.append(current_user["department"])
        if session:
            query += " AND m.session = %s"
            params.append(session)
        if exam_type:
            query += " AND m.exam_type = %s"
            params.append(exam_type)
        query += " ORDER BY m.session DESC, ee.subject_code, s.enrollment_no"
        cur.execute(query, params)
        return cur.fetchall()


@router.put("/verify")
def verify_marks(
    data: VerifyMarksRequest,
    db=Depends(get_db),
    current_user=Depends(require_roles("office_staff")),
):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        if current_user.get("department"):
            cur.execute(
                """SELECT COUNT(*) AS cnt FROM marks m
                   JOIN students s ON m.student_id = s.student_id
                   WHERE m.mark_id = ANY(%s::int[]) AND s.department != %s""",
                (data.mark_ids, current_user["department"]),
            )
            if cur.fetchone()["cnt"] > 0:
                raise HTTPException(403, "Cannot verify marks outside your department")
        cur.execute(
            "UPDATE marks SET is_verified = TRUE, verified_by = %s WHERE mark_id = ANY(%s::int[])",
            (current_user["user_id"], data.mark_ids),
        )
        db.commit()
    return {"message": f"Verified {len(data.mark_ids)} mark entries"}
