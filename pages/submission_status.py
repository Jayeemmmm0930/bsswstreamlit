import io
import pandas as pd
import streamlit as st
import plotly.express as px
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.textlabels import Label
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet

from data_collection import data_collections


# ==========================
# Old Curriculum Fetcher
# ==========================
def get_old_professors():
    """Return sorted list of unique professor full names (old curriculum)."""
    subjects = data_collections["subjects"]
    professors = data_collections.get("professors", [])  # if you have full names
    prof_map = {p["_id"]: p.get("fullName", p.get("name", "Unknown")) for p in professors}

    raw_names = [s.get("Teacher", "Unknown") for s in subjects]
    names = [prof_map.get(n, n) for n in raw_names]
    return sorted(set(names))


def get_old_submission_status(professor_fullname):
    grades = data_collections["grades"]
    subjects = {s["_id"]: s for s in data_collections["subjects"]}
    professors = data_collections.get("professors", [])
    prof_map = {p["_id"]: p.get("fullName", p.get("name", "Unknown")) for p in professors}

    rows = []
    for g in grades:
        for idx, teacher in enumerate(g.get("Teachers", [])):
            teacher_full = prof_map.get(teacher, teacher)
            if teacher_full == professor_fullname:
                subject_id = g["SubjectCodes"][idx]
                subject = subjects.get(subject_id, {})
                submitted = 1 if g["Grades"][idx] else 0
                rows.append((subject_id, subject.get("Description", ""), submitted, g["StudentID"]))

    if not rows:
        return pd.DataFrame(columns=["Course Code", "Course Title", "Submitted Grades", "Total Students", "Submission Rate"])

    df = pd.DataFrame(rows, columns=["Course Code", "Course Title", "Submitted", "StudentID"])
    summary = df.groupby(["Course Code", "Course Title"]).agg(
        Submitted_Grades=("Submitted", "sum"),
        Total_Students=("StudentID", "nunique"),
    ).reset_index()
    summary["Submission Rate"] = (
        (summary["Submitted_Grades"] / summary["Total_Students"]) * 100
    ).round(0).astype(int)

    summary.rename(columns={
        "Submitted_Grades": "Submitted Grades",
        "Total_Students": "Total Students"
    }, inplace=True)

    return summary


# ==========================
# New Curriculum Fetcher
# ==========================
def get_new_professors():
    """Return sorted list of professor full names (new curriculum)."""
    profs = data_collections["newProfessors"]
    return sorted([p.get("fullName", p.get("name", "Unknown")) for p in profs])


def get_new_submission_status(professor_id):
    """Return submission status for a professor by ID (new curriculum)."""
    professors = {p["_id"]: p for p in data_collections["newProfessors"]}
    subjects = {s["_id"]: s for s in data_collections["newSubjects"]}
    sections = data_collections["newSections"]
    new_grades = data_collections["newGrades"]

    if professor_id not in professors:
        return pd.DataFrame(columns=["Course Code", "Course Title", "Submitted Grades", "Total Students", "Submission Rate"]), "Unknown"

    professor_fullname = professors[professor_id].get("fullName", professors[professor_id].get("name", "Unknown"))

    rows = []
    for sec in sections:
        if sec.get("professorId") == professor_id:
            subj = subjects.get(sec["subjectId"], {})
            course_code = subj.get("subjectCode", "")
            title = subj.get("subjectName", "")
            student_ids = sec.get("studentIds", [])
            total_students = len(student_ids)

            submitted_count = sum(
                1 for g in new_grades
                if g["studentId"] in student_ids
                and g["subjectId"] == sec["subjectId"]
                and g.get("numericGrade") is not None
            )

            rows.append((course_code, title, submitted_count, total_students))

    if not rows:
        return pd.DataFrame(columns=["Course Code", "Course Title", "Submitted Grades", "Total Students", "Submission Rate"]), professor_fullname

    df = pd.DataFrame(rows, columns=["Course Code", "Course Title", "Submitted Grades", "Total Students"])
    df["Submission Rate"] = (df["Submitted Grades"] / df["Total Students"] * 100).round(0).astype(int)

    return df, professor_fullname


