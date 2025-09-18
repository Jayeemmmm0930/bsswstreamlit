import os
import io
import pickle
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet

from data_collection import data_collections


# ==========================
# OLD Curriculum Fetcher
# ==========================
def get_old_curriculum(student_id):
    students = data_collections["students"]
    subjects = {s["_id"]: s for s in data_collections["subjects"]}
    semesters = {s["_id"]: s for s in data_collections["semesters"]}
    grades = data_collections["grades"]

    student = next((s for s in students if s["_id"] == student_id), None)
    if not student:
        return None, []

    result = []
    for g in [x for x in grades if x["StudentID"] == student_id]:
        sem = semesters.get(g["SemesterID"], {})
        for i, sub_id in enumerate(g.get("SubjectCodes", [])):
            sub = subjects.get(sub_id, {})
            result.append({
                "YearLevel": student.get("YearLevel", ""),
                "Semester": sem.get("Semester", ""),
                "SchoolYear": sem.get("SchoolYear", ""),
                "SubjectCode": sub_id,
                "Description": sub.get("Description", ""),
                "LecHours": sub.get("Lec", 0) if "Lec" in sub else 0,
                "LabHours": sub.get("Lab", 0) if "Lab" in sub else 0,
                "Units": sub.get("Units", 0),
                "Prerequisites": sub.get("Prerequisites", ""),
                "Teacher": (g.get("Teachers") or [""] * 5)[i],
                "Grade": (g.get("Grades") or [""] * 5)[i]
            })

    df = pd.DataFrame(result)
    return student, df


# ==========================
# NEW Curriculum Fetcher
# ==========================
def get_new_curriculum(student_id):
    students = data_collections["newStudents"]
    subjects = {s["_id"]: s for s in data_collections["newSubjects"]}
    semesters = {s["_id"]: s for s in data_collections["newSemesters"]}
    grades = data_collections["newGrades"]
    curriculums = data_collections["curriculums"]

    student = next((s for s in students if s["_id"] == student_id), None)
    if not student:
        return None, []

    # ✅ Match curriculum for this student
    curriculum = next(
        (c for c in curriculums
         if c["courseCode"] == student["courseCode"] and c["curriculumYear"] == student["curriculumYear"]),
        None
    )

    prereq_map = {}
    if curriculum:
        for subj in curriculum.get("subjects", []):
            prereq_map[subj["subjectCode"]] = subj.get("prerequisite", None)

    result = []
    for g in [x for x in grades if x["studentId"] == student_id]:
        sem = semesters.get(g["termId"], {})
        sub = subjects.get(g["subjectId"], {})

        subject_code = sub.get("subjectCode", "")

        result.append({
            "YearLevel": sub.get("yearLevel", ""),
            "Semester": sub.get("semester", ""),
            "SchoolYear": sem.get("academicYear", ""),
            "SubjectCode": subject_code,
            "Description": sub.get("subjectName", ""),
            "LecHours": sub.get("lec", 0),
            "LabHours": sub.get("lab", 0),
            "Units": sub.get("units", 0),
            # ✅ pull prerequisites from curriculum
            "Prerequisites": prereq_map.get(subject_code, ""),
            "Teacher": "",
            "Grade": g.get("numericGrade", "")
        })

    df = pd.DataFrame(result)
    return student, df


# ==========================
# Helpers
# ==========================
def normalize_semester(val):
    """Convert semester text/number into 1 or 2"""
    if str(val).lower() in ["1", "first", "firstsem", "first semester"]:
        return 1
    if str(val).lower() in ["2", "second", "secondsem", "second semester"]:
        return 2
    return None


