import os
import io
import pickle
import tempfile
import streamlit as st
import pandas as pd
import plotly.express as px

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Table,
    TableStyle,
    Spacer,
    Image
)
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

from data_collection import data_collections  # your MongoDB collections dict


# ==========================
# Cache Setup
# ==========================
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

OLD_CACHE_FILE = os.path.join(CACHE_DIR, "old_curriculum.pkl")
NEW_CACHE_FILE = os.path.join(CACHE_DIR, "new_curriculum.pkl")


def save_cache(data, file_path):
    with open(file_path, "wb") as f:
        pickle.dump(data, f)


def load_cache(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            return pickle.load(f)
    return None


# ==========================
# Helpers
# ==========================
def calculate_gpa(grades, units):
    """Compute GPA as weighted average of grades based on units."""
    if not grades or not units:
        return 0
    clean_pairs = [(g if g is not None else 0, u if u is not None else 0) for g, u in zip(grades, units)]
    total_points = sum(g * u for g, u in clean_pairs)
    total_units = sum(u for _, u in clean_pairs)
    return round(total_points / total_units, 2) if total_units > 0 else 0


def dean_and_probation(df):
    """Return Dean's List and Academic Probation DataFrames."""
    deans_list = df[
        (df["GPA"] >= 90) &
        (df["Grades"].apply(lambda x: all((g or 0) >= 85 for g in x)))
    ].nlargest(10, "GPA")

    probation = df[
        (df["GPA"] < 75) |
        (df["Grades"].apply(lambda x: sum(1 for g in x if (g or 0) < 75) / len(x) >= 0.3 if len(x) > 0 else False))
    ].nsmallest(10, "GPA")

    return deans_list.reset_index(drop=True), probation.reset_index(drop=True)


# ==========================
# OLD CURRICULUM FETCH
# ==========================
def fetch_old_curriculum():
    cached = load_cache(OLD_CACHE_FILE)
    if cached is not None:
        return cached

    students = data_collections["students"]
    grades = data_collections["grades"]
    subjects = {s["_id"]: s for s in data_collections["subjects"]}

    rows = []
    for g in grades:
        sid = g["StudentID"]
        student = next((s for s in students if s["_id"] == sid), None)
        if not student:
            continue

        subject_units = [(subjects.get(code, {}).get("Units", 3) or 3) for code in g.get("SubjectCodes", [])]
        student_grades = [(val if val is not None else 0) for val in g.get("Grades", [])]

        gpa = calculate_gpa(student_grades, subject_units)

        rows.append({
            "ID": sid,
            "Name": student["Name"],
            "Prog": student["Course"],
            "Yr": student["YearLevel"],
            "Grades": student_grades,
            "Units": sum(subject_units),
            "GPA": gpa,
            "High": max(student_grades) if student_grades else 0,
        })

    df = pd.DataFrame(rows)
    save_cache(df, OLD_CACHE_FILE)
    return df


# ==========================
# NEW CURRICULUM FETCH
# ==========================
def fetch_new_curriculum():
    cached = load_cache(NEW_CACHE_FILE)
    if cached is not None:
        return cached

    students = data_collections["newStudents"]
    grades = data_collections["newGrades"]
    subjects = {s["_id"]: s for s in data_collections["newSubjects"]}

    rows = []
    for g in grades:
        sid = g["studentId"]
        student = next((s for s in students if s["_id"] == sid), None)
        if not student:
            continue

        subj = subjects.get(g["subjectId"])
        units = subj.get("units", 3) if subj else 3
        grade_val = g.get("numericGrade", 0) or 0

        gpa = calculate_gpa([grade_val], [units])

        rows.append({
            "ID": student["studentNumber"],
            "Name": student["name"],
            "Prog": student["courseCode"],
            "Yr": student.get("yearLevel", 1),
            "Grades": [grade_val],
            "Units": units,
            "GPA": gpa,
            "High": grade_val,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.groupby(["ID", "Name", "Prog", "Yr"]).agg({
            "Grades": sum,
            "Units": "sum",
            "GPA": "mean",
            "High": "max"
        }).reset_index()

    save_cache(df, NEW_CACHE_FILE)
    return df


# ==========================
# PDF EXPORT WITH CHARTS
# ==========================
def generate_pdf(deans_list, probation, fig_gpa, fig_prog):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("🎓 Academic Standing Report", styles["Title"]))
    elements.append(Spacer(1, 12))

    # Dean's List
    elements.append(Paragraph("🏅 Dean's List", styles["Heading2"]))
    if not deans_list.empty:
        table_data = [deans_list.columns.tolist()] + deans_list.values.tolist()
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No students qualified.", styles["Normal"]))
    elements.append(Spacer(1, 12))

    # Probation
    elements.append(Paragraph("⚠️ Academic Probation", styles["Heading2"]))
    if not probation.empty:
        table_data = [probation.columns.tolist()] + probation.values.tolist()
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightcoral),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No students under probation.", styles["Normal"]))
    elements.append(Spacer(1, 20))

    # Save charts temporarily and add them
    tmpfiles = []
    for fig in [fig_gpa, fig_prog]:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            fig.write_image(tmp.name, format="png")
            tmpfiles.append(tmp.name)
            elements.append(Image(tmp.name, width=400, height=250))
            elements.append(Spacer(1, 20))

    doc.build(elements)
    buffer.seek(0)
    return buffer


# ==========================
# MAIN VIEW
# ==========================
def student_academic_view():
    st.header("🎓 Student Academic Standing")

    if st.session_state.curriculum_type == "Old Curriculum":
        df = fetch_old_curriculum()
    else:
        df = fetch_new_curriculum()

    if df.empty:
        st.warning("No student data found.")
        return

    deans_list, probation = dean_and_probation(df)

    display_cols = [c for c in df.columns if c != "Grades"]
    deans_list = deans_list[display_cols]
    probation = probation[display_cols]

    # Dean’s List
    st.subheader("🏅 Dean's List (Top 10 Students)")
    st.caption("Criteria: No grade < 85 & GPA ≥ 90%")
    st.dataframe(deans_list)

    # Academic Probation
    st.subheader("⚠️ Academic Probation (10 Students)")
    st.caption("Criteria: GPA < 75% or ≥30% fails")
    st.dataframe(probation)

    # Graph: GPA Distribution
    st.subheader("📊 GPA Distribution")
    fig_gpa = px.histogram(df, x="GPA", nbins=20, title="Distribution of GPAs")
    st.plotly_chart(fig_gpa, use_container_width=True)

    # Graph: GPA per Program
    st.subheader("📈 Average GPA per Program")
    fig_prog = px.bar(df.groupby("Prog")["GPA"].mean().reset_index(),
                      x="Prog", y="GPA", title="Average GPA by Program")
    st.plotly_chart(fig_prog, use_container_width=True)

    # PDF Download Button
    pdf_buffer = generate_pdf(deans_list, probation, fig_gpa, fig_prog)
    st.download_button(
        label="⬇️ Download PDF Report",
        data=pdf_buffer,
        file_name="academic_standing.pdf",
        mime="application/pdf"
    )
