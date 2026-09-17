from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy.orm import joinedload

from database import (
    SessionLocal,
    Teacher,
    Student,
    PTM,
    Remark,
    Notification,
    init_db,
    seed_db,
)

from services import (
    find_available_slots,
    schedule_ptm,
    update_ptm_status,
    save_remark,
    ai_structure,
    format_time,
)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="PTM Automation System",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# DATABASE
# ============================================================

init_db()
seed_db()


def get_db():
    return SessionLocal()


# ============================================================
# HELPERS
# ============================================================

def status_badge(status):
    icons = {
        "Scheduled": "🟡",
        "Confirmed": "🟢",
        "Arrived": "🔵",
        "Completed": "✅",
        "Missed": "🔴",
        "Cancelled": "⚪",
    }
    return f"{icons.get(status, '⚪')} {status}"


def load_ptm(ptm_id):
    """
    Load one PTM with every relationship needed by the UI.
    This prevents DetachedInstanceError after the DB session closes.
    """
    db = get_db()

    try:
        ptm = (
            db.query(PTM)
            .options(
                joinedload(PTM.student)
                .joinedload(Student.teacher),

                joinedload(PTM.student)
                .joinedload(Student.parent),

                joinedload(PTM.teacher),

                joinedload(PTM.remark),
            )
            .filter(PTM.id == ptm_id)
            .first()
        )

        if not ptm:
            return None

        # Convert relationship values to plain Python data
        # before closing the session.
        data = {
            "id": ptm.id,
            "student_name": ptm.student.name,
            "teacher_name": ptm.teacher.name,
            "teacher_id": ptm.teacher.id,
            "class_name": ptm.student.class_name,
            "section": ptm.student.section,
            "subject": ptm.teacher.subject,
            "room": ptm.room,
            "meeting_date": ptm.meeting_date,
            "meeting_time": ptm.meeting_time,
            "status": ptm.status,
            "parent_confirmed": ptm.parent_confirmed,
            "attendance_pct": ptm.student.attendance_pct,
            "academic_level": ptm.student.academic_level,
            "remark": ptm.remark,
        }

        return data

    finally:
        db.close()


def load_teacher_ptms(teacher_id):
    """
    Load all PTMs for a teacher and convert them into plain
    dictionaries before closing the SQLAlchemy session.
    """

    db = get_db()

    try:
        ptms = (
            db.query(PTM)
            .options(
                joinedload(PTM.student),
                joinedload(PTM.teacher),
                joinedload(PTM.remark),
            )
            .filter(PTM.teacher_id == teacher_id)
            .order_by(
                PTM.meeting_date,
                PTM.meeting_time,
            )
            .all()
        )

        result = []

        for p in ptms:
            result.append(
                {
                    "id": p.id,
                    "student_name": p.student.name,
                    "student_id": p.student.id,
                    "teacher_name": p.teacher.name,
                    "teacher_id": p.teacher.id,
                    "class_name": p.student.class_name,
                    "section": p.student.section,
                    "room": p.room,
                    "meeting_date": p.meeting_date,
                    "meeting_time": p.meeting_time,
                    "status": p.status,
                    "attendance_pct": p.student.attendance_pct,
                    "academic_level": p.student.academic_level,
                    "remark": p.remark,
                }
            )

        return result

    finally:
        db.close()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("## 🎛️ Demo Controls")

    role = st.radio(
        "Open portal",
        ["Parent", "Teacher", "Admin"],
    )

    st.divider()

    st.caption("Local demo • Dummy data only")

    if st.button(
        "🔄 Reset dummy data",
        use_container_width=True,
    ):
        seed_db(force=True)
        st.success("Demo database reset successfully.")
        st.rerun()


# ============================================================
# HEADER
# ============================================================

st.title("🏫 PTM Automation System")

st.caption(
    "End-to-end Parent–Teacher Meeting workflow demo"
)


# ============================================================
# PARENT PORTAL
# ============================================================

