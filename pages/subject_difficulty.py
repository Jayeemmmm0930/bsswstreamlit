import os
import io
import pickle
import pandas as pd
import streamlit as st
import plotly.express as px

# ReportLab for PDF export
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

from data_collection import data_collections


# ==========================
# Cache Setup
# ==========================
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def cache_data(filename, data):
    filepath = os.path.join(CACHE_DIR, filename)
    with open(filepath, "wb") as f:
        pickle.dump(data, f)

def load_cache(filename):
    filepath = os.path.join(CACHE_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, "rb") as f:
            return pickle.load(f)
    return None


# ==========================
# Subject Difficulty (Old Curriculum)
# ==========================
def get_subject_difficulty_old(selected_prof):
    subjects = {s["_id"]: s for s in data_collections["subjects"]}
    grades = data_collections["grades"]

    rows = []
    for g in grades:
        for idx, subj_code in enumerate(g["SubjectCodes"]):
            subj = subjects.get(subj_code, {})
            teacher = g["Teachers"][idx] if idx < len(g["Teachers"]) else subj.get("Teacher")

            if teacher != selected_prof:
                continue

            grade = g["Grades"][idx] if idx < len(g["Grades"]) else None

            if grade is None:
                status = "Dropout"
            elif isinstance(grade, (int, float)) and grade < 75:
                status = "Fail"
            else:
                status = "Pass"

            rows.append({
                "Subject Code": subj_code,
                "Subject Name": subj.get("Description", "Unknown"),
                "Status": status
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["Subject Full Name", "Fail Rate (%)", "Dropout Rate (%)", "Difficulty Level"])

    summary = df.groupby(["Subject Code", "Subject Name"]).Status.value_counts(normalize=True).unstack().fillna(0) * 100
    summary = summary.reset_index()

    summary["Fail Rate (%)"] = summary["Fail"].round(1) if "Fail" in summary else 0.0
    summary["Dropout Rate (%)"] = summary["Dropout"].round(1) if "Dropout" in summary else 0.0

    def classify_difficulty(row):
        if row["Fail Rate (%)"] >= 20 or row["Dropout Rate (%)"] >= 5:
            return "High"
        elif row["Fail Rate (%)"] >= 10 or row["Dropout Rate (%)"] >= 2:
            return "Medium"
        else:
            return "Low"

    summary["Difficulty Level"] = summary.apply(classify_difficulty, axis=1)
    summary["Subject Full Name"] = summary["Subject Code"] + " - " + summary["Subject Name"]

    return summary[["Subject Full Name", "Fail Rate (%)", "Dropout Rate (%)", "Difficulty Level"]]


# ==========================
# Subject Difficulty (New Curriculum)
# ==========================
def get_subject_difficulty_new(professor_id):
    subjects = {s["_id"]: s for s in data_collections["newSubjects"]}
    professors = {p["_id"]: p for p in data_collections["newProfessors"]}
    grades = data_collections["newGrades"]

    if professor_id not in professors:
        return pd.DataFrame(columns=["Subject Full Name", "Fail Rate (%)", "Dropout Rate (%)", "Difficulty Level"])

    rows = []
    for g in grades:
        subj = subjects.get(g["subjectId"], {})
        if subj.get("professorId") != professor_id:
            continue

        grade = g.get("numericGrade")
        status = g.get("status")

        if status and status.lower() == "dropout":
            status = "Dropout"
        elif grade is not None and isinstance(grade, (int, float)) and grade < 75:
            status = "Fail"
        else:
            status = "Pass"

        rows.append({
            "Subject Code": subj.get("subjectCode", ""),
            "Subject Name": subj.get("subjectName", "Unknown"),
            "Status": status
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["Subject Full Name", "Fail Rate (%)", "Dropout Rate (%)", "Difficulty Level"])

    summary = df.groupby(["Subject Code", "Subject Name"]).Status.value_counts(normalize=True).unstack().fillna(0) * 100
    summary = summary.reset_index()

    summary["Fail Rate (%)"] = summary["Fail"].round(1) if "Fail" in summary else 0.0
    summary["Dropout Rate (%)"] = summary["Dropout"].round(1) if "Dropout" in summary else 0.0

    def classify_difficulty(row):
        if row["Fail Rate (%)"] >= 20 or row["Dropout Rate (%)"] >= 5:
            return "High"
        elif row["Fail Rate (%)"] >= 10 or row["Dropout Rate (%)"] >= 2:
            return "Medium"
        else:
            return "Low"

    summary["Difficulty Level"] = summary.apply(classify_difficulty, axis=1)
    summary["Subject Full Name"] = summary["Subject Code"] + " - " + summary["Subject Name"]

    return summary[["Subject Full Name", "Fail Rate (%)", "Dropout Rate (%)", "Difficulty Level"]]


# ==========================
# Export to PDF
# ==========================
def export_pdf(df, fig, filename="subject_difficulty.pdf"):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("📊 Subject Difficulty Report", styles["Title"]))
    elements.append(Spacer(1, 12))

    # Table
    table_data = [df.columns.tolist()] + df.values.tolist()
    t = Table(table_data)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 20))

    # Chart
    img_bytes = fig.to_image(format="png")
    elements.append(Image(io.BytesIO(img_bytes), width=600, height=300))

    doc.build(elements)
    buffer.seek(0)
    return buffer


