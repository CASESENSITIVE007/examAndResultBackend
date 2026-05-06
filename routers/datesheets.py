from fastapi import APIRouter, Depends, HTTPException
import psycopg.rows
from database import get_db
from auth import get_current_user, require_roles
from schemas import DatesheetCreate

router = APIRouter()


@router.post("", status_code=201)
def create_datesheet(
    data: DatesheetCreate,
    db=Depends(get_db),
    current_user=Depends(require_roles("dept_admin", "coe")),
):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            """INSERT INTO datesheets (exam_type, session, semester, department, created_by)
               VALUES (%s, %s, %s, %s, %s) RETURNING sheet_id""",
            (data.exam_type, data.session, data.semester, data.department, current_user["user_id"]),
        )
        sheet_id = cur.fetchone()["sheet_id"]

        for e in data.entries:
            cur.execute(
                """INSERT INTO exam_entries (sheet_id, subject_code, subject_name, exam_date, time_slot)
                   VALUES (%s, %s, %s, %s, %s)""",
                (sheet_id, e.subject_code, e.subject_name, e.exam_date, e.time_slot),
            )
        db.commit()
    return {"sheet_id": sheet_id, "message": "Datesheet created successfully"}


@router.get("")
def list_datesheets(db=Depends(get_db), current_user=Depends(get_current_user)):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            """SELECT d.*, u.full_name AS created_by_name
               FROM datesheets d
               JOIN users u ON d.created_by = u.user_id
               ORDER BY d.created_at DESC"""
        )
        sheets = cur.fetchall()
        for sheet in sheets:
            cur.execute(
                "SELECT * FROM exam_entries WHERE sheet_id = %s ORDER BY exam_date",
                (sheet["sheet_id"],),
            )
            sheet["entries"] = cur.fetchall()
    return sheets


@router.get("/{sheet_id}")
def get_datesheet(sheet_id: int, db=Depends(get_db), current_user=Depends(get_current_user)):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("SELECT * FROM datesheets WHERE sheet_id = %s", (sheet_id,))
        sheet = cur.fetchone()
        if not sheet:
            raise HTTPException(404, "Datesheet not found")
        cur.execute(
            "SELECT * FROM exam_entries WHERE sheet_id = %s ORDER BY exam_date",
            (sheet_id,),
        )
        sheet["entries"] = cur.fetchall()
    return sheet


@router.post("/{sheet_id}/publish")
def publish_datesheet(
    sheet_id: int,
    db=Depends(get_db),
    current_user=Depends(require_roles("dept_admin", "coe")),
):
    with db.cursor() as cur:
        cur.execute(
            "UPDATE datesheets SET is_published = TRUE WHERE sheet_id = %s",
            (sheet_id,),
        )
        db.commit()
    return {"message": "Datesheet published successfully"}
