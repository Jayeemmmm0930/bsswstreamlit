import streamlit as st
import pandas as pd
import numpy as np
import io
import os
import pickle
import plotly.express as px

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

from data_collection import data_collections


# ==========================
# Student Fetch Helper
# ==========================
def get_logged_in_student():
    curriculum = st.session_state.get("curriculum_type", "Old Curriculum")
    role = st.session_state.get("role", None)
    username = st.session_state.get("username", None)

    if role == "student":
        if curriculum == "Old Curriculum":
            students = {s["_id"]: s for s in data_collections["students"]}
            return students.get(username)
        else:
            students = {s["_id"]: s for s in data_collections["newStudents"]}
            return next(
                (s for s in students.values()
                 if s.get("studentNumber") == username or s["_id"] == username),
                None
            )
    return None


# ==========================
# Helper: Remarks
# ==========================
def get_remark(student_grade, class_avg):
    if student_grade is None:
        return "No grade available"
    if student_grade >= class_avg + 5:
        return "Above class average—excellent standing"
    elif student_grade <= class_avg - 5:
        return "Below class average—needs additional support"
    else:
        return "Slightly above average—solid performance"


# ==========================
# Old Curriculum Report
# ==========================
def get_old_curriculum_comparison(student_id):
    grades = data_collections["grades"]
    subjects = {s["_id"]: s for s in data_collections["subjects"]}

    student_grades = [g for g in grades if g["StudentID"] == student_id]

    records = []
    for g in student_grades:
        for idx, subject_id in enumerate(g["SubjectCodes"]):
            subject = subjects.get(subject_id, {})
            grade = g["Grades"][idx]

            all_grades = []
            for gr in grades:
                for i, subj in enumerate(gr["SubjectCodes"]):
                    if subj == subject_id and gr["Grades"][i] is not None:
                        all_grades.append(gr["Grades"][i])

            if not all_grades:
                continue

            total_students = len(all_grades)
            class_avg = np.mean(all_grades)

            rank = None
            if grade is not None:
                rank = 1 + sum(1 for gr in all_grades if gr > grade)
                rank = min(max(1, rank), total_students)

            remark = get_remark(grade, class_avg)

            records.append({
                "Course Code": subject_id,
                "Course Name": subject.get("Description", ""),
                "Total Students": total_students,
                "Your Grade (%)": grade,
                "Class Average (%)": class_avg,
                "Your Rank": f"{rank} of {total_students}" if rank else "",
                "Remark": remark
            })

    return pd.DataFrame(records)


# ==========================
# New Curriculum Report
# ==========================
def get_new_curriculum_comparison(student_id):
    grades = data_collections["newGrades"]
    subjects = {s["_id"]: s for s in data_collections["newSubjects"]}
    sections = data_collections.get("newSections", [])

    student_grades = [g for g in grades if g.get("studentId") == student_id]

    records = []
    for g in student_grades:
        subject_id = g.get("subjectId")
        subject = subjects.get(subject_id, {})
        grade = g.get("numericGrade", None)

        section = next(
            (sec for sec in sections if sec.get("subjectId") == subject_id and student_id in sec.get("studentIds", [])),
            None
        )
        if not section:
            continue

        classmates = section.get("studentIds", [])
        all_grades = []
        for sid in classmates:
            sg = next(
                (x for x in grades
                 if x.get("studentId") == sid
                 and x.get("subjectId") == subject_id
                 and x.get("numericGrade") is not None),
                None
            )
            if sg:
                all_grades.append(sg.get("numericGrade"))

        if not all_grades:
            continue

        total_students = len(all_grades)
        class_avg = np.mean(all_grades)

        rank = None
        if grade is not None:
            rank = 1 + sum(1 for gr in all_grades if gr > grade)
            rank = min(max(1, rank), total_students)

        remark = get_remark(grade, class_avg)

        records.append({
            "Course Code": subject.get("subjectCode", ""),
            "Course Name": subject.get("subjectName", ""),
            "Total Students": total_students,
            "Your Grade (%)": grade,
            "Class Average (%)": class_avg,
            "Your Rank": f"{rank} of {total_students}" if rank is not None else "",
            "Remark": remark
        })

    return pd.DataFrame(records)