if role == "Parent":

    st.header("👨‍👩‍👧 Parent Portal")

    st.write(
        "Select your child, preferred date and time. "
        "The system automatically checks teacher availability."
    )

    db = get_db()

    try:
        students = (
            db.query(Student)
            .options(
                joinedload(Student.teacher),
                joinedload(Student.parent),
            )
            .order_by(Student.name)
            .all()
        )

        student_options = {
            student.name: student.id
            for student in students
        }

        selected_student_name = st.selectbox(
            "Student",
            list(student_options.keys()),
        )

        selected_student_id = student_options[
            selected_student_name
        ]

        selected_student = next(
            s
            for s in students
            if s.id == selected_student_id
        )

        st.info(
            f"""
**Student:** {selected_student.name}  
**Class:** {selected_student.class_name}-{selected_student.section}  
**Teacher:** {selected_student.teacher.name}  
**Subject:** {selected_student.teacher.subject}  
**Room:** {selected_student.teacher.room}
"""
        )

    finally:
        db.close()

    st.divider()

    col1, col2 = st.columns(2)

    with col1:

        meeting_date = st.date_input(
            "Preferred date",
            value=date.today() + timedelta(days=1),
            min_value=date.today(),
        )

    with col2:

        available_slots = find_available_slots(
            selected_student_id,
            meeting_date,
        )

        if available_slots:

            slot_labels = [
                format_time(slot)
                for slot in available_slots
            ]

            selected_slot_label = st.selectbox(
                "Available time",
                slot_labels,
            )

            selected_slot = available_slots[
                slot_labels.index(selected_slot_label)
            ]

        else:

            selected_slot = None

            st.warning(
                "No available slots for this date."
            )

    if selected_slot:

        if st.button(
            "📅 Schedule PTM",
            type="primary",
            use_container_width=True,
        ):

            ptm_id, error = schedule_ptm(
                selected_student_id,
                meeting_date,
                selected_slot,
            )

            if error:

                st.error(error)

            else:

                st.success(
                    "🎉 PTM successfully scheduled!"
                )

                # ------------------------------------------------
                # IMPORTANT:
                # Reload EVERYTHING while the session is open.
                # load_ptm() converts it into plain Python data.
                # ------------------------------------------------

                ptm = load_ptm(ptm_id)

                if ptm:

                    st.markdown(
                        f"""
### ✅ PTM Confirmation

**Student:** {ptm["student_name"]}  
**Teacher:** {ptm["teacher_name"]}  
**Class:** {ptm["class_name"]}-{ptm["section"]}  
**Subject:** {ptm["subject"]}  
**Date:** {ptm["meeting_date"].strftime("%d %B %Y")}  
**Time:** {format_time(ptm["meeting_time"])}  
**Room:** {ptm["room"]}  
**Status:** {status_badge(ptm["status"])}
"""
                    )

                    st.info(
                        "📧 Demo confirmation notification generated."
                    )


    # ------------------------------------------------------------
    # RECENT NOTIFICATIONS
    # ------------------------------------------------------------

    st.divider()

    st.subheader("📨 Recent Notifications")

    db = get_db()

    try:

        notifications = (
            db.query(Notification)
            .order_by(
                Notification.sent_at.desc()
            )
            .limit(10)
            .all()
        )

        if notifications:

            notification_data = []

            for notification in notifications:

                notification_data.append(
                    {
                        "Channel": notification.channel,
                        "Recipient": notification.recipient,
                        "Message": notification.message,
                        "Status": notification.status,
                    }
                )

            st.dataframe(
                pd.DataFrame(notification_data),
                use_container_width=True,
                hide_index=True,
            )

        else:

            st.info("No notifications yet.")

    finally:

        db.close()


# ============================================================
# TEACHER PORTAL
# ============================================================