# ==========================
# RENDER VIEW
# ==========================
def curriculum_view():
    st.header("📚 Curriculum Subjects and Grades Viewer")

    # --- Course Selection ---
    st.subheader("🔎 Course Selection")
    if st.session_state.curriculum_type == "Old Curriculum":
        courses = sorted(set(s["Course"] for s in data_collections["students"]))
    else:
        courses = sorted(set(s["courseCode"] for s in data_collections["newStudents"]))

    course_selected = st.selectbox("Choose a course:", [""] + courses)
    if not course_selected:
        st.info("Please select a course to continue.")
        return

    # --- Student Selection ---
    st.subheader("🎓 Student Selection")
    if st.session_state.curriculum_type == "Old Curriculum":
        student_options = [
            {"id": s["_id"], "label": f"{s['_id']} - {s['Name']}"}
            for s in data_collections["students"] if s["Course"] == course_selected
        ]
    else:
        student_options = [
            {"id": s["_id"], "label": f"{s['_id']} - {s['name']}"}
            for s in data_collections["newStudents"] if s["courseCode"] == course_selected
        ]

    if not student_options:
        st.warning("No students found for this course.")
        return

    student_choice = st.selectbox(
        "Select Student:",
        options=student_options,
        format_func=lambda x: x["label"],
    )
    student_id = student_choice["id"] if student_choice else None
    if not student_id:
        st.info("Please select a student to view curriculum progress.")
        return

    # --- Fetch ---
    if st.session_state.curriculum_type == "Old Curriculum":
        student, df = get_old_curriculum(student_id)
    else:
        student, df = get_new_curriculum(student_id)

    if not student:
        st.warning("Student not found.")
        return
    if df.empty:
        st.warning("No subjects/grades found for this student.")
        return

    # --- Normalize semester column ---
    df["SemesterNum"] = df["Semester"].apply(normalize_semester)

    # --- Student Info ---
    st.subheader("📋 Student Information")
    if st.session_state.curriculum_type == "Old Curriculum":
        st.write(f"**Name:** {student.get('Name', '')}")
        st.write(f"**Course:** {student.get('Course', '')}")
        st.write(f"**Year Level:** {student.get('YearLevel', '')}")
    else:
        st.write(f"**Name:** {student.get('name', '')}")
        st.write(f"**Course Code:** {student.get('courseCode', '')}")
        st.write(f"**Curriculum Year:** {student.get('curriculumYear', '')}")
        st.write(f"**Year Level:** {student.get('yearLevel', '')}")

    # --- Group by Year + Semester ---
    st.subheader("📑 Curriculum Progress")
    for year, year_df in df.groupby("YearLevel"):
        st.markdown(f"## 🧑‍🎓 {year} Year")
        for sem, sem_df in year_df.groupby("SemesterNum"):
            sem_name = "First Semester" if sem == 1 else "Second Semester" if sem == 2 else f"Semester {sem}"
            st.markdown(f"### 📘 {sem_name}")

            display_df = sem_df[[
                "SubjectCode", "Description", "Grade", "LecHours", "LabHours", "Units", "Prerequisites"
            ]]

            def highlight_failed(val):
                try:
                    return "color: red;" if float(val) < 75 else ""
                except:
                    return ""

            styled_df = (
                display_df.style
                .applymap(highlight_failed, subset=["Grade"])
                .format(precision=2, na_rep="")
            )

            st.dataframe(
                styled_df,
                use_container_width=True,
                hide_index=True
            )

    # ============================================================
    # ✅ Predicted Subjects for Next Semester (based on curriculum + prerequisites)
    # ============================================================
    st.subheader("🔮 Predicted Subjects for Next Semester")

    if df.empty:
        st.info("No subject history available to predict.")
        return

    # Get last year + sem the student has taken
    current_year = pd.to_numeric(df["YearLevel"], errors="coerce").max()
    current_sem = df[df["YearLevel"].astype(str) == str(current_year)]["SemesterNum"].max()

    # Next sem calculation
    if current_sem == 1:
        next_year, next_sem = current_year, 2
    else:
        next_year, next_sem = current_year + 1, 1

    st.write(f"➡️ Next semester prediction: **Year {next_year}, Sem {next_sem}**")

    # --- Get curriculum subjects for this course ---
    curriculum = None
    if st.session_state.curriculum_type != "Old Curriculum":
        curriculum = next(
            (c for c in data_collections["curriculums"]
             if c["courseCode"] == student["courseCode"] and c["curriculumYear"] == student["curriculumYear"]),
            None
        )

    if not curriculum:
        st.warning("Curriculum structure not found for this student.")
        return

    # --- Build curriculum DataFrame ---
    all_subjects = pd.DataFrame(curriculum.get("subjects", []))
    all_subjects = all_subjects.rename(columns={
        "subjectCode": "SubjectCode",
        "subjectName": "Description",
        "yearLevel": "YearLevel",
        "semester": "SemesterNum",
        "units": "Units",
        "lec": "LecHours",
        "lab": "LabHours",
        "prerequisite": "Prerequisites"
    })

    # --- Failed subjects (must be repeated) ---
    failed_subjects = df[pd.to_numeric(df["Grade"], errors="coerce").fillna(0) < 75]
    failed_codes = failed_subjects["SubjectCode"].tolist()

    recommended, blocked = [], []

    # ✅ Add failed subjects back to recommended
    for _, row in failed_subjects.iterrows():
        recommended.append(row)

    # --- Next semester subjects from curriculum ---
    next_subjects = all_subjects[
        (pd.to_numeric(all_subjects["YearLevel"], errors="coerce") == next_year) &
        (pd.to_numeric(all_subjects["SemesterNum"], errors="coerce") == next_sem)
    ]

    # --- Check prerequisites ---
    passed_codes = df[pd.to_numeric(df["Grade"], errors="coerce").fillna(0) >= 75]["SubjectCode"].tolist()

    for _, row in next_subjects.iterrows():
        prereq = str(row["Prerequisites"]).split(",") if row["Prerequisites"] else []
        prereq = [p.strip() for p in prereq if p.strip()]

        if any(p not in passed_codes for p in prereq):
            blocked.append(row)
        else:
            recommended.append(row)

    # --- Display ---
    if recommended:
        st.success("✅ Recommended subjects for next semester (including repeats):")
        st.dataframe(
            pd.DataFrame(recommended).style.format(precision=2, na_rep=""),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.warning("No recommended subjects available.")

    if blocked:
        st.error("⛔ Blocked subjects (due to failed or missing prerequisites):")
        st.dataframe(
            pd.DataFrame(blocked).style.format(precision=2, na_rep=""),
            use_container_width=True,
            hide_index=True
        )

    # ============================================================
    # 📊 GRAPH + PDF Export + PKL Caching
    # ============================================================
    st.subheader("📊 Grade Distribution")

    fig, ax = plt.subplots()
    df["GradeNum"] = pd.to_numeric(df["Grade"], errors="coerce")
    df["GradeNum"].dropna().hist(ax=ax, bins=10)
    ax.set_title("Grade Distribution")
    ax.set_xlabel("Grades")
    ax.set_ylabel("Frequency")

    st.pyplot(fig)

    # Save chart as PNG in memory (not disk)
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)

    # --- PDF Export ---
    if st.button("📥 Download Curriculum Report as PDF"):
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph("Curriculum Report", styles["Title"]))
        elements.append(Spacer(1, 12))
        elements.append(Paragraph(f"Name: {student.get('Name', student.get('name', ''))}", styles["Normal"]))
        elements.append(Paragraph(f"Course: {student.get('Course', student.get('courseCode', ''))}", styles["Normal"]))
        elements.append(Spacer(1, 12))

        # Insert graph image
        buf.seek(0)
        elements.append(Image(buf, width=400, height=300))

        doc.build(elements)
        pdf_buffer.seek(0)

        st.download_button(
            label="📥 Download PDF",
            data=pdf_buffer,
            file_name=f"{student_id}_curriculum_report.pdf",
            mime="application/pdf"
        )

    # --- Save PKL Cache ---
    os.makedirs("cache", exist_ok=True)
    cache_file = os.path.join("cache", f"{student_id}_curriculum.pkl")
    with open(cache_file, "wb") as f:
        pickle.dump(df, f)
    st.success(f"✅ Progress saved to cache: {cache_file}")
