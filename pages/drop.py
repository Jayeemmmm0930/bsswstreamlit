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

DROP_FILE = os.path.join(CACHE_DIR, "retention.pkl")


def save_cache(data, file_path):
    with open(file_path, "wb") as f:
        pickle.dump(data, f)


def load_cache(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            return pickle.load(f)
    return None


# ==========================
# Retention & Dropout Logic
# ==========================
def calculate_retention_old():
    """
    Calculates retention for Old Curriculum.
    """
    grades = data_collections["grades"]
    semesters = {s["_id"]: s for s in data_collections["semesters"]}

    # Build mapping of semester → enrolled students
    sem_students = {}
    for g in grades:
        sid = g["StudentID"]
        sem_id = g.get("SemesterID")
        if sem_id not in sem_students:
            sem_students[sem_id] = set()
        sem_students[sem_id].add(sid)

    rows = []
    sem_ids = list(sem_students.keys())
    sem_ids.sort(key=lambda x: str(x))  # ensure order

    for i in range(len(sem_ids) - 1):
        curr_sem = semesters.get(sem_ids[i], {})
        next_sem = semesters.get(sem_ids[i + 1], {})

        curr_label = f"{curr_sem.get('Semester', '')} {curr_sem.get('SchoolYear', '')}"
        next_label = f"{next_sem.get('Semester', '')} {next_sem.get('SchoolYear', '')}"

        curr_students = sem_students[sem_ids[i]]
        next_students = sem_students[sem_ids[i + 1]]

        retained = len(curr_students & next_students)
        dropped = len(curr_students - next_students)
        rate = (retained / len(curr_students)) * 100 if curr_students else 0

        rows.append({
            "Semester to Semester": f"{curr_label} → {next_label}",
            "Retained": retained,
            "Dropped Out": dropped,
            "Retention Rate (%)": f"{rate:.1f}%"
        })

    return pd.DataFrame(rows)


def calculate_retention_new():
    """
    Calculates retention for New Curriculum.
    """
    grades = data_collections["newGrades"]
    semesters = {s["_id"]: s for s in data_collections["newSemesters"]}

    sem_students = {}
    for g in grades:
        sid = g["studentId"]
        sem_id = g.get("termId")
        if sem_id not in sem_students:
            sem_students[sem_id] = set()
        sem_students[sem_id].add(sid)

    rows = []
    sem_ids = list(sem_students.keys())
    sem_ids.sort(key=lambda x: str(x))

    for i in range(len(sem_ids) - 1):
        curr_sem = semesters.get(sem_ids[i], {})
        next_sem = semesters.get(sem_ids[i + 1], {})

        curr_label = f"{curr_sem.get('code', '')} {curr_sem.get('academicYear', '')}"
        next_label = f"{next_sem.get('code', '')} {next_sem.get('academicYear', '')}"

        curr_students = sem_students[sem_ids[i]]
        next_students = sem_students[sem_ids[i + 1]]

        retained = len(curr_students & next_students)
        dropped = len(curr_students - next_students)
        rate = (retained / len(curr_students)) * 100 if curr_students else 0

        rows.append({
            "Semester to Semester": f"{curr_label} → {next_label}",
            "Retained": retained,
            "Dropped Out": dropped,
            "Retention Rate (%)": f"{rate:.1f}%"
        })

    return pd.DataFrame(rows)


# ==========================
# PDF Export
# ==========================
def export_retention_pdf(df, filename="retention_dropout_report.pdf"):
    doc = SimpleDocTemplate(filename, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("5. Retention and Dropout Rates", styles["Heading2"]))
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
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(
        "Insight: Measures student persistence and identifies retention issues early—critical for institutional planning.",
        styles["Normal"]
    ))

    doc.build(elements)
    return filename


# ==========================
# MAIN VIEW
# ==========================
def retention_view():
    st.header("📊 Retention and Dropout Rates")

    if st.session_state.curriculum_type == "Old Curriculum":
        df = calculate_retention_old()
    else:
        df = calculate_retention_new()

    if df.empty:
        st.warning("No retention/dropout data available.")
        return

    st.dataframe(df, use_container_width=True)

    # 📈 Chart
    fig = px.bar(df, x="Semester to Semester", y="Retained",
                 text="Retention Rate (%)", title="Retention Trends")
    st.plotly_chart(fig, use_container_width=True)

    # Export to PDF
    if st.button("⬇️ Download Retention Report PDF"):
        pdf_file = export_retention_pdf(df)
        with open(pdf_file, "rb") as f:
            st.download_button(
                label="📥 Save PDF",
                data=f,
                file_name="retention_dropout_report.pdf",
                mime="application/pdf"
            )
