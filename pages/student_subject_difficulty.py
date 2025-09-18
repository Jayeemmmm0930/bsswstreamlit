import streamlit as st
import pandas as pd
import pickle
import os
import io
import plotly.express as px

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

from data_collection import data_collections


# ==========================
# Student Fetch Helper
# ==========================
def get_logged_in_student():
    curriculum = st.session_state.get("curriculum_type", "Old Curriculum")
    role = st.session_state.get("role", None)
    username = st.session_state.get("username", None)

    if role == "student":
        if curriculum == "Old Curriculum":
            students = {s["_id"]: s for s in data_collections["students"]}
            return students.get(username)
        else:
            students = {s["_id"]: s for s in data_collections["newStudents"]}
            return next(
                (s for s in students.values()
                 if s.get("studentNumber") == username or s["_id"] == username),
                None
            )
    return None


# ==========================
# Difficulty Level Helper
# ==========================
def get_difficulty_level(grade_distribution):
    fail_rate = grade_distribution.get("< 60 (%)", 0) + grade_distribution.get("60-69 (%)", 0)
    if fail_rate > 20:
        return "High"
    elif fail_rate > 10:
        return "Medium"
    else:
        return "Low"


# ==========================
# Old Curriculum Difficulty
# ==========================
def get_old_curriculum_difficulty(student_id):
    grades = data_collections["grades"]
    subjects = {s["_id"]: s for s in data_collections["subjects"]}
    student_grades = [g for g in grades if g["StudentID"] == student_id]

    records = []
    for g in student_grades:
        for idx, subject_id in enumerate(g["SubjectCodes"]):
            subject = subjects.get(subject_id, {})
            grade = g["Grades"][idx]

            # Count how many students took this subject
            total_students = sum(
                1 for gr in grades if subject_id in gr["SubjectCodes"]
            )

            # Example distribution (replace with real logic if you have)
            dist = {
                "90-100 (%)": 20,
                "80-89 (%)": 25,
                "70-79 (%)": 30,
                "60-69 (%)": 15,
                "< 60 (%)": 10,
            }
            diff_level = get_difficulty_level(dist)

            records.append({
                "Course Code": subject_id,
                "Course Name": subject.get("Description", ""),
                "Total Students": total_students,
                "Your Grade (%)": grade,
                **dist,
                "Difficulty Level": diff_level
            })

    return pd.DataFrame(records)


# ==========================
# New Curriculum Difficulty
# ==========================
def get_new_curriculum_difficulty(student_id):
    grades = data_collections["newGrades"]
    subjects = {s["_id"]: s for s in data_collections["newSubjects"]}
    sections = data_collections.get("newSections", [])
    student_grades = [g for g in grades if g["studentId"] == student_id]

    records = []
    for g in student_grades:
        subject_id = g["subjectId"]
        subject = subjects.get(subject_id, {})
        grade = g.get("numericGrade", None)

        # Count total students for this subject
        # Method 1: from grades
        total_students = sum(1 for gr in grades if gr["subjectId"] == subject_id)

        # Method 2: from sections (better if available)
        for sec in sections:
            if sec["subjectId"] == subject_id:
                total_students = len(sec.get("studentIds", []))
                break

        dist = {
            "90-100 (%)": 25,
            "80-89 (%)": 30,
            "70-79 (%)": 25,
            "60-69 (%)": 10,
            "< 60 (%)": 10,
        }
        diff_level = get_difficulty_level(dist)

        records.append({
            "Course Code": subject.get("subjectCode", ""),
            "Course Name": subject.get("subjectName", ""),
            "Total Students": total_students,
            "Your Grade (%)": grade,
            **dist,
            "Difficulty Level": diff_level
        })

    return pd.DataFrame(records)


# ==========================
# PDF Export
# ==========================
def generate_pdf(df, fig, student_name):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"Subject Difficulty Report - {student_name}", styles["Title"]))
    elements.append(Spacer(1, 12))

    table_data = [df.columns.tolist()] + df.astype(str).values.tolist()
    table = Table(table_data, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F81BD")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    img_buffer = io.BytesIO()
    fig.write_image(img_buffer, format="png")
    img_buffer.seek(0)
    elements.append(Image(img_buffer, width=500, height=300))

    doc.build(elements)
    buffer.seek(0)
    return buffer


# ==========================
# Main Viewer
# ==========================
def student_subject_difficulty():
    st.header("📊 Subject Difficulty Ratings")

    curriculum = st.session_state.get("curriculum_type", "Old Curriculum")
    role = st.session_state.get("role", None)

    student = get_logged_in_student()
    if role == "student" and not student:
        st.error("⚠️ Could not find your student record.")
        return

    if role == "student":
        student_id = student["_id"]
        student_name = student.get("Name", student.get("name", "Unknown"))
        st.info(f"Student: **{student_id} – {student_name}**")
    else:
        students = data_collections.get(
            "students" if curriculum == "Old Curriculum" else "newStudents", []
        )
        if not students:
            st.warning("No students found in the database.")
            return

        search_query = st.text_input("🔍 Search Student (by ID or Name)").lower().strip()
        student_options = {s["_id"]: s.get("Name") or s.get("name") for s in students}

        if search_query:
            filtered_options = {
                sid: name for sid, name in student_options.items()
                if search_query in sid.lower() or (name and search_query in name.lower())
            }
        else:
            filtered_options = student_options

        if not filtered_options:
            st.warning("No matching students found.")
            return

        student_id = st.selectbox(
            "Select a student",
            options=list(filtered_options.keys()),
            format_func=lambda x: filtered_options[x],
            key="difficulty_student_selector"
        )
        student_name = filtered_options[student_id]

    if curriculum == "Old Curriculum":
        df = get_old_curriculum_difficulty(student_id)
    else:
        df = get_new_curriculum_difficulty(student_id)

    if df.empty:
        st.warning("No subject data found for this student.")
        return

    st.subheader("Subject Performance & Difficulty")
    st.table(df)

    fig = px.bar(
        df, x="Course Code", y="Your Grade (%)", color="Difficulty Level",
        title="Grades vs. Subject Difficulty", text="Your Grade (%)"
    )
    st.plotly_chart(fig, use_container_width=True)

    os.makedirs("cache", exist_ok=True)
    cache_file = f"cache/{student_id}_subject_difficulty.pkl"
    with open(cache_file, "wb") as f:
        pickle.dump(df, f)

    pdf_buffer = generate_pdf(df, fig, student_name)
    st.download_button(
        label="📥 Download PDF Report",
        data=pdf_buffer,
        file_name=f"{student_id}_subject_difficulty.pdf",
        mime="application/pdf"
    )


if __name__ == "__main__":
    student_subject_difficulty()
