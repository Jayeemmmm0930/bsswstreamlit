import streamlit as st
import pandas as pd
import io
import os
import pickle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from data_collection import data_collections


# ==========================
# Student Fetcher
# ==========================
def get_student_by_id(curriculum, student_id):
    if curriculum == "Old Curriculum":
        students = {s["_id"]: s for s in data_collections["students"]}
        return students.get(student_id)
    else:
        students = {s["_id"]: s for s in data_collections["newStudents"]}
        return students.get(student_id)
    return None


def get_logged_in_student():
    curriculum = st.session_state.get("curriculum_type", "Old Curriculum")
    role = st.session_state.get("role", None)
    username = st.session_state.get("username", None)

    if role == "student":
        return get_student_by_id(curriculum, username)
    return None


# ==========================
# Grade Display Helpers
# ==========================
def style_grades(df: pd.DataFrame):
    df = df.copy().reset_index(drop=True)

    def highlight(val):
        if val == "No grade":
            return "background-color: #FFFACD; color: black;"
        try:
            if float(val) < 75:
                return "color: red; font-weight: bold;"
        except:
            pass
        return ""

    if "Grade" in df.columns:
        styled = df.style.applymap(highlight, subset=["Grade"])
        # wrap prerequisites column
        if "Prerequisites" in df.columns:
            styled = styled.set_properties(
                subset=["Prerequisites"],
                **{"white-space": "normal", "word-wrap": "break-word", "max-width": "200px"}
            )
        return styled
    else:
        return df.style


# ==========================
# PDF Export
# ==========================
def generate_pdf(grouped, student, curriculum):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    wrap_style = ParagraphStyle(name="Wrap", fontSize=8, leading=10)
    elements = []

    # --- Title ---
    elements.append(Paragraph("Curriculum Prospectus", styles["Title"]))
    elements.append(Spacer(1, 12))

    # --- Student Info ---
    if curriculum == "Old Curriculum":
        elements.append(Paragraph(f"Student ID: {student['_id']}", styles["Normal"]))
        elements.append(Paragraph(f"Student: {student['Name']}", styles["Normal"]))
        elements.append(Paragraph(f"Course: {student['Course']}", styles["Normal"]))
        elements.append(Paragraph(f"Year Level: {student['YearLevel']}", styles["Normal"]))
    else:
        elements.append(Paragraph(f"Student ID: {student['_id']}", styles["Normal"]))
        elements.append(Paragraph(f"Student: {student['name']}", styles["Normal"]))
        elements.append(Paragraph(f"Course: {student['courseCode']}", styles["Normal"]))
        elements.append(Paragraph(f"Curriculum Year: {student['curriculumYear']}", styles["Normal"]))
        elements.append(Paragraph(f"Year Level: {student.get('yearLevel', 'N/A')}", styles["Normal"]))

    elements.append(Spacer(1, 12))

    # --- Add curriculum tables ---
    for year_label, semesters in grouped.items():
        elements.append(Paragraph(f"<b>{year_label}</b>", styles["Heading1"]))
        elements.append(Spacer(1, 6))

        for sem_label, df in semesters.items():
            elements.append(Paragraph(f"{sem_label}", styles["Heading2"]))
            elements.append(Spacer(1, 6))

            expected_cols = [
                "Subject Code", "Subject Name", "Grade",
                "LecHours", "LabHours", "Units", "Prerequisites"
            ]
            for col in expected_cols:
                if col not in df.columns:
                    df[col] = ""

            df_display = df[expected_cols].copy()
            df_display["Grade"] = df_display["Grade"].apply(
                lambda x: "No grade" if pd.isna(x) or str(x).strip() == "" else x
            )

            # wrap prerequisites for PDF
            table_data = [expected_cols]
            for row in df_display.astype(str).values.tolist():
                row[-1] = Paragraph(row[-1] if row[-1] else "None", wrap_style)
                table_data.append(row)

            table = Table(table_data, repeatRows=1,
                          colWidths=[70, 200, 60, 60, 60, 50, 180])

            style = TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E3B4E")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ])

            # highlight grades
            for i, row in df_display.iterrows():
                grade_val = row["Grade"]
                if grade_val == "No grade":
                    style.add("BACKGROUND", (2, i + 1), (2, i + 1), colors.HexColor("#FFFACD"))
                    style.add("TEXTCOLOR", (2, i + 1), (2, i + 1), colors.black)
                elif str(grade_val).replace(".", "", 1).isdigit() and float(grade_val) < 75:
                    style.add("TEXTCOLOR", (2, i + 1), (2, i + 1), colors.red)

            table.setStyle(style)
            elements.append(table)
            elements.append(Spacer(1, 12))

    doc.build(elements)
    buffer.seek(0)
    return buffer


