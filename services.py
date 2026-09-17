import os
import re
import json
from datetime import datetime

import requests
from dotenv import load_dotenv

from database import SessionLocal, PTM, Student, Notification, Remark, SLOT_TIMES

load_dotenv()


def find_available_slots(student_id, meeting_date):
    db = SessionLocal()
    try:
        student = db.get(Student, student_id)
        if not student:
            return []

        booked = {
            p.meeting_time
            for p in db.query(PTM).filter(
                PTM.teacher_id == student.teacher_id,
                PTM.meeting_date == meeting_date,
                PTM.status != "Cancelled",
            ).all()
        }
        return [slot for slot in SLOT_TIMES if slot not in booked]
    finally:
        db.close()


def schedule_ptm(student_id, meeting_date, meeting_time):
    db = SessionLocal()
    try:
        student = db.get(Student, student_id)
        if not student:
            return None, "Student not found."

        conflict = db.query(PTM).filter(
            PTM.teacher_id == student.teacher_id,
            PTM.meeting_date == meeting_date,
            PTM.meeting_time == meeting_time,
            PTM.status != "Cancelled",
        ).first()

        if conflict:
            return None, "That teacher is already booked for the selected slot."

        ptm = PTM(
            student_id=student.id,
            teacher_id=student.teacher_id,
            meeting_date=meeting_date,
            meeting_time=meeting_time,
            room=student.teacher.room,
            status="Scheduled",
            parent_confirmed=True,
        )
        db.add(ptm)
        db.flush()

        parent = student.parent
        message = (
            f"Dear {parent.name}, your PTM for {student.name} is confirmed for "
            f"{meeting_date.strftime('%d %B %Y')} at {meeting_time.strftime('%I:%M %p')} "
            f"in Class {student.class_name}-{student.section}, Room {student.teacher.room}, "
            f"with {student.teacher.name}."
        )
        db.add(Notification(
            ptm_id=ptm.id,
            recipient=parent.email,
            message=message,
            channel="Demo Email",
            status="Sent",
        ))
        db.commit()
        return ptm.id, None
    finally:
        db.close()


def update_ptm_status(ptm_id, status):
    db = SessionLocal()
    try:
        ptm = db.get(PTM, ptm_id)
        if not ptm:
            return False
        ptm.status = status
        if status == "Arrived":
            ptm.arrived_at = datetime.now()
        if status == "Completed":
            ptm.completed_at = datetime.now()
        db.commit()
        return True
    finally:
        db.close()


def save_remark(ptm_id, raw_note, structured, ai_generated=False, approved=False):
    db = SessionLocal()
    try:
        remark = db.query(Remark).filter(Remark.ptm_id == ptm_id).first()
        if not remark:
            remark = Remark(ptm_id=ptm_id)
            db.add(remark)

        for field in ["academic", "participation", "behaviour", "attendance", "assignments", "recommendation"]:
            setattr(remark, field, structured.get(field, ""))
        remark.raw_note = raw_note
        remark.ai_generated = ai_generated
        remark.teacher_approved = approved
        db.commit()
        return True
    finally:
        db.close()


def rule_based_structure(note):
    text = note.lower()

    def has(*terms):
        return any(term in text for term in terms)

    academic = "Good conceptual understanding" if has("understand", "concept", "good", "strong") else "Requires teacher review"
    participation = "Needs improvement" if has("participat", "quiet", "shy", "doesn't speak", "does not participate") else "Satisfactory"
    behaviour = "Positive" if has("well behaved", "positive", "respectful", "cooperative") else ("Needs teacher review" if has("behaviour", "behavior") else "No issue noted")
    attendance = "Needs improvement" if has("low attendance", "attendance is low", "absent", "irregular") else ("Satisfactory" if has("attendance", "regular") else "No issue noted")
    assignments = "Needs improvement" if has("late", "missing", "assignment", "submission") else "Satisfactory"

    recommendations = []
    if participation == "Needs improvement":
        recommendations.append("Encourage classroom participation.")
    if assignments == "Needs improvement":
        recommendations.append("Follow up on timely assignment submission.")
    if attendance == "Needs improvement":
        recommendations.append("Discuss attendance and identify barriers.")
    if not recommendations:
        recommendations.append("Continue current support and monitor progress.")

    return {
        "academic": academic,
        "participation": participation,
        "behaviour": behaviour,
        "attendance": attendance,
        "assignments": assignments,
        "recommendation": " ".join(recommendations),
    }


def ai_structure(note):
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    model = os.getenv("OPENROUTER_MODEL", "qwen/qwen3-4b:free")

    if not api_key:
        return rule_based_structure(note), False, "Local fallback"

    prompt = f"""You are assisting a school teacher. Structure the following rough PTM note.
Return ONLY valid JSON with these keys:
academic, participation, behaviour, attendance, assignments, recommendation.

Do not invent facts. If a category is not supported by the note, use "Not specified".
Keep each value concise.

Teacher note:
{note}
"""

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
            timeout=30,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        content = re.sub(r"^```json\s*|\s*```$", "", content).strip()
        data = json.loads(content)

        required = ["academic", "participation", "behaviour", "attendance", "assignments", "recommendation"]
        if not all(k in data for k in required):
            raise ValueError("AI response missing required fields")
        return {k: str(data[k]) for k in required}, True, "OpenRouter AI"
    except Exception:
        return rule_based_structure(note), False, "Local fallback (AI unavailable)"


def format_time(t):
    return t.strftime("%I:%M %p")
