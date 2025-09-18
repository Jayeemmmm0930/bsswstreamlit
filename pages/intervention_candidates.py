import os
import io
import pickle
import pandas as pd
import streamlit as st
import plotly.express as px

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

from data_collection import data_collections  # your MongoDB collections dict


# ==========================
# Cache Helpers
# ==========================
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def save_cache(data, filename):
    with open(os.path.join(CACHE_DIR, filename), "wb") as f:
        pickle.dump(data, f)

def load_cache(filename):
    filepath = os.path.join(CACHE_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, "rb") as f:
            return pickle.load(f)
    return None


# ==========================
# Old Curriculum Intervention Candidates
# ==========================
def get_intervention_old(prof_name):
    students = {s["_id"]: s for s in data_collections["students"]}
    subjects = {s["_id"]: s for s in data_collections["subjects"]}
    grades = data_collections["grades"]

    rows = []
    for g in grades:
        student = students.get(g["StudentID"], {})
        for idx, subj_code in enumerate(g["SubjectCodes"]):
            teacher = g["Teachers"][idx] if idx < len(g["Teachers"]) else None
            if teacher != prof_name:
                continue

            subj = subjects.get(subj_code, {})
            grade = g["Grades"][idx] if idx < len(g["Grades"]) else None

            # risk logic
            if grade is None or grade == "" or str(grade).upper() in ["INC", "N/A"]:
                risk_flag = "Missing Grade"
                grade_display = "INC"
            elif isinstance(grade, (int, float)):
                if grade < 60:
                    risk_flag = "At Risk (<60)"
                    grade_display = grade
                elif grade < 75:
                    risk_flag = "Fail (<75)"
                    grade_display = grade
                else:
                    continue  # Passing, skip
            else:
                continue

            rows.append({
                "Student ID": g["StudentID"],
                "Student Name": student.get("Name", "Unknown"),
                "Course Code": subj_code,
                "Course Name": subj.get("Description", "Unknown"),
                "Current Grade": grade_display,
                "Risk Flag": risk_flag
            })

    return pd.DataFrame(rows)


# ==========================
# New Curriculum Intervention Candidates
# ==========================
def get_intervention_new(professor_id):
    students = {s["_id"]: s for s in data_collections["newStudents"]}
    subjects = {s["_id"]: s for s in data_collections["newSubjects"]}
    professors = {p["_id"]: p for p in data_collections["newProfessors"]}
    grades = data_collections["newGrades"]
    curriculums = {c["_id"]: c for c in data_collections["curriculums"]}

    if professor_id not in professors:
        return pd.DataFrame(), "Unknown"

    professor_fullname = professors[professor_id].get("fullName", professors[professor_id].get("name", "Unknown"))

    rows = []
    for g in grades:
        subj = subjects.get(g["subjectId"], {})
        if subj.get("professorId") != professor_id:
            continue

        student = students.get(g["studentId"], {})
        if not student:
            continue

        # fetch curriculum
        course_code = student.get("courseCode")
        year_level = student.get("yearLevel")
        curriculum = next((c for c in curriculums.values() if c.get("courseCode") == course_code), None)

        # check if subject is part of curriculum at/before current year level
        allowed_subjects = []
        if curriculum:
            allowed_subjects = [
                s["subjectCode"] for s in curriculum.get("subjects", [])
                if s.get("yearLevel", 0) <= year_level
            ]

        subj_code = subj.get("subjectCode", "")
        if subj_code not in allowed_subjects:
            continue  # skip future subjects

        grade = g.get("numericGrade")
        status = g.get("status")

        # risk logic
        if status and status.lower() == "dropout":
            risk_flag = "Dropout"
            grade_display = grade if grade not in [None, ""] else "INC"
        elif grade is None or grade == "" or str(grade).upper() in ["INC", "N/A"]:
            risk_flag = "Missing Grade"
            grade_display = "INC"
        elif isinstance(grade, (int, float)):
            if grade < 60:
                risk_flag = "At Risk (<60)"
                grade_display = grade
            elif grade < 75:
                risk_flag = "Fail (<75)"
                grade_display = grade
            else:
                continue  # Passing, skip
        else:
            continue

        rows.append({
            "Student ID": student.get("studentNumber", ""),
            "Student Name": student.get("name", "Unknown"),
            "Course Code": subj_code,
            "Course Name": subj.get("subjectName", "Unknown"),
            "Current Grade": grade_display,
            "Risk Flag": risk_flag
        })

    return pd.DataFrame(rows), professor_fullname


# ==========================
# PDF Export
# ==========================
def export_pdf(df, faculty, curriculum):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("4. Intervention Candidates List", styles["Heading2"]))
    elements.append(Paragraph(
        "- Lists students at academic risk based on current semester data (e.g., low grades, missing grades)",
        styles["Normal"]
    ))
    elements.append(Paragraph(f"Faculty Name: {faculty} ({curriculum})", styles["Normal"]))
    elements.append(Spacer(1, 12))

    if df.empty:
        elements.append(Paragraph("No intervention candidates found.", styles["Normal"]))
    else:
        data = [list(df.columns)] + df.values.tolist()
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    return buffer


# ==========================
# Display
# ==========================
def display_intervention_candidates():
    st.title("⚠️ Intervention Candidates List")
    curriculum = st.session_state.curriculum_type
    role = st.session_state.role
    username = st.session_state.username  # professorId if faculty

    # ========== OLD CURRICULUM ==========
    if curriculum == "Old Curriculum":
        all_profs = sorted({t for g in data_collections["grades"] for t in g.get("Teachers", []) if t})
        if role == "professor":
            selected_prof = username  # assume matches old teacher names
        else:
            selected_prof = st.selectbox("Select Professor:", all_profs)

        cache_key = f"intervention_{curriculum}_{selected_prof}.pkl"
        df = load_cache(cache_key)

        if df is None:
            df = get_intervention_old(selected_prof)
            save_cache(df, cache_key)

        faculty_name = selected_prof

    # ========== NEW CURRICULUM ==========
    else:
        professors = data_collections["newProfessors"]

        if role == "professor":
            # username is professorId
            df, faculty_name = get_intervention_new(username)
        else:
            all_profs = sorted([p.get("fullName", p.get("name", "Unknown")) for p in professors])
            selected_prof = st.selectbox("Select Professor:", all_profs)
            prof_id = next((p["_id"] for p in professors if p.get("fullName", p.get("name")) == selected_prof), None)
            df, faculty_name = get_intervention_new(prof_id)

        cache_key = f"intervention_{curriculum}_{faculty_name}.pkl"
        if load_cache(cache_key) is None:
            save_cache(df, cache_key)

    # ===== DISPLAY =====
    if not df.empty:
        st.subheader(f"Intervention Candidates — {faculty_name}")
        st.dataframe(df, use_container_width=True)

        # 📊 Risk Flag Distribution
        fig = px.histogram(df, x="Risk Flag", color="Risk Flag", text_auto=True)
        st.plotly_chart(fig, use_container_width=True)

        # 📥 PDF Download
        pdf_buffer = export_pdf(df, faculty_name, curriculum)
        st.download_button(
            label="📥 Download PDF",
            data=pdf_buffer,
            file_name=f"intervention_candidates_{faculty_name}_{curriculum}.pdf",
            mime="application/pdf"
        )
    else:
        st.info(f"No intervention candidates found for {faculty_name} in {curriculum}.")


# ==========================
# Run
# ==========================
if __name__ == "__main__":
    display_intervention_candidates()