# ==========================
# Save to Cache
# ==========================
def save_to_cache(student, grouped):
    os.makedirs("cache", exist_ok=True)
    for year_label, semesters in grouped.items():
        for sem_label, df in semesters.items():
            filename = f"cache/{student.get('Name', student.get('name')).replace(' ', '_')}_{year_label}_{sem_label.replace(' ', '_')}.pkl"
            with open(filename, "wb") as f:
                pickle.dump(df, f)


# ==========================
# Main Viewer
# ==========================
def student_curriculum_viewer():
    role = st.session_state.get("role", None)
    curriculum = st.session_state.get("curriculum_type", "Old Curriculum")

    # --- Select student if Admin ---
    if role == "admin":
        if curriculum == "Old Curriculum":
            all_students = list(data_collections["students"])
            name_map = {s["_id"]: s["Name"] for s in all_students}
        else:
            all_students = list(data_collections["newStudents"])
            name_map = {s["_id"]: s["name"] for s in all_students}

        search = st.text_input("🔍 Search Student by Name")
        filtered = {sid: name for sid, name in name_map.items()
                    if search.lower() in name.lower()}

        student_id = st.selectbox(
            "Select Student",
            options=list(filtered.keys()),
            format_func=lambda x: filtered[x]
        )
        student = get_student_by_id(curriculum, student_id)
    else:
        student = get_logged_in_student()

    if not student:
        st.error("No student selected or logged in.")
        return

    st.subheader("Curriculum Prospectus Viewer")

    # --- Student Info on Screen ---
    if curriculum == "Old Curriculum":
        st.markdown(f"**Student ID:** {student['_id']}")
        st.markdown(f"**Student Name:** {student['Name']}")
        st.markdown(f"**Course:** {student['Course']}")
        st.markdown(f"**Year Level:** {student['YearLevel']}")
    else:
        st.markdown(f"**Student ID:** {student['_id']}")
        st.markdown(f"**Student Name:** {student['name']}")
        st.markdown(f"**Course:** {student['courseCode']}")
        st.markdown(f"**Curriculum Year:** {student['curriculumYear']}")
        st.markdown(f"**Year Level:** {student.get('yearLevel', 'N/A')}")

    st.markdown("---")

    grouped = {}

    # --- Old Curriculum ---
    if curriculum == "Old Curriculum":
        st.info(f"Viewing Old Curriculum for {student['Name']}")
        grades = data_collections["grades"]
        subjects = {s["_id"]: s for s in data_collections["subjects"]}
        semesters = {s["_id"]: s for s in data_collections["semesters"]}

        # optional curriculum reference
        curriculum_subjects = {}
        for c in data_collections.get("curriculums", []):
            if c["courseCode"] == student["Course"]:
                curriculum_subjects = {s["subjectCode"]: s for s in c.get("subjects", [])}
                break

        for g in grades:
            if g["StudentID"] == student["_id"]:
                sem = semesters[g["SemesterID"]]

                year_label = sem["Semester"].split()[0] + " Year"
                sem_label = f"{sem['Semester']} ({sem['SchoolYear']})"

                df_data = []
                for idx, sub_id in enumerate(g["SubjectCodes"]):
                    subj = subjects[sub_id]
                    grade = g["Grades"][idx]

                    # handle prerequisite
                    prereq = ""
                    if subj["_id"] in curriculum_subjects:
                        prereq_val = curriculum_subjects[subj["_id"]].get("prerequisite")
                        if prereq_val:
                            if isinstance(prereq_val, list):
                                prereq = ", ".join(prereq_val)
                            else:
                                prereq = str(prereq_val)

                    df_data.append({
                        "Subject Code": subj["_id"],
                        "Subject Name": subj["Description"],
                        "Grade": grade,
                        "LecHours": "",
                        "LabHours": "",
                        "Units": subj["Units"],
                        "Prerequisites": prereq
                    })

                df = pd.DataFrame(df_data)
                grouped.setdefault(year_label, {})[sem_label] = df

    # --- New Curriculum ---
    else:
        st.info(f"Viewing New Curriculum for {student['name']}")
        newGrades = data_collections["newGrades"]
        newSubjects = {s["_id"]: s for s in data_collections["newSubjects"]}
        newSemesters = {s["_id"]: s for s in data_collections["newSemesters"]}

        # curriculum reference
        curriculum_data = None
        for c in data_collections["curriculums"]:
            if c["courseCode"] == student["courseCode"] and c["curriculumYear"] == student["curriculumYear"]:
                curriculum_data = c
                break
        curriculum_subjects = {s["subjectCode"]: s for s in curriculum_data["subjects"]} if curriculum_data else {}

        for g in newGrades:
            if g["studentId"] == student["_id"]:
                subj = newSubjects[g["subjectId"]]
                sem = newSemesters[g["termId"]]

                # Year Level from subject
                year_level_num = subj.get("yearLevel", None)
                year_map = {1: "First Year", 2: "Second Year", 3: "Third Year", 4: "Fourth Year"}
                year_label = year_map.get(year_level_num, "Unspecified Year")

                sem_label = f"{sem.get('code', 'Unknown Sem')} ({sem.get('academicYear', 'N/A')})"

                # handle prerequisite
                prereq = ""
                if subj["subjectCode"] in curriculum_subjects:
                    prereq_val = curriculum_subjects[subj["subjectCode"]].get("prerequisite")
                    if prereq_val:
                        if isinstance(prereq_val, list):
                            prereq = ", ".join(prereq_val)
                        else:
                            prereq = str(prereq_val)

                df = pd.DataFrame({
                    "Subject Code": [subj["subjectCode"]],
                    "Subject Name": [subj["subjectName"]],
                    "Grade": [g.get("numericGrade", "No grade")],
                    "LecHours": [subj["lec"]],
                    "LabHours": [subj["lab"]],
                    "Units": [subj["units"]],
                    "Prerequisites": [prereq],
                })

                if sem_label in grouped.get(year_label, {}):
                    grouped[year_label][sem_label] = pd.concat(
                        [grouped[year_label][sem_label], df], ignore_index=True
                    )
                else:
                    grouped.setdefault(year_label, {})[sem_label] = df

    # --- Display grouped prospectus ---
    for year_label, semesters in grouped.items():
        st.markdown(f"## {year_label}")
        for sem_label, df in semesters.items():
            st.markdown(f"### {sem_label}")
            st.markdown(
                style_grades(df).to_html(), unsafe_allow_html=True
            )

    # --- Save to cache ---
    save_to_cache(student, grouped)

    # --- PDF Export ---
    pdf_buffer = generate_pdf(grouped, student, curriculum)
    st.download_button(
        "📥 Download Prospectus PDF",
        data=pdf_buffer,
        file_name=f"{student.get('Name', student.get('name'))}_prospectus.pdf",
        mime="application/pdf"
    )


if __name__ == "__main__":
    student_curriculum_viewer()
