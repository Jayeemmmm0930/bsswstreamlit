import io
import pandas as pd
import streamlit as st
import plotly.express as px
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet

from data_collection import data_collections


# ==========================
# Grade Distribution Helpers
# ==========================
GRADE_BINS = {
    "95-100 (%)": (95, 100),
    "90-94 (%)": (90, 94),
    "85-89 (%)": (85, 89),
    "80-84 (%)": (80, 84),
    "75-79 (%)": (75, 79),
    "Below 75 (%)": (0, 74)
}


def compute_distribution(grades):
    """Compute grade distribution percentages from list of numeric grades."""
    total = len(grades)
    if total == 0:
        return {col: 0 for col in GRADE_BINS} | {"Total S": 0}

    counts = {}
    for label, (low, high) in GRADE_BINS.items():
        counts[label] = sum(1 for g in grades if low <= g <= high) / total * 100

    counts["Total S"] = total
    return counts


# ==========================
# Old Curriculum
# ==========================
def fetch_distribution_old(professor, semester_id):
    grades = data_collections["grades"]
    subjects = {s["_id"]: s for s in data_collections["subjects"]}

    rows = []
    for g in grades:
        if g.get("SemesterID") != semester_id:
            continue

        subject_codes = g.get("SubjectCodes", [])
        subject_grades = g.get("Grades", [])
        teachers = g.get("Teachers", [])

        for code, grade, teacher in zip(subject_codes, subject_grades, teachers):
            if grade is None or teacher != professor:
                continue
            subj = subjects.get(code, {})
            subj_name = subj.get("Description", f"Subj {code}")
            rows.append({"Course Code": code, "Course Name": subj_name, "Grade": grade})

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame()

    dist_rows = []
    for code, group in df.groupby(["Course Code", "Course Name"]):
        stats = compute_distribution(group["Grade"].tolist())
        dist_rows.append({"Course Code": code[0], "Course Name": code[1]} | stats)

    return pd.DataFrame(dist_rows)


# ==========================
# New Curriculum
# ==========================
def fetch_distribution_new(professor_id, semester_id):
    grades = data_collections["newGrades"]
    subjects = {s["_id"]: s for s in data_collections["newSubjects"]}
    sections = data_collections["newSections"]

    rows = []
    for sec in sections:
        if sec.get("semesterId") != semester_id or sec.get("professorId") != professor_id:
            continue

        subject_id = sec.get("subjectId")
        student_ids = sec.get("studentIds", [])

        for g in grades:
            if g.get("studentId") not in student_ids or g.get("subjectId") != subject_id:
                continue
            grade = g.get("numericGrade")
            if grade is None:
                continue
            subj = subjects.get(subject_id, {})
            subj_name = subj.get("subjectName", f"Subj {subject_id}")
            subj_code = subj.get("subjectCode", subject_id)
            rows.append({"Course Code": subj_code, "Course Name": subj_name, "Grade": grade})

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame()

    dist_rows = []
    for code, group in df.groupby(["Course Code", "Course Name"]):
        stats = compute_distribution(group["Grade"].tolist())
        dist_rows.append({"Course Code": code[0], "Course Name": code[1]} | stats)

    return pd.DataFrame(dist_rows)


# ==========================
# PDF Export
# ==========================
def generate_pdf(df, fig, professor, semester):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("1. Class Grade Distribution", styles["Title"]))
    elements.append(Paragraph(
        f"- Displays a histogram of student grade distribution per subject.<br/>"
        f"Faculty Name: {professor}<br/>"
        f"Semester and School Year: {semester}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 12))

    # Table
    table_data = [list(df.columns)] + df.values.tolist()
    table = Table(table_data, colWidths=[80] * len(df.columns))
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    # Histogram image
    img_bytes = fig.to_image(format="png", width=800, height=400, scale=2)
    img = Image(io.BytesIO(img_bytes), width=600, height=300)
    elements.append(img)

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


# ==========================
# MAIN VIEW
# ==========================
def class_distribution_view():
    st.header("📊 Class Grade Distribution")

    curriculum = st.session_state.curriculum_type
    role = st.session_state.role
    username = st.session_state.username  # ✅ professorId when role=professor

    # --- Professor + Semester selections ---
    if curriculum == "Old Curriculum":
        all_profs = sorted({t for g in data_collections["grades"] for t in g.get("Teachers", []) if t})
        semesters = {s["_id"]: f"{s['Semester']} {s['SchoolYear']}" for s in data_collections["semesters"]}

        if role == "professor":
            professor = username  # 🔒 professor login locks to their name
        else:
            professor = st.selectbox("👨‍🏫 Select Professor (Full Name)", ["-- Select --"] + all_profs)

    else:  # New Curriculum
        professors = {p["_id"]: p["name"] for p in data_collections["newProfessors"]}
        semesters = {s["_id"]: f"{s['code']} ({s['academicYear']})" for s in data_collections["newSemesters"]}

        if role == "professor":
            prof_id = username
            professor = professors.get(prof_id, "Unknown")
        else:
            professor = st.selectbox("👨‍🏫 Select Professor (Full Name)", ["-- Select --"] + list(professors.values()))

    semester = st.selectbox("📅 Select Semester", ["-- Select --"] + list(semesters.values()))

    # --- Do not show results until both selected ---
    if professor == "-- Select --" or semester == "-- Select --":
        st.info("Please select both a Professor and a Semester to view results.")
        return

    # Resolve IDs for New Curriculum
    if curriculum == "Old Curriculum":
        semester_id = [k for k, v in semesters.items() if v == semester][0]
        df = fetch_distribution_old(professor, semester_id)
    else:
        semester_id = [k for k, v in semesters.items() if v == semester][0]
        professor_id = [k for k, v in professors.items() if v == professor][0]
        df = fetch_distribution_new(professor_id, semester_id)

    if df.empty:
        st.warning("No grade distribution data found for this professor and semester.")
        return

    # --- Show Results ---
    st.subheader(f"📑 Grade Distribution — {professor} ({semester})")
    st.dataframe(df, use_container_width=True)

    dist_cols = list(GRADE_BINS.keys())
    fig = px.bar(
        df,
        x="Course Name",
        y=dist_cols,
        barmode="stack",
        title=f"Grade Distribution per Subject ({professor}, {semester})"
    )
    st.plotly_chart(fig, use_container_width=True)

    pdf_bytes = generate_pdf(df, fig, professor, semester)
    st.download_button(
        label="⬇️ Download Grade Distribution PDF",
        data=pdf_bytes,
        file_name="class_grade_distribution.pdf",
        mime="application/pdf"
    )
