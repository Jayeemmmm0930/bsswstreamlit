import os
import io
import pickle
import tempfile
import pandas as pd
import streamlit as st
import plotly.express as px

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image
)
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

from data_collection import data_collections


# ==========================
# Cache Setup
# ==========================
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

OLD_PASS_FAIL_FILE = os.path.join(CACHE_DIR, "old_pass_fail.pkl")
NEW_PASS_FAIL_FILE = os.path.join(CACHE_DIR, "new_pass_fail.pkl")


def save_cache(data, file_path):
    with open(file_path, "wb") as f:
        pickle.dump(data, f)


def load_cache(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            return pickle.load(f)
    return None


# ==========================
# Old Curriculum
# ==========================
def fetch_pass_fail_old():
    cached = load_cache(OLD_PASS_FAIL_FILE)
    if cached is not None:
        return cached

    grades = data_collections["grades"]
    subjects = {s["_id"]: s for s in data_collections["subjects"]}
    semesters = {s["_id"]: s for s in data_collections["semesters"]}

    rows = []
    for g in grades:
        semester = semesters.get(g.get("SemesterID"), {})
        sem_label = f"{semester.get('Semester', '')} {semester.get('SchoolYear', '')}"

        for code, grade in zip(g.get("SubjectCodes", []), g.get("Grades", [])):
            subject = subjects.get(code, {})
            subject_name = subject.get("Description", "Unknown")
            subject_code = code

            is_pass = (grade or 0) >= 75
            rows.append({
                "Subject Code": subject_code,
                "Subject Name": subject_name,
                "Semester": sem_label,
                "Pass": 1 if is_pass else 0,
                "Fail": 0 if is_pass else 1,
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.groupby(["Subject Code", "Subject Name", "Semester"]).agg(
            Pass_Count=("Pass", "sum"),
            Fail_Count=("Fail", "sum")
        ).reset_index()

        df["Pass %"] = round(df["Pass_Count"] / (df["Pass_Count"] + df["Fail_Count"]) * 100, 1)
        df["Fail %"] = round(df["Fail_Count"] / (df["Pass_Count"] + df["Fail_Count"]) * 100, 1)

    save_cache(df, OLD_PASS_FAIL_FILE)
    return df


# ==========================
# New Curriculum
# ==========================
def fetch_pass_fail_new():
    cached = load_cache(NEW_PASS_FAIL_FILE)
    if cached is not None:
        return cached

    grades = data_collections["newGrades"]
    subjects = {s["_id"]: s for s in data_collections["newSubjects"]}
    semesters = {s["_id"]: s for s in data_collections["newSemesters"]}

    rows = []
    for g in grades:
        subject = subjects.get(g.get("subjectId"), {})
        semester = semesters.get(g.get("termId"), {})

        subject_code = subject.get("subjectCode", "Unknown")
        subject_name = subject.get("subjectName", "Unknown")
        sem_label = f"{semester.get('code', '')} {semester.get('academicYear', '')}"

        grade_val = g.get("numericGrade", 0) or 0
        is_pass = grade_val >= 75

        rows.append({
            "Subject Code": subject_code,
            "Subject Name": subject_name,
            "Semester": sem_label,
            "Pass": 1 if is_pass else 0,
            "Fail": 0 if is_pass else 1,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.groupby(["Subject Code", "Subject Name", "Semester"]).agg(
            Pass_Count=("Pass", "sum"),
            Fail_Count=("Fail", "sum")
        ).reset_index()

        df["Pass %"] = round(df["Pass_Count"] / (df["Pass_Count"] + df["Fail_Count"]) * 100, 1)
        df["Fail %"] = round(df["Fail_Count"] / (df["Pass_Count"] + df["Fail_Count"]) * 100, 1)

    save_cache(df, NEW_PASS_FAIL_FILE)
    return df


# ==========================
# PDF Export
# ==========================
def generate_pdf(df, fig):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("📊 Subject Pass/Fail Distribution", styles["Title"]))
    elements.append(Spacer(1, 12))

    if not df.empty:
        table_data = [df.columns.tolist()] + df.values.tolist()
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No data available.", styles["Normal"]))
    elements.append(Spacer(1, 20))

    # Save chart temporarily and add
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        fig.write_image(tmp.name, format="png")
        elements.append(Image(tmp.name, width=450, height=300))

    doc.build(elements)
    buffer.seek(0)
    return buffer


# ==========================
# MAIN VIEW
# ==========================
def pass_fail_view():
    st.header("📊 Subject Pass/Fail Distribution")

    if st.session_state.curriculum_type == "Old Curriculum":
        df = fetch_pass_fail_old()
    else:
        df = fetch_pass_fail_new()

    if df.empty:
        st.warning("No pass/fail data found.")
        return

    # 🔍 Search bar
    search_query = st.text_input("Search by subject code/name/semester").lower()
    if search_query:
        df = df[df.apply(lambda row:
                         search_query in str(row["Subject Code"]).lower() or
                         search_query in str(row["Subject Name"]).lower() or
                         search_query in str(row["Semester"]).lower(),
                         axis=1)]

    st.dataframe(df)

    # 📊 Graph (Pass % and Fail % by Subject)
    st.subheader("📈 Pass vs Fail % by Subject")
    fig = px.bar(df,
                 x="Subject Code",
                 y=["Pass %", "Fail %"],
                 barmode="group",
                 title="Pass/Fail Percentage by Subject")
    st.plotly_chart(fig, use_container_width=True)

    # ⬇️ Download CSV
    st.download_button(
        label="⬇️ Download Pass/Fail CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="subject_pass_fail.csv",
        mime="text/csv"
    )

    # ⬇️ Download PDF
    pdf_buffer = generate_pdf(df, fig)
    st.download_button(
        label="⬇️ Download Pass/Fail PDF",
        data=pdf_buffer,
        file_name="subject_pass_fail.pdf",
        mime="application/pdf"
    )
