import streamlit as st
import pandas as pd
import plotly.express as px
import pickle
import io
import os

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

from data_collection import data_collections


# ==========================
# GPA Calculators
# ==========================
def get_old_curriculum_gpa(student_id):
    grades = data_collections["grades"]
    semesters = {s["_id"]: s for s in data_collections["semesters"]}

    student_grades = [g for g in grades if g["StudentID"] == student_id]

    records = []
    for g in student_grades:
        semester = semesters.get(g["SemesterID"], {})
        sem_label = f"{semester.get('Semester', '')} {semester.get('SchoolYear', '')}"

        if g["Grades"]:
            gpa = sum(g["Grades"]) / len(g["Grades"])
        else:
            gpa = None

        records.append({"Semester": sem_label, "GPA": gpa})

    df = pd.DataFrame(records).sort_values("Semester")
    if not df.empty:
        df["GPA"] = df["GPA"].round(2)
    return df


def get_new_curriculum_gpa(student_id):
    new_grades = data_collections["newGrades"]
    new_semesters = {s["_id"]: s for s in data_collections["newSemesters"]}

    student_grades = [g for g in new_grades if g["studentId"] == student_id]

    records = []
    for g in student_grades:
        sem = new_semesters.get(g["termId"], {})
        sem_label = f"{sem.get('code', '')} {sem.get('academicYear', '')}"

        gpa = g.get("numericGrade", None)
        records.append({"Semester": sem_label, "GPA": gpa})

    df = pd.DataFrame(records)
    if not df.empty:
        df = df.groupby("Semester", as_index=False).mean()
        df["GPA"] = df["GPA"].round(2)
    return df.sort_values("Semester")


# ==========================
# PDF Export Helper
# ==========================
def create_pdf(df, chart_bytes, student_name):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"Performance Trend Report - {student_name}", styles["Title"]))
    elements.append(Spacer(1, 12))

    # Force GPA to 2 decimals for table
    df_display = df.copy()
    df_display["GPA"] = df_display["GPA"].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")

    # Table
    data = [["Semester", "GPA"]] + df_display.values.tolist()
    table = Table(data, hAlign="LEFT")
    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F81BD")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ])
    )
    elements.append(table)
    elements.append(Spacer(1, 20))

    # Chart image
    img = Image(io.BytesIO(chart_bytes))
    img._restrictSize(500, 300)
    elements.append(img)

    doc.build(elements)
    buffer.seek(0)
    return buffer


# ==========================
# Trend Viewer
# ==========================
def display_trend_viewer():
    st.header("📈 Performance Trend Over Time")

    curriculum = st.session_state.get("curriculum_type", "Old Curriculum")
    role = st.session_state.get("role", None)

    # ==========================
    # Student Login Logic
    # ==========================
    if role == "student":
        current_user = st.session_state.get("username")  # student _id or studentNumber

        if curriculum == "Old Curriculum":
            students = {s["_id"]: s for s in data_collections["students"]}
            student = students.get(current_user)
            student_id = student["_id"] if student else None
        else:
            students = {s["_id"]: s for s in data_collections["newStudents"]}
            student = next(
                (s for s in students.values()
                 if s.get("studentNumber") == current_user or s["_id"] == current_user),
                None
            )
            student_id = student["_id"] if student else None

        if not student_id:
            st.error("⚠️ Could not find your student record.")
            return

        student_name = student.get("Name", student.get("name", "Unknown"))
        st.info(f"Showing GPA trend for **{student_name}**")

    else:
        # ==========================
        # Admin/Professor logic
        # ==========================
        students = data_collections.get(
            "students" if curriculum == "Old Curriculum" else "newStudents",
            []
        )

        if not students:
            st.warning("No students found in the database.")
            return

        search_query = st.text_input("🔍 Search Student by Name or ID")
        student_options = {
            s["_id"]: s.get("Name") or s.get("name")
            for s in students
            if search_query.lower() in (s.get("Name") or s.get("name") or "").lower()
            or search_query.lower() in str(s.get("_id")).lower()
        }

        if not student_options:
            st.warning("No matching students found.")
            return

        student_id = st.selectbox(
            "Select a student",
            options=list(student_options.keys()),
            format_func=lambda x: student_options[x],
            key="trend_student_selector"
        )
        student_name = student_options[student_id]

    # ==========================
    # GPA Data with caching
    # ==========================
    os.makedirs("cache", exist_ok=True)
    cache_key = f"cache/trend_cache_{curriculum}_{student_id}.pkl"

    if os.path.exists(cache_key):
        with open(cache_key, "rb") as f:
            df = pickle.load(f)
    else:
        if curriculum == "Old Curriculum":
            df = get_old_curriculum_gpa(student_id)
        else:
            df = get_new_curriculum_gpa(student_id)
        with open(cache_key, "wb") as f:
            pickle.dump(df, f)

    if df.empty:
        st.warning("No GPA data found for this student.")
        return

    # ==========================
    # Display Table + Chart
    # ==========================
    st.subheader("Semester GPA Progression")

    # Format GPA column for display
    df_display = df.copy()
    df_display["GPA"] = df_display["GPA"].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
    st.table(df_display)

    fig = px.line(
        df,
        x="Semester",
        y="GPA",
        markers=True,
        title="GPA Progression"
    )
    fig.update_traces(hovertemplate="Semester=%{x}<br>GPA=%{y:.2f}<extra></extra>")
    fig.update_yaxes(tickformat=".2f")

    chart_bytes = fig.to_image(format="png")
    st.plotly_chart(fig, use_container_width=True)

    st.caption("Description: Represents GPA progression across semesters, ideal for a line chart visual.")

    # ==========================
    # Download PDF
    # ==========================
    pdf_buffer = create_pdf(df, chart_bytes, student_name)
    st.download_button(
        label="📥 Download GPA Trend PDF",
        data=pdf_buffer,
        file_name=f"GPA_Trend_{student_name}.pdf",
        mime="application/pdf"
    )


# ==========================
# Run Page
# ==========================
if __name__ == "__main__":
    display_trend_viewer()
