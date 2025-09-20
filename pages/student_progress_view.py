import streamlit as st
import pandas as pd
import plotly.express as px
import io
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

from data_collection import data_collections


# ==========================
# GPA Calculator (Old Curriculum)
# ==========================
def get_student_gpa_old(selected_prof, selected_course=None, selected_year=None, selected_subject=None):
    students = {s["_id"]: s for s in data_collections["students"]}
    grades = data_collections["grades"]
    semesters = {s["_id"]: s for s in data_collections["semesters"]}
    subjects = {s["_id"]: s for s in data_collections["subjects"]}

    rows = []
    for g in grades:
        for idx, subj_code in enumerate(g["SubjectCodes"]):
            subj = subjects.get(subj_code, {})
            teacher = g["Teachers"][idx] if idx < len(g["Teachers"]) else subj.get("Teacher")

            if teacher != selected_prof:
                continue

            student = students.get(g["StudentID"], {})
            if selected_course and student.get("Course") != selected_course:
                continue
            if selected_year and str(student.get("YearLevel")) != str(selected_year):
                continue
            if selected_subject and subj.get("Description") != selected_subject:
                continue

            gpa = g["Grades"][idx] if idx < len(g["Grades"]) else None

            rows.append({
                "Student ID": g["StudentID"],
                "Name": student.get("Name", "Unknown"),
                "Course": student.get("Course", "Unknown"),
                "YearLevel": student.get("YearLevel", "N/A"),
                "Semester": semesters.get(g["SemesterID"], {}).get("Semester", "N/A"),
                "GPA": gpa,
                "Professor": teacher,
                "Subject": subj.get("Description", "Unknown"),
                "Section": "N/A"  # No sections in old curriculum
            })

    return pd.DataFrame(rows)


# ==========================
# GPA Calculator (New Curriculum)
# ==========================
def get_student_gpa_new(selected_prof, selected_course=None, selected_year=None, selected_subject=None, selected_section=None):
    students = {s["_id"]: s for s in data_collections["newStudents"]}
    grades = data_collections["newGrades"]
    semesters = {s["_id"]: s for s in data_collections["newSemesters"]}
    subjects = {s["_id"]: s for s in data_collections["newSubjects"]}
    professors = {p["_id"]: p for p in data_collections["newProfessors"]}
    sections = {s["_id"]: s for s in data_collections["newSections"]}

    rows = []
    for g in grades:
        subj = subjects.get(g["subjectId"], {})
        prof_id = subj.get("professorId")
        professor = professors.get(prof_id, {}).get("name")

        if professor != selected_prof:
            continue

        student = students.get(g["studentId"], {})
        if selected_course and student.get("courseCode") != selected_course:
            continue
        if selected_year and str(student.get("yearLevel")) != str(selected_year):
            continue
        if selected_subject and subj.get("subjectName") != selected_subject:
            continue

        # Find section(s) for this subject+student
        section_name = None
        for sec in sections.values():
            if g["subjectId"] == sec.get("subjectId") and g["studentId"] in sec.get("studentIds", []):
                section_name = sec.get("sectionName")
                break

        if selected_section and section_name != selected_section:
            continue

        semester = semesters.get(g["termId"], {}).get("code", "N/A")

        rows.append({
            "Student ID": g["studentId"],
            "Name": student.get("name", "Unknown"),
            "Course": student.get("courseCode", "Unknown"),
            "YearLevel": student.get("yearLevel", "N/A"),
            "Semester": semester,
            "GPA": g.get("numericGrade"),
            "Professor": professor,
            "Subject": subj.get("subjectName", "Unknown"),
            "Section": section_name or "N/A"
        })

    return pd.DataFrame(rows)


# ==========================
# Trend Analyzer
# ==========================
def calculate_trend(gpa_list):
    gpa_list = [g for g in gpa_list if g is not None]
    if len(gpa_list) < 2:
        return "— Insufficient Data"

    if gpa_list[-1] > gpa_list[0]:
        return "↑ Improving"
    elif gpa_list[-1] < gpa_list[0]:
        return "↓ Needs Attention"
    else:
        return "→ Stable High"


# ==========================
# PDF Export Helper
# ==========================
def create_pdf(df, fig, selected_prof, curriculum, selected_section=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    elements = []

    title = f"Student Progress Report - {selected_prof} ({curriculum})"
    if selected_section:
        title += f" | Section: {selected_section}"

    elements.append(Paragraph(title, styles["Title"]))
    elements.append(Spacer(1, 12))

    # Format GPA to 2 decimals
    df = df.copy()
    if "GPA" in df.columns:
        df["GPA"] = df["GPA"].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "—")

    # Table
    data = [df.columns.tolist()] + df.values.tolist()
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

    # Chart
    img_bytes = fig.to_image(format="png")
    img = Image(io.BytesIO(img_bytes))
    img._restrictSize(500, 300)
    elements.append(img)

    doc.build(elements)
    buffer.seek(0)
    return buffer


