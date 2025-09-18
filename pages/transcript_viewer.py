import os
import io
import pickle
import pandas as pd
import streamlit as st
import plotly.express as px

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

from data_collection import data_collections


# ==========================
# Transcript Fetcher (Old Curriculum)
# ==========================
def get_transcript_old(student_id):
    students = {s["_id"]: s for s in data_collections["students"]}
    subjects = {s["_id"]: s for s in data_collections["subjects"]}
    semesters = {s["_id"]: s for s in data_collections["semesters"]}
    grades = [g for g in data_collections["grades"] if g["StudentID"] == student_id]

    student = students.get(student_id, {})
    rows = []
    for g in grades:
        sem = semesters.get(g["SemesterID"], {})
        for idx, subj_code in enumerate(g["SubjectCodes"]):
            subj = subjects.get(subj_code, {})
            grade_val = g["Grades"][idx] if idx < len(g["Grades"]) else None
            remark = (
                "No Grade" if grade_val is None
                else "Passed" if grade_val >= 75
                else "Failed"
            )
            rows.append({
                "Year": sem.get("SchoolYear", ""),
                "Semester": sem.get("Semester", ""),
                "Course Code": subj_code,
                "Course Name": subj.get("Description", "Unknown"),
                "Grade (%)": grade_val if grade_val is not None else "—",
                "Credit Units": subj.get("Units", 0),
                "Remark": remark
            })

    return student, pd.DataFrame(rows)


# ==========================
# Transcript Fetcher (New Curriculum)
# ==========================
def get_transcript_new(student_id):
    students = {s["_id"]: s for s in data_collections["newStudents"]}
    subjects = {s["_id"]: s for s in data_collections["newSubjects"]}
    semesters = {s["_id"]: s for s in data_collections["newSemesters"]}
    grades = [g for g in data_collections["newGrades"] if g["studentId"] == student_id]

    student = students.get(student_id, {})
    rows = []
    for g in grades:
        subj = subjects.get(g["subjectId"], {})
        sem = semesters.get(g["termId"], {})
        grade_val = g.get("numericGrade")
        remark = (
            "No Grade" if grade_val is None
            else "Passed" if grade_val >= 75
            else "Failed"
        )
        rows.append({
            "Year": sem.get("academicYear", ""),
            "Semester": sem.get("semesterNumber", ""),
            "Course Code": subj.get("subjectCode", "N/A"),
            "Course Name": subj.get("subjectName", "Unknown"),
            "Grade (%)": grade_val if grade_val is not None else "—",
            "Credit Units": subj.get("units", 0),
            "Remark": remark
        })

    return student, pd.DataFrame(rows)


# ==========================
# PDF Export
# ==========================
def generate_pdf(student, df, fig):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()

    story.append(Paragraph("Academic Transcript", styles["Title"]))
    story.append(Paragraph(f"Student: {student.get('Name', student.get('name', ''))}", styles["Heading2"]))
    story.append(Spacer(1, 12))

    # Add Transcript Table
    table_data = [df.columns.tolist()] + df.astype(str).values.tolist()
    table = Table(table_data, repeatRows=1)

    # Base table style
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
    ])

    # Highlight Failed / No Grade rows
    for i, row in enumerate(df.itertuples(), start=1):  # +1 because header row = 0
        if row.Remark == "Failed":
            style.add("BACKGROUND", (0, i), (-1, i), colors.lightcoral)
            style.add("TEXTCOLOR", (0, i), (-1, i), colors.black)
        elif row.Remark == "No Grade":
            style.add("BACKGROUND", (0, i), (-1, i), colors.lightyellow)
            style.add("TEXTCOLOR", (0, i), (-1, i), colors.black)

    table.setStyle(style)
    story.append(table)
    story.append(Spacer(1, 24))

    # Save Plotly figure to PNG then embed
    img_buffer = io.BytesIO()
    fig.write_image(img_buffer, format="png")
    img_buffer.seek(0)
    story.append(Image(img_buffer, width=400, height=250))

    doc.build(story)
    buffer.seek(0)
    return buffer