# ==========================
# PDF Export
# ==========================
def export_pdf(df, faculty, curriculum):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("5. Grade Submission Status", styles["Heading2"]))
    elements.append(Paragraph(
        "- Tracks the status of grade submissions by faculty for each class. (e.g., complete grades, with blank grades)",
        styles["Normal"]
    ))
    elements.append(Paragraph(f"Grade Submission Status — {faculty} ({curriculum})", styles["Normal"]))
    elements.append(Spacer(1, 12))

    if df.empty:
        elements.append(Paragraph("No grade submission data found.", styles["Normal"]))
    else:
        # Table
        data = [list(df.columns)] + df.values.tolist()
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 20))

        # Chart
        chart_data = list(df["Submission Rate"])
        labels = list(df["Course Code"])

        drawing = Drawing(400, 200)
        bc = VerticalBarChart()
        bc.x = 50
        bc.y = 30
        bc.height = 150
        bc.width = 300
        bc.data = [chart_data]
        bc.categoryAxis.categoryNames = labels
        bc.barWidth = 15
        bc.valueAxis.valueMin = 0
        bc.valueAxis.valueMax = 100
        bc.valueAxis.valueStep = 20
        bc.bars[0].fillColor = colors.HexColor("#4CAF50")

        # Title
        title = Label()
        title.setOrigin(200, 190)
        title.boxAnchor = "c"
        title.setText("Submission Rates (%)")

        drawing.add(bc)
        drawing.add(title)
        elements.append(drawing)

    doc.build(elements)
    buffer.seek(0)
    return buffer


# ==========================
# Streamlit App
# ==========================
def display_submission_status():
    st.title("📊 Grade Submission Status")

    curriculum = st.session_state.curriculum_type
    role = st.session_state.role
    username = st.session_state.username  # 👉 professorId if role=professor (new curriculum)

    # ================================
    # Old Curriculum
    # ================================
    if curriculum == "Old Curriculum":
        professors = get_old_professors()
        if role == "professor":
            prof = username  # assume already full name
        else:
            prof = st.selectbox("Select Professor", professors)

        if prof:
            df = get_old_submission_status(prof)
            st.subheader(f"Grade Submission Status — {prof}")
            st.dataframe(df)

            if not df.empty:
                fig = px.bar(
                    df,
                    x="Course Code",
                    y="Submission Rate",
                    text="Submission Rate",
                    title="Submission Rates (%)",
                    labels={"Submission Rate": "Submission Rate (%)"},
                )
                fig.update_traces(textposition="outside")
                fig.update_yaxes(range=[0, 100])
                st.plotly_chart(fig, use_container_width=True)

                pdf = export_pdf(df, prof, curriculum)
                st.download_button(
                    "📄 Download PDF Report",
                    data=pdf,
                    file_name=f"Grade_Submission_Status_{prof}_{curriculum}.pdf",
                    mime="application/pdf",
                )

    # ================================
    # New Curriculum
    # ================================
    elif curriculum == "New Curriculum":
        if role == "professor":
            # ✅ username is professorId here
            df, prof_fullname = get_new_submission_status(username)
            prof = prof_fullname
        else:
            professors = get_new_professors()
            prof = st.selectbox("Select Professor", professors)
            # convert fullname to id
            prof_id = next((p["_id"] for p in data_collections["newProfessors"]
                            if p.get("fullName", p.get("name")) == prof), None)
            df, _ = get_new_submission_status(prof_id)

        if prof:
            st.subheader(f"Grade Submission Status — {prof}")
            st.dataframe(df)

            if not df.empty:
                fig = px.bar(
                    df,
                    x="Course Code",
                    y="Submission Rate",
                    text="Submission Rate",
                    title="Submission Rates (%)",
                    labels={"Submission Rate": "Submission Rate (%)"},
                )
                fig.update_traces(textposition="outside")
                fig.update_yaxes(range=[0, 100])
                st.plotly_chart(fig, use_container_width=True)

                pdf = export_pdf(df, prof, curriculum)
                st.download_button(
                    "📄 Download PDF Report",
                    data=pdf,
                    file_name=f"Grade_Submission_Status_{prof}_{curriculum}.pdf",
                    mime="application/pdf",
                )


if __name__ == "__main__":
    display_submission_status()