# ==========================
# PDF Export
# ==========================
def generate_pdf(df, fig, student_name):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    elements = []

    # Title
    elements.append(Paragraph(f"Comparison with Class Average - {student_name}", styles["Title"]))
    elements.append(Spacer(1, 12))

    # Table data
    table_data = [df.columns.tolist()] + df.astype(str).values.tolist()
    table = Table(table_data, repeatRows=1, hAlign="LEFT")

    # Base style
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
    ])

    # Column alignment
    col_idx = {c: i for i, c in enumerate(df.columns)}
    if "Course Code" in col_idx:
        style.add("ALIGN", (col_idx["Course Code"], 1), (col_idx["Course Code"], -1), "LEFT")
    if "Course Name" in col_idx:
        style.add("ALIGN", (col_idx["Course Name"], 1), (col_idx["Course Name"], -1), "LEFT")
    if "Total Students" in col_idx:
        style.add("ALIGN", (col_idx["Total Students"], 1), (col_idx["Total Students"], -1), "RIGHT")
    if "Your Grade (%)" in col_idx:
        style.add("ALIGN", (col_idx["Your Grade (%)"], 1), (col_idx["Your Grade (%)"], -1), "RIGHT")
    if "Class Average (%)" in col_idx:
        style.add("ALIGN", (col_idx["Class Average (%)"], 1), (col_idx["Class Average (%)"], -1), "RIGHT")
    if "Your Rank" in col_idx:
        style.add("ALIGN", (col_idx["Your Rank"], 1), (col_idx["Your Rank"], -1), "CENTER")
    if "Remark" in col_idx:
        style.add("ALIGN", (col_idx["Remark"], 1), (col_idx["Remark"], -1), "CENTER")

    # Row striping + conditional formatting
    for i, row in df.iterrows():
        row_idx = i + 1
        bg_color = colors.whitesmoke if row_idx % 2 == 0 else colors.white
        style.add("BACKGROUND", (0, row_idx), (-1, row_idx), bg_color)

        # Missing grade
        if pd.isna(row["Your Grade (%)"]):
            style.add("BACKGROUND", (col_idx["Your Grade (%)"], row_idx),
                      (col_idx["Your Grade (%)"], row_idx), colors.HexColor("#FFFACD"))
            style.add("TEXTCOLOR", (col_idx["Your Grade (%)"], row_idx),
                      (col_idx["Your Grade (%)"], row_idx), colors.black)
        else:
            try:
                grade_val = float(row["Your Grade (%)"])
                if grade_val < 60:
                    style.add("TEXTCOLOR", (col_idx["Your Grade (%)"], row_idx),
                              (col_idx["Your Grade (%)"], row_idx), colors.red)
                    style.add("FONTNAME", (col_idx["Your Grade (%)"], row_idx),
                              (col_idx["Your Grade (%)"], row_idx), "Helvetica-Bold")
            except Exception:
                pass

    table.setStyle(style)
    elements.append(table)
    elements.append(Spacer(1, 20))

    # Chart styling
    fig.update_traces(marker=dict(line=dict(width=1, color="black")))
    fig.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(size=10),
    )

    # Save chart as PNG
    img_buffer = io.BytesIO()
    fig.write_image(img_buffer, format="png", scale=2)
    img_buffer.seek(0)
    elements.append(Image(img_buffer, width=500, height=300))

    doc.build(elements)
    buffer.seek(0)
    return buffer


# ==========================
# Main Viewer
# ==========================
def comparison_with_class_average():
    st.header("📊 Comparison with Class Average")

    curriculum = st.session_state.get("curriculum_type", "Old Curriculum")
    role = st.session_state.get("role", None)

    student = get_logged_in_student()
    if role == "student" and not student:
        st.error("⚠️ Could not find your student record.")
        return

    if role == "student":
        student_id = student["_id"]
        student_name = student.get("Name", student.get("name", "Unknown"))
        st.subheader(f"Student: {student_id} – {student_name}")
    else:
        students = data_collections.get(
            "students" if curriculum == "Old Curriculum" else "newStudents", []
        )
        if not students:
            st.warning("No students found.")
            return

        search_query = st.text_input("🔍 Search Student (by ID or Name)").lower().strip()
        student_options = {s["_id"]: s.get("Name") or s.get("name") for s in students}

        if search_query:
            filtered_options = {
                sid: name for sid, name in student_options.items()
                if search_query in sid.lower() or (name and search_query in name.lower())
            }
        else:
            filtered_options = student_options

        if not filtered_options:
            st.warning("No matching students found.")
            return

        student_id = st.selectbox(
            "Select Student",
            options=list(filtered_options.keys()),
            format_func=lambda x: filtered_options[x],
            key="comparison_student_selector"
        )
        student_name = filtered_options[student_id]
        st.subheader(f"Student: {student_id} – {student_name}")

    # Load comparison data
    if curriculum == "Old Curriculum":
        df = get_old_curriculum_comparison(student_id)
    else:
        df = get_new_curriculum_comparison(student_id)

    if df.empty:
        st.warning("No data available for this student.")
        return

    # Format table for Streamlit
    df_display = df.copy()
    df_display["Your Grade (%)"] = df_display["Your Grade (%)"].apply(
        lambda x: f"{x}%" if pd.notna(x) else "No grade"
    )
    df_display["Class Average (%)"] = df_display["Class Average (%)"].apply(
        lambda x: f"{round(x,1)}%" if pd.notna(x) else ""
    )

    st.subheader("📑 Detailed Report")
    st.dataframe(
        df_display.style.applymap(
            lambda v: "background-color:#FFFACD; color:black;" if v == "No grade" else ""
        )
    )

    # Chart
    st.subheader("📊 Graph: Your Grade vs Class Average")
    fig = px.bar(
        df.dropna(subset=["Your Grade (%)"]),
        x="Course Code",
        y=["Your Grade (%)", "Class Average (%)"],
        barmode="group",
        title="Grades vs Class Average",
        labels={"value": "Percentage", "variable": "Legend"},
        color_discrete_map={
            "Your Grade (%)": "seagreen",
            "Class Average (%)": "steelblue"
        }
    )
    st.plotly_chart(fig, use_container_width=True)

    # Cache save
    os.makedirs("cache", exist_ok=True)
    cache_file = f"cache/{student_id}_comparison.pkl"
    with open(cache_file, "wb") as f:
        pickle.dump(df, f)

    # PDF export
    pdf_buffer = generate_pdf(df, fig, student_name)
    st.download_button(
        label="📥 Download PDF Report",
        data=pdf_buffer,
        file_name=f"{student_id}_comparison.pdf",
        mime="application/pdf"
    )


if __name__ == "__main__":
    comparison_with_class_average()