# ==========================
# Display Transcript Viewer
# ==========================
def display_transcript_viewer():
    st.title("📄 Academic Transcript Viewer")

    curriculum = st.session_state.curriculum_type
    role = st.session_state.get("role", None)

    # ==========================
    # Student Login Logic
    # ==========================
    if role == "student":
        current_user = st.session_state.get("username")  # stores student _id or studentNumber
        if curriculum == "Old Curriculum":
            students = {s["_id"]: s for s in data_collections["students"]}
            student = students.get(current_user)
            student_id = student["_id"] if student else None
        else:
            students = {s["_id"]: s for s in data_collections["newStudents"]}
            student = next(
                (s for s in students.values() if s["studentNumber"] == current_user or s["_id"] == current_user),
                None
            )
            student_id = student["_id"] if student else None

        if not student_id:
            st.error("⚠️ Could not find your student record.")
            return

        st.info(f"Showing transcript for **{student.get('Name', student.get('name'))}**")

    else:
        # Admin/Professor view with search + dropdown
        if curriculum == "Old Curriculum":
            students = data_collections["students"]
            student_dict = {s["_id"]: s["Name"] for s in students}
        else:
            students = data_collections["newStudents"]
            student_dict = {s["_id"]: s["name"] for s in students}

        search_query = st.text_input("Search Student by Name or ID")
        filtered_students = {
            sid: name for sid, name in student_dict.items()
            if search_query.lower() in name.lower() or search_query.lower() in sid.lower()
        }

        student_id = st.selectbox(
            "Choose Student",
            options=list(filtered_students.keys()),
            format_func=lambda x: filtered_students.get(x, "")
        )

        if not student_id:
            st.info("Please select a student to view transcript.")
            return

    # ==========================
    # Fetch transcript
    # ==========================
    if curriculum == "Old Curriculum":
        student, df = get_transcript_old(student_id)
    else:
        student, df = get_transcript_new(student_id)

    if df.empty:
        st.warning("No transcript data available.")
        return

    # ==========================
    # Student Info
    # ==========================
    st.markdown(f"**Student:** {student_id} - {student.get('Name', student.get('name'))}")
    numeric_grades = df[df["Grade (%)"] != "—"]["Grade (%)"].astype(float)
    cumulative_gpa = numeric_grades.mean().round(2) if not numeric_grades.empty else "N/A"
    st.markdown(f"**Cumulative GPA:** {cumulative_gpa}%")

    # Highlight helper for DataFrame
    def highlight_row(row):
        if row["Remark"] == "Failed":
            return ["background-color: lightcoral; color: black"] * len(row)
        elif row["Remark"] == "No Grade":
            return ["background-color: lightyellow; color: black"] * len(row)
        return [""] * len(row)

    # Transcript by semester
    for (year, sem), sem_df in df.groupby(["Year", "Semester"]):
        st.markdown(f"#### 📘 {year} - Semester {sem}")
        st.dataframe(
            sem_df.drop(columns=["Year", "Semester"]).style.apply(highlight_row, axis=1),
            use_container_width=True
        )

    # Graph
    st.markdown("### 📈 Performance Trend")
    plot_df = df[df["Grade (%)"] != "—"].copy()
    if not plot_df.empty:
        plot_df["Grade (%)"] = plot_df["Grade (%)"].astype(float)
        plot_df["SemLabel"] = plot_df["Year"].astype(str) + " - Sem " + plot_df["Semester"].astype(str)
        fig = px.line(plot_df, x="SemLabel", y="Grade (%)", color="Course Name", markers=True)
        fig.update_yaxes(range=[50, 100])
        st.plotly_chart(fig, use_container_width=True)
    else:
        fig = px.line()
        st.info("No numeric grades available for plotting.")

    # Save pickle to cache/
    os.makedirs("cache", exist_ok=True)
    with open(f"cache/{student_id}_transcript.pkl", "wb") as f:
        pickle.dump(df, f)

    # PDF download button
    pdf_buffer = generate_pdf(student, df, fig)
    st.download_button(
        label="📥 Download Transcript as PDF",
        data=pdf_buffer,
        file_name=f"{student_id}_transcript.pdf",
        mime="application/pdf"
    )


# ==========================
# Run Page
# ==========================
if __name__ == "__main__":
    display_transcript_viewer()
