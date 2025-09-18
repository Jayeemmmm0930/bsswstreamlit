# teacher_panel.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import io

from data_collection import data_collections  # ✅ Direct import (Mongo collections dict)


# ------------------------------
# Helpers
# ------------------------------
def format_grade(val):
    """Format grade with ❌, ⭐ or numeric"""
    if pd.isna(val):
        return "❌"
    elif val >= 75:
        return f"⭐ {int(val)}"
    else:
        return f"{int(val)}"


def highlight_fails(val):
    """Highlight grades < 75 in red, leave ❌ normal"""
    if isinstance(val, str):
        if val == "❌":
            return ""
        if val.replace("⭐ ", "").isdigit() and int(val.replace("⭐ ", "")) < 75:
            return "background-color: #ffcccc"
    return ""


def generate_excel(df, filename="report.xlsx"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()


def generate_pdf(data, title="Report", type="class"):
    # Placeholder fake PDF (replace with ReportLab if needed)
    return b"%PDF-1.4\n%Fake PDF content"


# ------------------------------
# Teacher Panel
# ------------------------------
def grade_analytics():
    curriculum_type = st.session_state.get("curriculum_type", "Old Curriculum")
    role = st.session_state.get("role", "")

    if curriculum_type == "Old Curriculum":
        if role == "admin":
            run_old_teacher_panel(admin_mode=True)
        else:
            run_old_teacher_panel(admin_mode=False)
    else:
        if role == "admin":
            run_new_teacher_panel(admin_mode=True)
        else:
            run_new_teacher_panel(admin_mode=False)


# ------------------------------
# Old Curriculum Panel
# ------------------------------
def run_old_teacher_panel(admin_mode=False):
    students = data_collections["students"]
    grades = data_collections["grades"]
    subjects_data = data_collections["subjects"]
    semesters_map = {s["_id"]: s for s in data_collections["semesters"]}

    student_df = pd.DataFrame(students)
    grades_df = pd.DataFrame(grades)

    merged_df = grades_df.merge(
        student_df,
        left_on="StudentID",
        right_on="_id",
        suffixes=("_grade", "_student"),
        how="left"
    )

    teacher_names = set()
    for subj in subjects_data:
        teacher_field = subj.get("Teacher") or subj.get("teacher")
        if isinstance(teacher_field, str) and teacher_field.strip():
            teacher_names.add(teacher_field.strip())

    teacher_names = sorted(teacher_names)

    if admin_mode:
        selected_teacher_name = st.selectbox("👨‍🏫 Select Teacher (Admin Mode)", [""] + teacher_names)
    else:
        selected_teacher_name = st.session_state.get("username", "")

    if selected_teacher_name:
        subjects_map = {item.get("_id"): item for item in subjects_data if item.get("_id")}
        faculty_dashboard_old(selected_teacher_name, merged_df, subjects_map, semesters_map)


# ------------------------------
# New Curriculum Panel
# ------------------------------
def run_new_teacher_panel(admin_mode=False):
    students = data_collections["newStudents"]
    grades = data_collections["newGrades"]
    subjects = data_collections["newSubjects"]
    semesters = data_collections["newSemesters"]
    professors = data_collections["newProfessors"]

    if admin_mode:
        # ✅ Build dictionary {prof_name: prof_id}
        prof_names = {p["name"]: p["_id"] for p in professors if "name" in p and "_id" in p}
        selected_prof_name = st.selectbox("👨‍🏫 Select Professor (Admin Mode)", [""] + list(prof_names.keys()))
        if not selected_prof_name:
            return
        prof_name = selected_prof_name
        prof_id = prof_names[prof_name]
    else:
        username = st.session_state.get("username", "")
        prof = next((p for p in professors if p.get("username") == username), None)
        if not prof:
            st.error("❌ No professor record found for your account.")
            return
        prof_id = prof["_id"]
        prof_name = prof.get("name", "Unknown Professor")

    st.info(f"Welcome, **{prof_name}**! (ID: {prof_id})")

    taught_subjects = [s for s in subjects if s.get("professorId") == prof_id]

    if not taught_subjects:
        st.warning("⚠️ No subjects assigned.")
        return

    taught_subjects_df = pd.DataFrame(taught_subjects)
    subject_options = sorted(taught_subjects_df["subjectCode"].unique())
    selected_subject_code = st.radio("Select Subject:", subject_options)
    if not selected_subject_code:
        return

    subj_info = next((s for s in subjects if s["subjectCode"] == selected_subject_code), {})
    subj_id = subj_info.get("_id")

    subject_grades = []
    for g in grades:
        if g["subjectId"] == subj_id and g.get("numericGrade") is not None:
            student = next((s for s in students if s["_id"] == g["studentId"]), {})
            subject_grades.append({
                "StudentID": student.get("studentNumber"),
                "StudentName": student.get("name"),
                "Course": student.get("courseCode"),
                "YearLevel": student.get("yearLevel"),
                "NumericGrade": g["numericGrade"],
                "Status": g.get("status", "N/A"),
            })

    if not subject_grades:
        st.warning("⚠️ No grade records found.")
        return

    df_subject_grades = pd.DataFrame(subject_grades)
    faculty_dashboard_common(
        prof_name,
        selected_subject_code,
        subj_info.get("subjectName", ""),
        df_subject_grades
    )


# ------------------------------
# Old Curriculum Dashboard
# ------------------------------
def faculty_dashboard_old(selected_teacher_name, df, subjects_map, semesters_map):
    taught_subjects = []
    for subj in subjects_map.values():
        if subj.get("Teacher") == selected_teacher_name:
            taught_subjects.append(subj)

    if not taught_subjects:
        st.warning("You are not currently assigned to any subjects.")
        return

    taught_subjects_df = pd.DataFrame(taught_subjects)
    subject_options = sorted(taught_subjects_df["_id"].unique())
    selected_subject_code = st.radio("Select Subject:", subject_options)
    if not selected_subject_code:
        return

    subj_info = subjects_map.get(selected_subject_code, {})
    subject_desc = subj_info.get("Description", "N/A")

    subject_grades = []
    for _, row in df.iterrows():
        student_subjects = row.get("SubjectCodes", [])
        student_grades = row.get("Grades", [])

        if isinstance(student_subjects, list) and selected_subject_code in student_subjects:
            idx = student_subjects.index(selected_subject_code)
            grade = pd.to_numeric(student_grades[idx], errors='coerce') if len(student_grades) > idx else None
            subject_grades.append({
                "StudentID": row.get("StudentID"),
                "StudentName": row.get("Name"),
                "Course": row.get("Course"),
                "YearLevel": row.get("YearLevel"),
                "NumericGrade": grade,
            })

    if not subject_grades:
        st.warning("No grade records found for this subject.")
        return

    df_subject_grades = pd.DataFrame(subject_grades)
    faculty_dashboard_common(selected_teacher_name, selected_subject_code, subject_desc, df_subject_grades)


# ------------------------------
# Shared Dashboard (Both Curriculums)
# ------------------------------
def faculty_dashboard_common(selected_teacher_name, subject_code, subject_desc, df_subject_grades):
    st.markdown(f"## Grades Summary for {subject_code} - {subject_desc}")

    mean_grade = df_subject_grades['NumericGrade'].mean()
    median_grade = df_subject_grades['NumericGrade'].median()
    highest_grade = df_subject_grades['NumericGrade'].max()
    lowest_grade = df_subject_grades['NumericGrade'].min()

    summary_df = pd.DataFrame({
        "Mean": [f"{mean_grade:.2f}"],
        "Median": [f"{median_grade:.2f}"],
        "Highest": [f"{highest_grade:.2f}"],
        "Lowest": [f"{lowest_grade:.2f}"],
    })
    st.table(summary_df)

    # --- Histogram ---
    fig, ax = plt.subplots()
    bins = range(60, 101, 5)
    ax.hist(df_subject_grades['NumericGrade'].dropna(), bins=bins, edgecolor="black")
    ax.set_title(f"Grade Distribution - {subject_code}")
    ax.set_xlabel("Grades")
    ax.set_ylabel("Frequency")
    st.pyplot(fig)

    # --- Pass vs Fail ---
    df_subject_grades['Remarks'] = df_subject_grades['NumericGrade'].apply(
        lambda x: "Passed" if pd.notna(x) and x >= 75 else "Failed"
    )
    pass_count = (df_subject_grades['Remarks'] == 'Passed').sum()
    fail_count = (df_subject_grades['Remarks'] == 'Failed').sum()

    fig, ax = plt.subplots()
    ax.bar(["Passed", "Failed"], [pass_count, fail_count], color=["green", "red"])
    ax.set_title("Passed vs Failed")
    st.pyplot(fig)

    # --- Student Table ---
    df_subject_grades["Grade"] = df_subject_grades["NumericGrade"].apply(format_grade)

    final_table = df_subject_grades[[
        "StudentID", "StudentName", "Course", "YearLevel", "Grade", "Remarks"
    ]]

    styled_table = final_table.style.applymap(highlight_fails, subset=["Grade"])
    st.dataframe(styled_table, use_container_width=True)

    # --- Downloads ---
    st.markdown("### Download Class Report")
    excel_bytes = generate_excel(final_table)
    st.download_button(
        label="Download as Excel",
        data=excel_bytes,
        file_name=f"FacultyReport_{subject_code}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    pdf_bytes = generate_pdf(
        data={"dataframe": final_table},
        title="Faculty Class Report",
        type="class"
    )
    st.download_button(
        label="Download as PDF",
        data=pdf_bytes,
        file_name=f"FacultyReport_{subject_code}.pdf",
        mime="application/pdf"
    )


# ------------------------------
# Run the panel
# ------------------------------
if __name__ == "__main__":
    grade_analytics()
