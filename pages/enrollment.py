import os
import io
import pickle
import pandas as pd
import streamlit as st
import plotly.express as px
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet

from data_collection import data_collections  # MongoDB collections dict

# ==========================
# Cache Setup
# ==========================
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

OLD_ENROLL_FILE = os.path.join(CACHE_DIR, "old_enrollment.pkl")
NEW_ENROLL_FILE = os.path.join(CACHE_DIR, "new_enrollment.pkl")


def save_cache(data, file_path):
    with open(file_path, "wb") as f:
        pickle.dump(data, f)


def load_cache(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            return pickle.load(f)
    return None


# ==========================
# Old Curriculum Enrollment
# ==========================
def fetch_enrollment_old():
    cached = load_cache(OLD_ENROLL_FILE)
    if cached is not None:
        return cached

    grades = data_collections["grades"]
    semesters = {s["_id"]: s for s in data_collections["semesters"]}

    rows = []
    for sem_id, sem in semesters.items():
        sem_label = f"{sem.get('Semester', '')} {sem.get('SchoolYear', '')}"

        enrolled_students = {g["StudentID"] for g in grades if g.get("SemesterID") == sem_id}
        total = len(enrolled_students)

        dropouts, new_enrollees = 0, 0
        for sid in enrolled_students:
            student_grades = [g for g in grades if g["StudentID"] == sid and g.get("SemesterID") == sem_id]
            all_grades = [v for g in student_grades for v in g.get("Grades", []) if v is not None]
            if all_grades and all(v < 75 for v in all_grades):
                dropouts += 1

            first_sem = min([g.get("SemesterID") for g in grades if g["StudentID"] == sid])
            if first_sem == sem_id:
                new_enrollees += 1

        retention_rate = round(((total - dropouts) / total) * 100, 1) if total > 0 else 0

        rows.append({
            "Semester": sem_label,
            "Total Enrollment": total,
            "New Enrollees": new_enrollees,
            "Dropouts": dropouts,
            "Retention Rate (%)": retention_rate
        })

    df = pd.DataFrame(rows).sort_values("Semester")
    save_cache(df, OLD_ENROLL_FILE)
    return df


# ==========================
# New Curriculum Enrollment
# ==========================
def fetch_enrollment_new():
    cached = load_cache(NEW_ENROLL_FILE)
    if cached is not None:
        return cached

    grades = data_collections["newGrades"]
    semesters = {s["_id"]: s for s in data_collections["newSemesters"]}

    rows = []
    for sem_id, sem in semesters.items():
        sem_label = f"{sem.get('code', '')} {sem.get('academicYear', '')}"

        enrolled_students = {g["studentId"] for g in grades if g.get("termId") == sem_id}
        total = len(enrolled_students)

        dropouts, new_enrollees = 0, 0
        for sid in enrolled_students:
            student_grades = [g for g in grades if g["studentId"] == sid and g.get("termId") == sem_id]
            all_grades = [g.get("numericGrade") for g in student_grades if g.get("numericGrade") is not None]
            if all_grades and all(v < 75 for v in all_grades):
                dropouts += 1

            first_sem = min([g.get("termId") for g in grades if g["studentId"] == sid])
            if first_sem == sem_id:
                new_enrollees += 1

        retention_rate = round(((total - dropouts) / total) * 100, 1) if total > 0 else 0

        rows.append({
            "Semester": sem_label,
            "Total Enrollment": total,
            "New Enrollees": new_enrollees,
            "Dropouts": dropouts,
            "Retention Rate (%)": retention_rate
        })

    df = pd.DataFrame(rows).sort_values("Semester")
    save_cache(df, NEW_ENROLL_FILE)
    return df


# ==========================
# PDF Export (no file saving)
# ==========================
def generate_pdf(df, fig):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Enrollment Trend Analysis", styles["Title"]))
    elements.append(Spacer(1, 12))

    # Table
    table_data = [list(df.columns)] + df.values.tolist()
    table = Table(table_data, colWidths=[100] * len(df.columns))  # Auto-fit column widths
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    # Graph as in-memory PNG
    img_bytes = fig.to_image(format="png", width=800, height=400, scale=2)
    img = Image(io.BytesIO(img_bytes), width=600, height=300)  # ✅ FIXED
    elements.append(img)

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


# ==========================
# MAIN VIEW
# ==========================
def enrollment_view():
    st.header("📈 Enrollment Trend Analysis")

    if st.session_state.curriculum_type == "Old Curriculum":
        df = fetch_enrollment_old()
    else:
        df = fetch_enrollment_new()

    if df.empty:
        st.warning("No enrollment data found.")
        return

    # Show table
    st.dataframe(df)

    # Plot Trends
    st.subheader("📊 Enrollment Trends Over Time")
    fig = px.line(df, x="Semester", y="Total Enrollment", markers=True, title="Total Enrollment Over Time")
    st.plotly_chart(fig, use_container_width=True)

    # PDF Download (pass fig directly)
    pdf_bytes = generate_pdf(df, fig)
    st.download_button(
        label="⬇️ Download Enrollment PDF",
        data=pdf_bytes,
        file_name="enrollment_trends.pdf",
        mime="application/pdf"
    )

    # Insight
    st.markdown(
        "**Insight:** Plotting these values as line or area charts reveals enrollment dynamics—semester over semester or year over year."
    )