elif role == "Teacher":

    st.header("👩‍🏫 Teacher Portal")

    st.write(
        "Track PTMs, update meeting status and capture "
        "structured teacher observations."
    )

    # ------------------------------------------------------------
    # TEACHER SELECT
    # ------------------------------------------------------------

    db = get_db()

    try:

        teachers = (
            db.query(Teacher)
            .order_by(Teacher.name)
            .all()
        )

        teacher_options = {
            teacher.name: teacher.id
            for teacher in teachers
        }

    finally:

        db.close()

    selected_teacher_name = st.selectbox(
        "Teacher",
        list(teacher_options.keys()),
    )

    selected_teacher_id = teacher_options[
        selected_teacher_name
    ]

    # ------------------------------------------------------------
    # LOAD PTMS
    # ------------------------------------------------------------

    teacher_ptms = load_teacher_ptms(
        selected_teacher_id
    )

    st.subheader("📅 Assigned PTMs")

    if not teacher_ptms:

        st.info(
            "No PTMs are currently assigned to this teacher."
        )

    else:

        table_data = []

        for p in teacher_ptms:

            table_data.append(
                {
                    "ID": p["id"],
                    "Student": p["student_name"],
                    "Class": f'{p["class_name"]}-{p["section"]}',
                    "Date": p["meeting_date"].strftime(
                        "%d %b %Y"
                    ),
                    "Time": format_time(
                        p["meeting_time"]
                    ),
                    "Room": p["room"],
                    "Status": status_badge(
                        p["status"]
                    ),
                }
            )

        st.dataframe(
            pd.DataFrame(table_data),
            use_container_width=True,
            hide_index=True,
        )

        st.divider()

        # --------------------------------------------------------
        # SELECT PTM
        # --------------------------------------------------------

        st.subheader("📝 Manage a PTM")

        ptm_labels = {
            (
                f'{p["student_name"]} • '
                f'{p["meeting_date"].strftime("%d %b")} • '
                f'{format_time(p["meeting_time"])} • '
                f'#{p["id"]}'
            ): p["id"]
            for p in teacher_ptms
        }

        selected_ptm_label = st.selectbox(
            "Select PTM",
            list(ptm_labels.keys()),
        )

        selected_ptm_id = ptm_labels[
            selected_ptm_label
        ]

        selected_ptm = next(
            p
            for p in teacher_ptms
            if p["id"] == selected_ptm_id
        )

        # --------------------------------------------------------
        # STUDENT INFORMATION
        # --------------------------------------------------------

        st.subheader("👨‍🎓 Student")

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.metric(
                "Student",
                selected_ptm["student_name"],
            )

        with c2:
            st.metric(
                "Attendance",
                f'{selected_ptm["attendance_pct"]}%',
            )

        with c3:
            st.metric(
                "Academic",
                selected_ptm["academic_level"],
            )

        with c4:
            st.metric(
                "Room",
                selected_ptm["room"],
            )

        st.write(
            f'**Scheduled:** '
            f'{selected_ptm["meeting_date"].strftime("%d %B %Y")} '
            f'at '
            f'{format_time(selected_ptm["meeting_time"])}'
        )

        # --------------------------------------------------------
        # STATUS
        # --------------------------------------------------------

        st.subheader("📌 PTM Status")

        status_options = [
            "Scheduled",
            "Confirmed",
            "Arrived",
            "Completed",
            "Missed",
            "Cancelled",
        ]

        current_status = selected_ptm["status"]

        try:
            status_index = status_options.index(
                current_status
            )
        except ValueError:
            status_index = 0

        new_status = st.selectbox(
            "PTM status",
            status_options,
            index=status_index,
        )

        if st.button(
            "💾 Update Status",
            use_container_width=True,
        ):

            success = update_ptm_status(
                selected_ptm_id,
                new_status,
            )

            if success:

                st.success(
                    f"PTM status updated to {new_status}."
                )

                st.rerun()

            else:

                st.error(
                    "Could not update PTM status."
                )

        # --------------------------------------------------------
        # REMARKS
        # --------------------------------------------------------

        st.divider()

        st.subheader("📝 Teacher Remarks")

        existing_remark = selected_ptm["remark"]

        default_raw_note = ""

        if existing_remark:
            default_raw_note = (
                existing_remark.raw_note or ""
            )

        raw_note = st.text_area(
            "Rough teacher notes",
            value=default_raw_note,
            height=150,
            placeholder=(
                "Example: Student understands concepts "
                "but doesn't participate much and needs "
                "to submit assignments regularly."
            ),
        )

        st.caption(
            "Source: Teacher-entered / AI-assisted / manually edited"
        )

        # --------------------------------------------------------
        # AI STRUCTURE
        # --------------------------------------------------------

        if st.button(
            "✨ Structure remarks with AI",
            use_container_width=True,
        ):

            if not raw_note.strip():

                st.warning(
                    "Please enter teacher notes first."
                )

            else:

                structured, ai_used, source = ai_structure(
                    raw_note
                )

                st.session_state[
                    "structured_remark"
                ] = structured

                st.session_state[
                    "remark_source"
                ] = source

                st.session_state[
                    "remark_ai"
                ] = ai_used

                st.success(
                    f"Remarks structured using {source}."
                )

        # --------------------------------------------------------
        # STRUCTURED REMARKS
        # --------------------------------------------------------

        if "structured_remark" in st.session_state:

            structured = st.session_state[
                "structured_remark"
            ]

            source = st.session_state.get(
                "remark_source",
                "Local fallback",
            )

            ai_used = st.session_state.get(
                "remark_ai",
                False,
            )

            st.info(
                f"Source: {source}"
            )

            st.markdown(
                "### ✨ Structured Observation"
            )

            academic = st.text_input(
                "Academic performance",
                value=structured.get(
                    "academic",
                    "",
                ),
            )

            participation = st.text_input(
                "Class participation",
                value=structured.get(
                    "participation",
                    "",
                ),
            )

            behaviour = st.text_input(
                "Behaviour",
                value=structured.get(
                    "behaviour",
                    "",
                ),
            )

            attendance = st.text_input(
                "Attendance observation",
                value=structured.get(
                    "attendance",
                    "",
                ),
            )

            assignments = st.text_input(
                "Assignments",
                value=structured.get(
                    "assignments",
                    "",
                ),
            )

            recommendation = st.text_area(
                "Recommendation",
                value=structured.get(
                    "recommendation",
                    "",
                ),
                height=100,
            )

            updated_structured = {
                "academic": academic,
                "participation": participation,
                "behaviour": behaviour,
                "attendance": attendance,
                "assignments": assignments,
                "recommendation": recommendation,
            }

            if st.button(
                "✅ Approve & Save Remarks",
                type="primary",
                use_container_width=True,
            ):

                save_remark(
                    selected_ptm_id,
                    raw_note,
                    updated_structured,
                    ai_generated=ai_used,
                    approved=True,
                )

                st.success(
                    "Teacher remarks saved successfully."
                )

                st.session_state.pop(
                    "structured_remark",
                    None,
                )

                st.session_state.pop(
                    "remark_source",
                    None,
                )

                st.session_state.pop(
                    "remark_ai",
                    None,
                )

                st.rerun()