# ==========================
# Display Function
# ==========================
def display_student_progress():
    st.title("🎓 Student Progress Tracker")
    st.caption("Shows longitudinal performance for individual students. Filtered by **Professor, Subject, Course, Year Level, and Section (new curriculum only).**")

    curriculum = st.session_state.curriculum_type
    role = st.session_state.role
    username = st.session_state.username  # ✅ professorId when role=professor

    # ======================
    # Professor Handling
    # ======================
    if curriculum == "Old Curriculum":
        all_profs = sorted({t for g in data_collections["grades"] for t in g.get("Teachers", []) if t})

        if role == "professor":
            selected_prof = username  # 🔒 use logged-in professor only
        else:
            selected_prof = st.selectbox("Select Professor (Full Name):", all_profs)

    else:
        professors = {p["_id"]: p for p in data_collections["newProfessors"]}

        if role == "professor":
            prof_id = username  # from login
            selected_prof = professors.get(prof_id, {}).get("name", "Unknown")
        else:
            all_profs = sorted([p["name"] for p in professors.values()])
            selected_prof = st.selectbox("Select Professor (Full Name):", all_profs)

    # ======================
    # Load All Data
    # ======================
    if curriculum == "Old Curriculum":
        df_all = get_student_gpa_old(selected_prof)
    else:
        df_all = get_student_gpa_new(selected_prof)

    # ======================
    # Dynamic Filters
    # ======================
    if not df_all.empty:
        courses = sorted(df_all["Course"].dropna().unique())
        years = sorted(df_all["YearLevel"].dropna().astype(str).unique())
        subjects = sorted(df_all["Subject"].dropna().unique())
        sections = sorted(df_all["Section"].dropna().unique()) if curriculum != "Old Curriculum" else []
    else:
        courses, years, subjects, sections = [], [], [], []

    selected_course = st.selectbox("Filter by Course:", ["All"] + courses)
    selected_year = st.selectbox("Filter by Year Level:", ["All"] + years)
    selected_subject = st.selectbox("Filter by Subject:", ["All"] + subjects)

    selected_section = None
    if curriculum != "Old Curriculum":
        selected_section = st.selectbox("Filter by Section:", ["All"] + sections)
        if selected_section == "All":
            selected_section = None

    # ======================
    # Filtered Data
    # ======================
    if curriculum == "Old Curriculum":
        df = get_student_gpa_old(
            selected_prof,
            None if selected_course == "All" else selected_course,
            None if selected_year == "All" else selected_year,
            None if selected_subject == "All" else selected_subject,
        )
    else:
        df = get_student_gpa_new(
            selected_prof,
            None if selected_course == "All" else selected_course,
            None if selected_year == "All" else selected_year,
            None if selected_subject == "All" else selected_subject,
            selected_section
        )

    # ======================
    # Display
    # ======================
    if not df.empty:
        gpa_pivot = df.pivot_table(
            index=["Student ID", "Name"],
            columns="Semester",
            values="GPA",
            aggfunc="mean"
        ).reset_index()

        # Add trend
        gpa_pivot["Overall Trend"] = [
            calculate_trend([row[col] for col in gpa_pivot.columns if col not in ["Student ID", "Name"]])
            for _, row in gpa_pivot.iterrows()
        ]

        st.markdown(f"### 👨‍🏫 Professor: **{selected_prof}**")

        st.subheader("📑 GPA Table")
        st.dataframe(gpa_pivot, use_container_width=True)

        fig = px.line(
            df.dropna(),
            x="Semester",
            y="GPA",
            color="Name",
            markers=True,
            title=f"📈 GPA Trends"
        )
        st.plotly_chart(fig, use_container_width=True)

        # PDF Download
        pdf_buffer = create_pdf(df, fig, selected_prof, curriculum, selected_section)
        st.download_button(
            label="📥 Download Student Progress PDF",
            data=pdf_buffer,
            file_name=f"StudentProgress_{selected_prof}.pdf",
            mime="application/pdf"
        )

    else:
        st.warning(f"No GPA data available for {selected_prof} in {curriculum}.")


# ==========================
# Run Display
# ==========================
if __name__ == "__main__":
    display_student_progress()
