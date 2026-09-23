from pydantic import BaseModel
from typing import Optional

class AttendanceUpdate(BaseModel):
    status: Optional[str] = None
    subject: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    section: Optional[str] = None
    branch_code: Optional[str] = None

class AttendanceManualCreate(BaseModel):
    roll_no: str
    subject: str
    date: Optional[str] = None
    time: Optional[str] = None
    status: str = "Present"
    section: Optional[str] = None
    branch_code: Optional[str] = None

class StudentProfileUpdate(BaseModel):
    name: Optional[str] = None
    branch_code: Optional[str] = None
    section: Optional[str] = None
    year: Optional[int] = None
    class_roll_no: Optional[str] = None
