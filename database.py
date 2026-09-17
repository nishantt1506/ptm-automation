from datetime import date, time, datetime, timedelta
from pathlib import Path

import streamlit as st

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Date,
    Time,
    DateTime,
    ForeignKey,
    Text,
    Boolean,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker


# ============================================================
# DATABASE LOCATION
# ============================================================
#
# Local Mac:
#     ./ptm.db
#
# Streamlit Cloud:
#     /tmp/ptm.db
#
# This allows the same code to work both locally and in the
# deployed Streamlit application.
#
# IMPORTANT:
# SQLite in /tmp is runtime storage. It is suitable for a
# demonstration, but not permanent production storage.
# ============================================================

if st.runtime.exists():
    DB_PATH = Path("/tmp/ptm.db")
else:
    BASE_DIR = Path(__file__).resolve().parent
    DB_PATH = BASE_DIR / "ptm.db"


# ============================================================
# SQLALCHEMY ENGINE
# ============================================================

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)


SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


Base = declarative_base()


# ============================================================
# TEACHER
# ============================================================

class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True)

    name = Column(
        String,
        nullable=False,
    )

    subject = Column(
        String,
        nullable=False,
    )

    class_name = Column(
        String,
        nullable=False,
    )

    section = Column(
        String,
        nullable=False,
    )

    room = Column(
        String,
        nullable=False,
    )

    students = relationship(
        "Student",
        back_populates="teacher",
    )


# ============================================================
# PARENT
# ============================================================

class Parent(Base):
    __tablename__ = "parents"

    id = Column(Integer, primary_key=True)

    name = Column(
        String,
        nullable=False,
    )

    phone = Column(
        String,
        nullable=False,
    )

    email = Column(
        String,
        nullable=False,
    )

    students = relationship(
        "Student",
        back_populates="parent",
    )


# ============================================================
# STUDENT
# ============================================================

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True)

    name = Column(
        String,
        nullable=False,
    )

    class_name = Column(
        String,
        nullable=False,
    )

    section = Column(
        String,
        nullable=False,
    )

    attendance_pct = Column(
        Integer,
        default=90,
    )

    academic_level = Column(
        String,
        default="Good",
    )

    parent_id = Column(
        Integer,
        ForeignKey("parents.id"),
        nullable=False,
    )

    teacher_id = Column(
        Integer,
        ForeignKey("teachers.id"),
        nullable=False,
    )

    parent = relationship(
        "Parent",
        back_populates="students",
    )

    teacher = relationship(
        "Teacher",
        back_populates="students",
    )

    ptms = relationship(
        "PTM",
        back_populates="student",
    )


# ============================================================
# PTM
# ============================================================

class PTM(Base):
    __tablename__ = "ptms"

    id = Column(
        Integer,
        primary_key=True,
    )

    student_id = Column(
        Integer,
        ForeignKey("students.id"),
        nullable=False,
    )

    teacher_id = Column(
        Integer,
        ForeignKey("teachers.id"),
        nullable=False,
    )

    meeting_date = Column(
        Date,
        nullable=False,
    )

    meeting_time = Column(
        Time,
        nullable=False,
    )

    room = Column(
        String,
        nullable=False,
    )

    status = Column(
        String,
        default="Scheduled",
    )

    parent_confirmed = Column(
        Boolean,
        default=True,
    )

    arrived_at = Column(
        DateTime,
        nullable=True,
    )

    completed_at = Column(
        DateTime,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.now,
    )

    student = relationship(
        "Student",
        back_populates="ptms",
    )

    teacher = relationship(
        "Teacher",
    )

    remark = relationship(
        "Remark",
        back_populates="ptm",
        uselist=False,
    )

    notifications = relationship(
        "Notification",
        back_populates="ptm",
    )


# ============================================================
# REMARK
# ============================================================

class Remark(Base):
    __tablename__ = "remarks"

    id = Column(
        Integer,
        primary_key=True,
    )

    ptm_id = Column(
        Integer,
        ForeignKey("ptms.id"),
        unique=True,
        nullable=False,
    )

    raw_note = Column(
        Text,
        default="",
    )

    academic = Column(
        Text,
        default="",
    )

    participation = Column(
        Text,
        default="",
    )

    behaviour = Column(
        Text,
        default="",
    )

    attendance = Column(
        Text,
        default="",
    )

    assignments = Column(
        Text,
        default="",
    )

    recommendation = Column(
        Text,
        default="",
    )

    ai_generated = Column(
        Boolean,
        default=False,
    )

    teacher_approved = Column(
        Boolean,
        default=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.now,
    )

    ptm = relationship(
        "PTM",
        back_populates="remark",
    )