# ==========================
# Display Function
# ==========================
def display_subject_difficulty():
    st.title("📊 Subject Difficulty Heatmap")
    st.caption("Visualizes subjects with high failure or dropouts. Filtered by **Professor**.")

    curriculum = st.session_state.curriculum_type
    role = st.session_state.role
    username = st.session_state.username  # 👈 professorId when role=professor

    # ---------- OLD ----------
    if curriculum == "Old Curriculum":
        all_profs = sorted({t for g in data_collections["grades"] for t in g.get("Teachers", []) if t})
        if role == "professor":
            selected_prof = username
        else:
            selected_prof = st.selectbox("Select Professor:", all_profs)

        cache_key = f"subject_difficulty_{curriculum}_{selected_prof}.pkl"
        df = load_cache(cache_key)
        if df is None:
            df = get_subject_difficulty_old(selected_prof)
            cache_data(cache_key, df)

    # ---------- NEW ----------
    else:
        professors = {p["_id"]: p for p in data_collections["newProfessors"]}

        if role == "professor":
            professor_id = username  # ✅ direct from login
            selected_prof = professors.get(professor_id, {}).get("fullName", professors.get(professor_id, {}).get("name", "Unknown"))
        else:
            all_profs = sorted([p.get("fullName", p.get("name", "Unknown")) for p in professors.values()])
            selected_prof = st.selectbox("Select Professor:", all_profs)
            professor_id = next((pid for pid, p in professors.items() if p.get("fullName", p.get("name")) == selected_prof), None)

        cache_key = f"subject_difficulty_{curriculum}_{professor_id}.pkl"
        df = load_cache(cache_key)
        if df is None:
            df = get_subject_difficulty_new(professor_id)
            cache_data(cache_key, df)

    # ---------- DISPLAY ----------
    if not df.empty and "Subject Full Name" in df.columns:
        df_display = df.copy()
        df_display["Fail Rate (%)"] = df_display["Fail Rate (%)"].map(lambda x: f"{x:.1f}%")
        df_display["Dropout Rate (%)"] = df_display["Dropout Rate (%)"].map(lambda x: f"{x:.1f}%")

        st.subheader(f"Results for {selected_prof}")
        st.dataframe(df_display, use_container_width=True)

        # Heatmap
        fig = px.imshow(
            df[["Fail Rate (%)", "Dropout Rate (%)"]],
            labels=dict(x="Metric", y="Subject", color="Rate (%)"),
            x=["Fail Rate (%)", "Dropout Rate (%)"],
            y=df["Subject Full Name"],
            text_auto=True,
            aspect="auto",
            color_continuous_scale="Reds"
        )
        st.plotly_chart(fig, use_container_width=True)

        # PDF Export
        pdf_buffer = export_pdf(df_display, fig)
        st.download_button(
            "📥 Download PDF",
            data=pdf_buffer,
            file_name="subject_difficulty.pdf",
            mime="application/pdf"
        )
    else:
        st.warning(f"No subject difficulty data found for {selected_prof} in {curriculum}.")


# ==========================
# Run Display
# ==========================
if __name__ == "__main__":
    display_subject_difficulty()
