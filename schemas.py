from pydantic import BaseModel
from typing import List, Optional
from datetime import date


class LoginRequest(BaseModel):
    username: str
    password: str


class DatesheetEntryCreate(BaseModel):
    subject_code: str
    subject_name: str
    exam_date: date
    time_slot: str


class DatesheetCreate(BaseModel):
    exam_type: str
    session: str
    semester: int
    department: str
    entries: List[DatesheetEntryCreate] = []


class MarksEntry(BaseModel):
    student_id: int
    raw_marks: float


class MarksUpload(BaseModel):
    exam_entry_id: int
    exam_type: str
    session: str
    semester: int
    marks_list: List[MarksEntry]


class VerifyMarksRequest(BaseModel):
    mark_ids: List[int]


class SubmitForReviewRequest(BaseModel):
    subject_code: str
    session: str
    semester: int


class PublishResultsRequest(BaseModel):
    session: str
    semester: int
    department: str


class DepartmentCreate(BaseModel):
    dept_code: str
    dept_name: str
    faculty_code: Optional[str] = None


class CourseCreate(BaseModel):
    course_code: str
    course_name: str
    dept_code: str


class SubjectCreate(BaseModel):
    subject_code: str
    subject_name: str
    course_code: str
    semester: int
    credits: int = 4


class AcademicFacultyCreate(BaseModel):
    faculty_code: str
    faculty_name: str


class FacultyCreate(BaseModel):
    username: str
    password: str
    full_name: str
    department: str
    email: Optional[str] = None
    faculty_type: Optional[str] = None


class StudentCreate(BaseModel):
    enrollment_no: str
    full_name: str
    department: str
    course: Optional[str] = None
    current_semester: int
    session: str


class StaffCreate(BaseModel):
    username: str
    password: str
    full_name: str
    role: str          # 'office_staff' or 'dept_admin'
    department: str    # dept_code
    email: Optional[str] = None
