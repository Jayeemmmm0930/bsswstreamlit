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

OLD_INC_FILE = os.path.join(CACHE_DIR, "old_incomplete.pkl")
NEW_INC_FILE = os.path.join(CACHE_DIR, "new_incomplete.pkl")


def save_cache(data, file_path):
    with open(file_path, "wb") as f:
        pickle.dump(data, f)


def load_cache(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            return pickle.load(f)
    return None


# ==========================
# Old Curriculum Incomplete Grades
# ==========================
def fetch_incomplete_old():
    cached = load_cache(OLD_INC_FILE)
    if cached is not None:
        return cached

    grades = data_collections["grades"]
    students = {s["_id"]: s for s in data_collections["students"]}
    subjects = {s["_id"]: s for s in data_collections["subjects"]}
    semesters = {s["_id"]: s for s in data_collections["semesters"]}

    rows = []
    for g in grades:
        sid = g["StudentID"]
        student = students.get(sid, {})
        semester = semesters.get(g.get("SemesterID"))
        sem_label = f"{semester.get('Semester', '')} {semester.get('SchoolYear', '')}" if semester else ""

        subject_codes = g.get("SubjectCodes", [])
        subject_grades = g.get("Grades", [])

        for idx, subj_code in enumerate(subject_codes):
            grade = subject_grades[idx] if idx < len(subject_grades) else None
            if grade in ["INC", "Dropped", None]:
                subj = subjects.get(subj_code, {})
                rows.append({
                    "Student ID": sid,
                    "Name": student.get("Name", ""),
                    "Course Code": subj_code,
                    "Course Title": subj.get("Description", ""),
                    "Term": sem_label,
                    "Grade Status": grade if grade else "INC"
                })

    df = pd.DataFrame(rows)
    save_cache(df, OLD_INC_FILE)
    return df


# ==========================
# New Curriculum Incomplete Grades
# ==========================
def fetch_incomplete_new():
    cached = load_cache(NEW_INC_FILE)
    if cached is not None:
        return cached

    grades = data_collections["newGrades"]
    students = {s["_id"]: s for s in data_collections["newStudents"]}
    subjects = {s["_id"]: s for s in data_collections["newSubjects"]}
    semesters = {s["_id"]: s for s in data_collections["newSemesters"]}

    rows = []
    for g in grades:
        sid = g["studentId"]
        student = students.get(sid, {})
        subj = subjects.get(g.get("subjectId"), {})
        sem = semesters.get(g.get("termId"))

        sem_label = f"{sem.get('code', '')} {sem.get('academicYear', '')}" if sem else ""
        status = g.get("status")
        numeric = g.get("numericGrade")

        if status in ["INC", "Dropped"] or numeric is None:
            rows.append({
                "Student ID": student.get("studentNumber", ""),
                "Name": student.get("name", ""),
                "Course Code": subj.get("subjectCode", ""),
                "Course Title": subj.get("subjectName", ""),
                "Term": sem_label,
                "Grade Status": status if status else "INC"
            })

    df = pd.DataFrame(rows)
    save_cache(df, NEW_INC_FILE)
    return df


# ==========================
# PDF Export
# ==========================
def export_incomplete_pdf(df, filename="incomplete_grades_report.pdf"):
    doc = SimpleDocTemplate(filename, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("4. Incomplete Grades Report", styles["Heading2"]))
    elements.append(Spacer(1, 12))

    # Convert DataFrame to list for table
    data = [list(df.columns)] + df.values.tolist()
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
    doc.build(elements)
    return filename


# ==========================
# MAIN VIEW
# ==========================
def incomplete_view():
    st.header("📋 Incomplete Grades Report")

    # Fetch Data
    if st.session_state.curriculum_type == "Old Curriculum":
        df = fetch_incomplete_old()
    else:
        df = fetch_incomplete_new()

    if df.empty:
        st.warning("No incomplete or dropped grades found.")
        return

    # 🔍 Search Bar
    search_term = st.text_input("🔍 Search by Student ID or Name")
    if search_term:
        df = df[df.apply(lambda row: search_term.lower() in str(row["Student ID"]).lower() 
                         or search_term.lower() in str(row["Name"]).lower(), axis=1)]

    st.dataframe(df, use_container_width=True)

    # 📊 Graphs
    col1, col2 = st.columns(2)

    with col1:
        status_count = df["Grade Status"].value_counts().reset_index()
        status_count.columns = ["Grade Status", "Count"]
        fig1 = px.pie(status_count, names="Grade Status", values="Count", title="Distribution of Incomplete/Dropped")
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        term_count = df.groupby("Term")["Grade Status"].count().reset_index()
        term_count.columns = ["Term", "Count"]
        fig2 = px.bar(term_count, x="Term", y="Count", title="Incomplete/Dropped by Term")
        st.plotly_chart(fig2, use_container_width=True)

    # Export to PDF
    if st.button("⬇️ Download Incomplete Grades PDF"):
        pdf_file = export_incomplete_pdf(df)
        with open(pdf_file, "rb") as f:
            st.download_button(
                label="📥 Save PDF",
                data=f,
                file_name="incomplete_grades_report.pdf",
                mime="application/pdf"
            )
