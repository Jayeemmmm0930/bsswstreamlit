import os
import pickle
import pandas as pd
import streamlit as st
import plotly.express as px
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

from data_collection import data_collections  # MongoDB collections dict

# ==========================
# Cache Setup
# ==========================
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

HIGHEST_FILE = os.path.join(CACHE_DIR, "highest.pkl")


def save_cache(data, file_path):
    with open(file_path, "wb") as f:
        pickle.dump(data, f)


def load_cache(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            return pickle.load(f)
    return None


# ==========================
# GPA Calculation Helpers
# ==========================
def compute_gpa_old(grades, subjects):
    total_points, total_units = 0, 0
    for subj_code, grade in zip(grades.get("SubjectCodes", []), grades.get("Grades", [])):
        subj = subjects.get(subj_code, {})
        units = subj.get("Units", 3)

        if isinstance(grade, (int, float)):
            total_points += grade * units
            total_units += units

    return round(total_points / total_units, 2) if total_units > 0 else None


def compute_gpa_new(student_id, term_id, new_grades, new_subjects):
    total_points, total_units = 0, 0
    for g in new_grades:
        if g["studentId"] == student_id and g["termId"] == term_id:
            subj = new_subjects.get(g["subjectId"], {})
            units = subj.get("units", 3)
            grade = g.get("numericGrade")
            if isinstance(grade, (int, float)):
                total_points += grade * units
                total_units += units

    return round(total_points / total_units, 2) if total_units > 0 else None


# ==========================
# Old Curriculum Top Performers
# ==========================
def fetch_highest_old():
    grades = data_collections["grades"]
    students = {s["_id"]: s for s in data_collections["students"]}
    subjects = {s["_id"]: s for s in data_collections["subjects"]}
    semesters = {s["_id"]: s for s in data_collections["semesters"]}

    records = []
    for g in grades:
        sid = g["StudentID"]
        student = students.get(sid, {})
        sem = semesters.get(g.get("SemesterID"), {})
        sem_label = f"{sem.get('Semester', '')} {sem.get('SchoolYear', '')}"

        gpa = compute_gpa_old(g, subjects)
        if gpa is not None:
            records.append({
                "Program": student.get("Course", ""),
                "Semester": sem_label,
                "Student ID": sid,
                "Student Name": student.get("Name", ""),
                "GPA": gpa
            })

    df = pd.DataFrame(records)
    if df.empty:
        return df

    # Rank per Program per Semester
    df["Rank"] = df.groupby(["Program", "Semester"])["GPA"].rank(ascending=False, method="dense")
    return df[df["Rank"] == 1]


# ==========================
# New Curriculum Top Performers
# ==========================
def fetch_highest_new():
    grades = data_collections["newGrades"]
    students = {s["_id"]: s for s in data_collections["newStudents"]}
    subjects = {s["_id"]: s for s in data_collections["newSubjects"]}
    semesters = {s["_id"]: s for s in data_collections["newSemesters"]}

    records = []
    for sem_id, sem in semesters.items():
        sem_label = f"{sem.get('code', '')} {sem.get('academicYear', '')}"
        for sid, student in students.items():
            gpa = compute_gpa_new(sid, sem_id, grades, subjects)
            if gpa is not None:
                records.append({
                    "Program": student.get("courseCode", ""),
                    "Semester": sem_label,
                    "Student ID": student.get("studentNumber", ""),
                    "Student Name": student.get("name", ""),
                    "GPA": gpa
                })

    df = pd.DataFrame(records)
    if df.empty:
        return df

    df["Rank"] = df.groupby(["Program", "Semester"])["GPA"].rank(ascending=False, method="dense")
    return df[df["Rank"] == 1]


# ==========================
# PDF Export
# ==========================
def export_highest_pdf(df, filename="top_performers_report.pdf"):
    doc = SimpleDocTemplate(filename, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("6. Top Performers per Program", styles["Heading2"]))
    elements.append(Spacer(1, 12))

    # Separate tables per Program
    for program, group in df.groupby("Program"):
        elements.append(Paragraph(f"Program: {program}", styles["Heading3"]))
        data = [list(group.columns)] + group.values.tolist()
        table = Table(data, repeatRows=1)

        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 12))

    doc.build(elements)
    return filename


# ==========================
# MAIN VIEW
# ==========================
def highest_view():
    st.header("🏆 Top Performers per Program")

    if st.session_state.curriculum_type == "Old Curriculum":
        df = fetch_highest_old()
    else:
        df = fetch_highest_new()

    if df.empty:
        st.warning("No GPA records found.")
        return

    # Show separately per Program
    for program, group in df.groupby("Program"):
        st.subheader(f"📌 Program: {program}")
        st.dataframe(group, use_container_width=True)

        # Chart
        fig = px.bar(group, x="Semester", y="GPA",
                     text="Student Name", color="Semester",
                     title=f"Top Performers - {program}")
        st.plotly_chart(fig, use_container_width=True)

    # PDF Export
    if st.button("⬇️ Download Top Performers Report PDF"):
        pdf_file = export_highest_pdf(df)
        with open(pdf_file, "rb") as f:
            st.download_button(
                label="📥 Save PDF",
                data=f,
                file_name="top_performers_report.pdf",
                mime="application/pdf"
            )
