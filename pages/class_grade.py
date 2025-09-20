import io
import pandas as pd
import streamlit as st
import plotly.express as px
import tempfile
from datetime import datetime

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
    """Compute grade distribution percentages from list of numeric grades (2 decimal places)."""
    total = len(grades)
    if total == 0:
        return {col: 0.00 for col in GRADE_BINS} | {"Total S": 0}

    counts = {}
    for label, (low, high) in GRADE_BINS.items():
        pct = sum(1 for g in grades if low <= g <= high) / total * 100
        counts[label] = round(pct, 2)

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
# PDF Export (better table + graph colors)
# ==========================
def generate_pdf(df, fig, professor, semester):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    styles = getSampleStyleSheet()
    elements = []

    # Title + meta
    elements.append(Paragraph("1. Class Grade Distribution", styles["Heading2"]))
    elements.append(Paragraph(
        f"Faculty Name: {professor}<br/>"
        f"Semester and School Year: {semester}<br/>"
        f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 12))

    # Round + format numbers
    for col in GRADE_BINS.keys():
        if col in df.columns:
            df[col] = df[col].round(2)

    # Format numbers as strings (except Total S)
    df = df.applymap(lambda x: f"{x:.2f}" if isinstance(x, float) else x)

    # Table with better layout
    data = [list(df.columns)] + df.values.tolist()
    col_widths = [70, 180] + [60] * (len(df.columns) - 2)
    table = Table(data, colWidths=col_widths)

    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
    ])

    # Alternate row shading
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.add("BACKGROUND", (0, i), (-1, i), colors.whitesmoke)

    table.setStyle(style)
    elements.append(table)
    elements.append(Spacer(1, 20))

    # Chart (export with colors)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
        fig.write_image(tmpfile.name, width=1000, height=500)
        elements.append(Image(tmpfile.name, width=700, height=300))

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
            professor = username
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

    if professor == "-- Select --" or semester == "-- Select --":
        st.info("Please select both a Professor and a Semester to view results.")
        return

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

    # Round + format for display
    for col in GRADE_BINS.keys():
        if col in df.columns:
            df[col] = df[col].round(2)

    df_display = df.applymap(lambda x: f"{x:.2f}" if isinstance(x, float) else x)

    # Show Results
    st.subheader(f"📑 Grade Distribution — {professor} ({semester})")
    st.dataframe(df_display, use_container_width=True)

    # Color palette for graph
    dist_cols = list(GRADE_BINS.keys())
    color_map = {
        "95-100 (%)": "#2ca02c",
        "90-94 (%)": "#1f77b4",
        "85-89 (%)": "#ff7f0e",
        "80-84 (%)": "#d62728",
        "75-79 (%)": "#9467bd",
        "Below 75 (%)": "#8c564b",
    }

    fig = px.bar(
        df,
        x="Course Name",
        y=dist_cols,
        barmode="stack",
        title=f"Grade Distribution per Subject ({professor}, {semester})",
        color_discrete_map=color_map
    )
    st.plotly_chart(fig, use_container_width=True)

    # Export PDF
    pdf_bytes = generate_pdf(df, fig, professor, semester)
    st.download_button(
        label="⬇️ Download Grade Distribution PDF",
        data=pdf_bytes,
        file_name="class_grade_distribution.pdf",
        mime="application/pdf"
    )
