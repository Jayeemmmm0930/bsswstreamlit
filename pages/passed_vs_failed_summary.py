import streamlit as st
import pandas as pd
import numpy as np
import io
import pickle
import os
import plotly.express as px

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.pagesizes import A4
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
# Passed vs Failed Summary: Old Curriculum
# ==========================
def get_old_curriculum_summary(student_id):
    grades = data_collections["grades"]
    subjects = {s["_id"]: s for s in data_collections["subjects"]}

    student_grades = [g for g in grades if g["StudentID"] == student_id]

    taken = []
    for g in student_grades:
        for idx, subject_id in enumerate(g["SubjectCodes"]):
            grade = g["Grades"][idx]
            if grade is not None:
                taken.append((subject_id, grade))

    passed = [s for s in taken if s[1] >= 75]
    failed = [s for s in taken if s[1] < 75]

    total_required = len(subjects)
    total_taken = len(taken)
    not_yet = total_required - total_taken

    data = [
        ["Passed Subjects", len(passed), f"{(len(passed) / total_required * 100):.2f}%",
         "Courses where student achieved passing grades"],
        ["Failed Subjects", len(failed), f"{(len(failed) / total_required * 100):.2f}%",
         "Courses where student earned failing grades"],
        ["Not Yet Taken", not_yet, f"{(not_yet / total_required * 100):.2f}%",
         "Remaining required courses yet to be taken"],
        ["Total Required Subjects", total_required, "100.00%",
         "Total courses in the curriculum"],
    ]
    df = pd.DataFrame(data, columns=["Category", "Count", "Percentage (%)", "Description"])
    return df


# ==========================
# Passed vs Failed Summary: New Curriculum
# ==========================
def get_new_curriculum_summary(student_id):
    grades = data_collections["newGrades"]
    subjects = data_collections["newSubjects"]

    required_subjects = [s["_id"] for s in subjects]
    student_grades = [g for g in grades if g["studentId"] == student_id]

    taken = {g["subjectId"]: g.get("numericGrade") for g in student_grades if g.get("numericGrade") is not None}
    passed = [sid for sid, grade in taken.items() if grade >= 75]
    failed = [sid for sid, grade in taken.items() if grade < 75]

    total_required = len(required_subjects)
    total_taken = len(taken)
    not_yet = total_required - total_taken

    data = [
        ["Passed Subjects", len(passed), f"{(len(passed) / total_required * 100):.2f}%",
         "Courses where student achieved passing grades"],
        ["Failed Subjects", len(failed), f"{(len(failed) / total_required * 100):.2f}%",
         "Courses where student earned failing grades"],
        ["Not Yet Taken", not_yet, f"{(not_yet / total_required * 100):.2f}%",
         "Remaining required courses yet to be taken"],
        ["Total Required Subjects", total_required, "100.00%",
         "Total courses in the curriculum"],
    ]
    df = pd.DataFrame(data, columns=["Category", "Count", "Percentage (%)", "Description"])
    return df


# ==========================
# PDF Export
# ==========================
def generate_pdf(df, fig, student_name):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"Passed vs Failed Summary - {student_name}", styles["Title"]))
    elements.append(Spacer(1, 12))

    table_data = [df.columns.tolist()] + df.astype(str).values.tolist()
    table = Table(table_data, repeatRows=1, hAlign="LEFT")

    # Base style
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F81BD")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ])

    # Highlight "Not Yet Taken" row
    for i, row in enumerate(df.values.tolist(), start=1):
        if row[0] == "Not Yet Taken":
            style.add("BACKGROUND", (0, i), (-1, i), colors.lightgrey)
            style.add("TEXTCOLOR", (0, i), (-1, i), colors.black)

    table.setStyle(style)
    elements.append(table)
    elements.append(Spacer(1, 20))

    img_buffer = io.BytesIO()
    fig.write_image(img_buffer, format="png")
    img_buffer.seek(0)
    elements.append(Image(img_buffer, width=400, height=300))

    doc.build(elements)
    buffer.seek(0)
    return buffer


# ==========================
# Main Viewer
# ==========================
def passed_vs_failed_summary():
    st.header("📘 Passed vs Failed Summary")

    curriculum = st.session_state.get("curriculum_type", "Old Curriculum")
    role = st.session_state.get("role", None)

    student = get_logged_in_student()
    if role == "student" and not student:
        st.error("⚠️ Could not find your student record.")
        return

    if role == "student":
        student_id = student["_id"]
        student_name = student.get("Name", student.get("name", "Unknown"))
        st.subheader(f"Student: {student_id} – {student_name}")
    else:
        # Faculty/Admin → Searchable Student Picker
        students = data_collections.get(
            "students" if curriculum == "Old Curriculum" else "newStudents", []
        )
        student_options = {s["_id"]: s.get("Name") or s.get("name") for s in students}

        # Search box
        search_term = st.text_input("🔍 Search Student")
        filtered_students = {
            sid: name for sid, name in student_options.items()
            if search_term.lower() in name.lower()
        } if search_term else student_options

        if not filtered_students:
            st.warning("No matching students found.")
            return

        student_id = st.selectbox(
            "Select Student",
            options=list(filtered_students.keys()),
            format_func=lambda x: filtered_students[x]
        )
        student_name = filtered_students[student_id]

    # Load data
    if curriculum == "Old Curriculum":
        df = get_old_curriculum_summary(student_id)
    else:
        df = get_new_curriculum_summary(student_id)

    if df.empty:
        st.warning("No data available.")
        return

    # Table
    st.table(df)

    # Pie chart
    fig = px.pie(df, values="Count", names="Category", title="Passed vs Failed vs Not Yet Taken")
    st.plotly_chart(fig, use_container_width=True)

    # Cache save
    os.makedirs("cache", exist_ok=True)
    cache_file = f"cache/{student_id}_pf_summary.pkl"
    with open(cache_file, "wb") as f:
        pickle.dump(df, f)

    # PDF
    pdf_buffer = generate_pdf(df, fig, student_name)
    st.download_button("📥 Download PDF", data=pdf_buffer,
                       file_name=f"{student_id}_pf_summary.pdf", mime="application/pdf")


if __name__ == "__main__":
    passed_vs_failed_summary()