# ============================================================
# ADMIN DASHBOARD
# ============================================================

else:

    st.header("📊 Admin Dashboard")

    st.write(
        "Centralized PTM operations, attendance and "
        "teacher observation analytics."
    )

    db = get_db()

    try:

        all_ptms = (
            db.query(PTM)
            .options(
                joinedload(PTM.student),
                joinedload(PTM.teacher),
                joinedload(PTM.remark),
            )
            .order_by(
                PTM.meeting_date,
                PTM.meeting_time,
            )
            .all()
        )

        all_students = (
            db.query(Student)
            .options(
                joinedload(Student.teacher),
                joinedload(Student.parent),
            )
            .order_by(Student.name)
            .all()
        )

        all_teachers = (
            db.query(Teacher)
            .order_by(Teacher.name)
            .all()
        )

        all_remarks = (
            db.query(Remark)
            .all()
        )

        # Convert PTMs into dictionaries while session is alive
        ptm_rows = []

        for p in all_ptms:

            ptm_rows.append(
                {
                    "id": p.id,
                    "student": p.student.name,
                    "student_id": p.student.id,
                    "teacher": p.teacher.name,
                    "teacher_id": p.teacher.id,
                    "class": (
                        f"{p.student.class_name}-"
                        f"{p.student.section}"
                    ),
                    "date": p.meeting_date,
                    "time": p.meeting_time,
                    "room": p.room,
                    "status": p.status,
                    "attendance": p.student.attendance_pct,
                    "remark": p.remark,
                }
            )

    finally:

        db.close()

    # ------------------------------------------------------------
    # KPI
    # ------------------------------------------------------------

    total_ptms = len(ptm_rows)

    completed = sum(
        1
        for p in ptm_rows
        if p["status"] == "Completed"
    )

    pending = sum(
        1
        for p in ptm_rows
        if p["status"] in [
            "Scheduled",
            "Confirmed",
            "Arrived",
        ]
    )

    missed = sum(
        1
        for p in ptm_rows
        if p["status"] == "Missed"
    )

    attendance_rate = (
        (completed / total_ptms) * 100
        if total_ptms
        else 0
    )

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.metric(
            "Total PTMs",
            total_ptms,
        )

    with c2:
        st.metric(
            "Completed",
            completed,
        )

    with c3:
        st.metric(
            "Pending",
            pending,
        )

    with c4:
        st.metric(
            "Missed",
            missed,
        )

    with c5:
        st.metric(
            "Completion Rate",
            f"{attendance_rate:.0f}%",
        )

    st.divider()

    # ------------------------------------------------------------
    # CHARTS
    # ------------------------------------------------------------

    if ptm_rows:

        col1, col2 = st.columns(2)

        status_df = (
            pd.DataFrame(ptm_rows)
            .groupby("status")
            .size()
            .reset_index(name="count")
        )

        teacher_df = (
            pd.DataFrame(ptm_rows)
            .groupby("teacher")
            .size()
            .reset_index(name="count")
        )

        with col1:

            st.subheader("PTM Status")

            fig_status = px.pie(
                status_df,
                names="status",
                values="count",
                hole=0.45,
            )

            st.plotly_chart(
                fig_status,
                use_container_width=True,
            )

        with col2:

            st.subheader("PTMs by Teacher")

            fig_teacher = px.bar(
                teacher_df,
                x="teacher",
                y="count",
            )

            st.plotly_chart(
                fig_teacher,
                use_container_width=True,
            )

    # ------------------------------------------------------------
    # STUDENT HISTORY
    # ------------------------------------------------------------

    st.divider()

    st.subheader("👨‍🎓 Student-wise PTM History")

    student_names = sorted(
        {
            p["student"]
            for p in ptm_rows
        }
    )

    if student_names:

        selected_history_student = st.selectbox(
            "Select student",
            student_names,
        )

        history = [
            p
            for p in ptm_rows
            if p["student"]
            == selected_history_student
        ]

        history_data = []

        for p in history:

            history_data.append(
                {
                    "Date": p["date"].strftime(
                        "%d %b %Y"
                    ),
                    "Time": format_time(
                        p["time"]
                    ),
                    "Teacher": p["teacher"],
                    "Class": p["class"],
                    "Room": p["room"],
                    "Status": status_badge(
                        p["status"]
                    ),
                }
            )

        st.dataframe(
            pd.DataFrame(history_data),
            use_container_width=True,
            hide_index=True,
        )

    # ------------------------------------------------------------
    # ALL PTMS
    # ------------------------------------------------------------

    st.divider()

    st.subheader("📋 All PTMs")

    if ptm_rows:

        all_ptm_data = []

        for p in ptm_rows:

            all_ptm_data.append(
                {
                    "Student": p["student"],
                    "Teacher": p["teacher"],
                    "Class": p["class"],
                    "Date": p["date"].strftime(
                        "%d %b %Y"
                    ),
                    "Time": format_time(
                        p["time"]
                    ),
                    "Room": p["room"],
                    "Status": status_badge(
                        p["status"]
                    ),
                }
            )

        st.dataframe(
            pd.DataFrame(all_ptm_data),
            use_container_width=True,
            hide_index=True,
        )

    # ------------------------------------------------------------
    # COMMON CONCERNS
    # ------------------------------------------------------------

    st.divider()

    st.subheader("🧠 Common Teacher Observation Signals")

    concern_counts = {
        "Participation": 0,
        "Assignments": 0,
        "Attendance": 0,
        "Behaviour": 0,
    }

    for p in ptm_rows:

        remark = p["remark"]

        if not remark:
            continue

        if (
            remark.participation
            and "improvement"
            in remark.participation.lower()
        ):
            concern_counts["Participation"] += 1

        if (
            remark.assignments
            and "improvement"
            in remark.assignments.lower()
        ):
            concern_counts["Assignments"] += 1

        if (
            remark.attendance
            and "improvement"
            in remark.attendance.lower()
        ):
            concern_counts["Attendance"] += 1

        if (
            remark.behaviour
            and "review"
            in remark.behaviour.lower()
        ):
            concern_counts["Behaviour"] += 1

    concern_df = pd.DataFrame(
        {
            "Concern": list(
                concern_counts.keys()
            ),
            "Count": list(
                concern_counts.values()
            ),
        }
    )

    st.bar_chart(
        concern_df.set_index("Concern")
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "PTM Automation System • Demo Prototype • "
    "SQLite + SQLAlchemy + Streamlit + Optional AI"
)