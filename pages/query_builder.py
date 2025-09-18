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
# Condition Mapping
# ==========================
CONDITION_MAP = {
    "less than": "<",
    "less than or equal to": "<=",
    "greater than": ">",
    "greater than or equal to": ">=",
    "equal to": "==",
    "not equal to": "!=",
}


# ==========================
# Old Curriculum Query
# ==========================
def run_old_query(subject_code, condition, threshold):
    grades = data_collections["grades"]
    students = {s["_id"]: s for s in data_collections["students"]}
    subjects = {s["_id"]: s for s in data_collections["subjects"]}

    rows = []
    for g in grades:
        if subject_code in g.get("SubjectCodes", []):
            idx = g["SubjectCodes"].index(subject_code)
            grade = g["Grades"][idx]
            if grade is None:
                continue
            if eval(f"{grade} {condition} {threshold}"):
                student = students.get(g["StudentID"], {})
                subject = subjects.get(subject_code, {})
                rows.append((
                    g["StudentID"],
                    student.get("Name", ""),
                    subject_code,
                    subject.get("Description", ""),
                    grade
                ))

    return pd.DataFrame(rows, columns=["Student ID", "Name", "Course Code", "Course Name", "Grade"])


# ==========================
# New Curriculum Query
# ==========================
def run_new_query(subject_code, condition, threshold):
    grades = data_collections["newGrades"]
    students = {s["_id"]: s for s in data_collections["newStudents"]}
    subjects = {s["_id"]: s for s in data_collections["newSubjects"]}

    subj_id = next((s["_id"] for s in subjects.values() if s.get("subjectCode") == subject_code), None)
    if not subj_id:
        return pd.DataFrame(columns=["Student ID", "Name", "Course Code", "Course Name", "Grade"])

    rows = []
    for g in grades:
        if g["subjectId"] == subj_id and g.get("numericGrade") is not None:
            grade = g["numericGrade"]
            if eval(f"{grade} {condition} {threshold}"):
                student = students.get(g["studentId"], {})
                subj = subjects.get(subj_id, {})
                rows.append((
                    student.get("studentNumber", ""),
                    student.get("name", ""),
                    subj.get("subjectCode", ""),
                    subj.get("subjectName", ""),
                    grade
                ))

    return pd.DataFrame(rows, columns=["Student ID", "Name", "Course Code", "Course Name", "Grade"])


# ==========================
# PDF Export (with Graph)
# ==========================
def export_pdf(df, subject_code, condition_word, threshold, curriculum, teacher_name):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("6. Custom Query Builder", styles["Heading2"]))
    elements.append(Paragraph(
        "- Allows users to build filtered queries (e.g., 'Show all students with grade less than 75 in CS101').",
        styles["Normal"]
    ))
    elements.append(Paragraph(
        f"Query Example: Show all students with grade {condition_word} {threshold} in {subject_code} "
        f"({curriculum}, Teacher: {teacher_name})", styles["Normal"]
    ))
    elements.append(Spacer(1, 12))

    if df.empty:
        elements.append(Paragraph("No students matched the query.", styles["Normal"]))
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

        # Graph in PDF
        chart_data = list(df["Grade"])
        labels = list(df["Name"])

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
        bc.valueAxis.valueStep = 10
        bc.bars[0].fillColor = colors.HexColor("#4CAF50")

        title = Label()
        title.setOrigin(200, 190)
        title.boxAnchor = "c"
        title.setText("Grades of Students")

        drawing.add(bc)
        drawing.add(title)
        elements.append(drawing)

    doc.build(elements)
    buffer.seek(0)
    return buffer


# ==========================
# Streamlit UI
# ==========================
def display_query_builder():
    st.title("🔍 Custom Query Builder")

    curriculum = st.session_state.curriculum_type
    role = st.session_state.get("role", "")

    # ==========================
    # Teacher selection logic
    # ==========================
    if role == "professor":
        # ✅ Auto-detect professor based on username
        username = st.session_state.get("username", "")
        prof = next((p for p in data_collections["newProfessors"] if p.get("username") == username), None)
        if not prof:
            st.error("❌ No professor record found for your account.")
            return
        teacher_name = prof.get("name", "Unknown Professor")
        prof_id = prof["_id"]
        st.info(f"👨‍🏫 Logged in as: **{teacher_name}**")
    else:
        # Admin view → select teacher
        if curriculum == "Old Curriculum":
            teachers = sorted({s.get("Teacher", "") for s in data_collections["subjects"] if s.get("Teacher")})
        else:
            teachers = sorted([p.get("name", "") for p in data_collections["newProfessors"]])
        teacher_name = st.selectbox("Select Teacher", teachers)
        prof_id = next((p["_id"] for p in data_collections["newProfessors"] if p.get("name") == teacher_name), None)

    # ==========================
    # Subject selection filtered by teacher
    # ==========================
    if curriculum == "Old Curriculum":
        subjects = [s for s in data_collections["subjects"] if s.get("Teacher") == teacher_name]
    else:
        subjects = [s for s in data_collections["newSubjects"] if s.get("professorId") == prof_id]

    subject_map = {s.get("subjectCode") if curriculum == "New Curriculum" else s["_id"]:
                   s.get("Description", s.get("subjectName", "")) for s in subjects}

    subject_code = st.selectbox("Select Subject", list(subject_map.keys()),
                                format_func=lambda x: f"{x} - {subject_map[x]}")

    # Query inputs
    condition_word = st.selectbox("Condition", list(CONDITION_MAP.keys()))
    condition = CONDITION_MAP[condition_word]
    threshold = st.number_input("Threshold", min_value=0, max_value=100, value=75)

    # Run query
    if st.button("Run Query"):
        if curriculum == "Old Curriculum":
            df = run_old_query(subject_code, condition, threshold)
        else:
            df = run_new_query(subject_code, condition, threshold)

        st.subheader(f"Query Results — {subject_code} ({curriculum}, Teacher: {teacher_name})")
        st.dataframe(df)

        if not df.empty:
            # Show Graph in Streamlit
            fig = px.bar(df, x="Name", y="Grade", color="Grade",
                         title="Grades of Students Matching Query",
                         text="Grade")
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

            # PDF Export with Graph
            pdf = export_pdf(df, subject_code, condition_word, threshold, curriculum, teacher_name)
            st.download_button(
                "📄 Download PDF Report",
                data=pdf,
                file_name=f"Custom_Query_{subject_code}_{curriculum}.pdf",
                mime="application/pdf",
            )


if __name__ == "__main__":
    display_query_builder()