# ============================================================
# NOTIFICATION
# ============================================================

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(
        Integer,
        primary_key=True,
    )

    ptm_id = Column(
        Integer,
        ForeignKey("ptms.id"),
        nullable=False,
    )

    channel = Column(
        String,
        default="Demo",
    )

    recipient = Column(
        String,
        nullable=False,
    )

    message = Column(
        Text,
        nullable=False,
    )

    sent_at = Column(
        DateTime,
        default=datetime.now,
    )

    status = Column(
        String,
        default="Sent",
    )

    ptm = relationship(
        "PTM",
        back_populates="notifications",
    )


# ============================================================
# AVAILABLE PTM SLOTS
# ============================================================

SLOT_TIMES = [
    time(9, 0),
    time(9, 30),
    time(10, 0),
    time(10, 30),
    time(11, 0),
    time(11, 30),
    time(12, 0),
    time(12, 30),
    time(14, 0),
    time(14, 30),
    time(15, 0),
    time(15, 30),
]


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def init_db():
    """
    Create all database tables if they don't already exist.
    """
    Base.metadata.create_all(engine)


# ============================================================
# SEED DEMO DATA
# ============================================================

def seed_db(force=False):
    """
    Create the dummy school data used by the demonstration.

    force=True:
        Deletes the existing demo data and recreates it.

    force=False:
        Keeps the existing database if data already exists.
    """

    init_db()

    db = SessionLocal()

    try:

        # ----------------------------------------------------
        # FORCE RESET
        # ----------------------------------------------------

        if force:

            db.query(Notification).delete()
            db.query(Remark).delete()
            db.query(PTM).delete()
            db.query(Student).delete()
            db.query(Parent).delete()
            db.query(Teacher).delete()

            db.commit()

        # ----------------------------------------------------
        # DON'T DUPLICATE SEED DATA
        # ----------------------------------------------------

        if db.query(Teacher).count() > 0:
            return

        # ----------------------------------------------------
        # TEACHERS
        # ----------------------------------------------------

        teachers = [
            Teacher(
                name="Priya Mehta",
                subject="Mathematics",
                class_name="8",
                section="B",
                room="204",
            ),

            Teacher(
                name="Rahul Singh",
                subject="Science",
                class_name="8",
                section="A",
                room="202",
            ),

            Teacher(
                name="Neha Sharma",
                subject="English",
                class_name="9",
                section="A",
                room="201",
            ),

            Teacher(
                name="Arjun Kapoor",
                subject="Computer Science",
                class_name="9",
                section="B",
                room="203",
            ),
        ]

        db.add_all(teachers)
        db.flush()

        # ----------------------------------------------------
        # PARENTS
        # ----------------------------------------------------

        parents = [
            Parent(
                name="Rahul Sharma",
                phone="9876543210",
                email="rahul@example.com",
            ),

            Parent(
                name="Neha Verma",
                phone="9876543211",
                email="neha@example.com",
            ),

            Parent(
                name="Amit Kumar",
                phone="9876543212",
                email="amit@example.com",
            ),

            Parent(
                name="Pooja Gupta",
                phone="9876543213",
                email="pooja@example.com",
            ),

            Parent(
                name="Vikram Singh",
                phone="9876543214",
                email="vikram@example.com",
            ),

            Parent(
                name="Kavita Rao",
                phone="9876543215",
                email="kavita@example.com",
            ),
        ]

        db.add_all(parents)
        db.flush()

        # ----------------------------------------------------
        # STUDENTS
        # ----------------------------------------------------

        students = [

            Student(
                name="Aarav Sharma",
                class_name="8",
                section="B",
                attendance_pct=91,
                academic_level="Good",
                parent_id=parents[0].id,
                teacher_id=teachers[0].id,
            ),

            Student(
                name="Ananya Verma",
                class_name="8",
                section="B",
                attendance_pct=96,
                academic_level="Very Good",
                parent_id=parents[1].id,
                teacher_id=teachers[0].id,
            ),

            Student(
                name="Rohan Kumar",
                class_name="8",
                section="A",
                attendance_pct=84,
                academic_level="Average",
                parent_id=parents[2].id,
                teacher_id=teachers[1].id,
            ),

            Student(
                name="Siya Gupta",
                class_name="9",
                section="A",
                attendance_pct=93,
                academic_level="Excellent",
                parent_id=parents[3].id,
                teacher_id=teachers[2].id,
            ),

            Student(
                name="Kabir Singh",
                class_name="9",
                section="B",
                attendance_pct=88,
                academic_level="Good",
                parent_id=parents[4].id,
                teacher_id=teachers[3].id,
            ),

            Student(
                name="Meera Rao",
                class_name="9",
                section="A",
                attendance_pct=79,
                academic_level="Needs Support",
                parent_id=parents[5].id,
                teacher_id=teachers[2].id,
            ),
        ]

        db.add_all(students)
        db.flush()

        # ----------------------------------------------------
        # DEMO PTMs
        # ----------------------------------------------------

        today = date.today()

        demo_dates = [
            today,
            today + timedelta(days=1),
            today + timedelta(days=2),
        ]

        demo_ptms = [

            PTM(
                student_id=students[0].id,
                teacher_id=teachers[0].id,
                meeting_date=demo_dates[0],
                meeting_time=time(11, 0),
                room="204",
                status="Completed",
                parent_confirmed=True,
                completed_at=datetime.now(),
            ),

            PTM(
                student_id=students[1].id,
                teacher_id=teachers[0].id,
                meeting_date=demo_dates[0],
                meeting_time=time(11, 30),
                room="204",
                status="Scheduled",
                parent_confirmed=True,
            ),

            PTM(
                student_id=students[2].id,
                teacher_id=teachers[1].id,
                meeting_date=demo_dates[0],
                meeting_time=time(12, 0),
                room="202",
                status="Missed",
                parent_confirmed=True,
            ),

            PTM(
                student_id=students[3].id,
                teacher_id=teachers[2].id,
                meeting_date=demo_dates[1],
                meeting_time=time(10, 0),
                room="201",
                status="Confirmed",
                parent_confirmed=True,
            ),

            PTM(
                student_id=students[4].id,
                teacher_id=teachers[3].id,
                meeting_date=demo_dates[1],
                meeting_time=time(14, 0),
                room="203",
                status="Scheduled",
                parent_confirmed=True,
            ),

            PTM(
                student_id=students[5].id,
                teacher_id=teachers[2].id,
                meeting_date=demo_dates[2],
                meeting_time=time(15, 0),
                room="201",
                status="Scheduled",
                parent_confirmed=True,
            ),
        ]

        db.add_all(demo_ptms)
        db.flush()

        # ----------------------------------------------------
        # DEMO AI REMARK
        # ----------------------------------------------------

        db.add(
            Remark(
                ptm_id=demo_ptms[0].id,

                raw_note=(
                    "Understands concepts well but does not participate much. "
                    "Attendance is okay. Needs to submit assignments on time."
                ),

                academic="Good conceptual understanding",

                participation="Needs improvement",

                behaviour="Positive",

                attendance="Satisfactory",

                assignments="Needs more consistency",

                recommendation=(
                    "Encourage classroom participation and timely "
                    "assignment submission."
                ),

                ai_generated=True,

                teacher_approved=True,
            )
        )

        # ----------------------------------------------------
        # DEMO NOTIFICATIONS
        # ----------------------------------------------------

        for ptm in demo_ptms:

            student = db.get(
                Student,
                ptm.student_id,
            )

            parent = db.get(
                Parent,
                student.parent_id,
            )

            teacher = db.get(
                Teacher,
                student.teacher_id,
            )

            message = (
                f"Dear {parent.name}, your PTM for {student.name} "
                f"is scheduled for "
                f"{ptm.meeting_date.strftime('%d %B %Y')} at "
                f"{ptm.meeting_time.strftime('%I:%M %p')} in Class "
                f"{student.class_name}-{student.section}, Room "
                f"{ptm.room}, with {teacher.name}."
            )

            db.add(
                Notification(
                    ptm_id=ptm.id,
                    recipient=parent.email,
                    message=message,
                    channel="Demo Email",
                    status="Sent",
                )
            )

        # ----------------------------------------------------
        # SAVE
        # ----------------------------------------------------

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()