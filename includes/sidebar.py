import streamlit as st
from pages.student_academic import student_academic_view
from pages.pass_failed import pass_fail_view
from pages.enrollment import enrollment_view
from pages.inc import incomplete_view
from pages.drop import retention_view
from pages.highest import highest_view


    # ==========================
from pages.curriculum_view import curriculum_view
from pages.class_grade import class_distribution_view
from pages.student_progress_view import display_student_progress
from pages.subject_difficulty import display_subject_difficulty
from pages.intervention_candidates import display_intervention_candidates
from pages.submission_status import display_submission_status
from pages.query_builder import display_query_builder
from pages.grade_analytics import grade_analytics
    # ==========================
from pages.transcript_viewer import display_transcript_viewer
from pages.performance_trend import  display_trend_viewer
from pages.student_subject_difficulty import student_subject_difficulty
from pages.comparison_with_class_average import comparison_with_class_average
from pages.passed_vs_failed_summary import passed_vs_failed_summary
from pages.student_curriculum_viewer import student_curriculum_viewer



def sidebar_menu():
    """Render sidebar with role-based navigation and main content"""

    # Make sure user is logged in
    if "role" not in st.session_state:
        st.error("⚠️ Please log in first.")
        st.stop()

    role = st.session_state.role
    username = st.session_state.username

    # ==========================
    # Curriculum default per role
    # ==========================
    if "curriculum_type" not in st.session_state:
        if role in ["professor", "student"]:
            st.session_state.curriculum_type = "New Curriculum"
        else:
            st.session_state.curriculum_type = "Old Curriculum"

    # Sidebar Navigation
    st.sidebar.title(f"📌 Welcome, {username} ({role.title()})")

    # Role-based menus
    if role == "admin":
        menu = st.sidebar.radio("Go to", ["Registrar", "Faculty", "Student"])
    elif role == "professor":
        menu = st.sidebar.radio("Go to", ["Faculty"])
    elif role == "student":
        menu = st.sidebar.radio("Go to", ["Student"])
    else:
        st.error("❌ Unknown role")
        return

    # ==========================
    # Registrar Dashboard
    # ==========================
    if menu == "Registrar":
        st.title("🏫 Registrar Dashboard")

        registrar_option = st.sidebar.radio(
            "Registrar Options",
            [
                "Overview",
                "Student Academic Standing Report",
                "Subject Pass/Fail Distribution",
                "Enrollment Trend Analysis",
                "Incomplete Grades Report",
                "Retention and Dropout Rates",
                "Top Performers per Program",
                "Curriculum Progress and Advising"
            ]
        )

        if registrar_option == "Overview":
            st.write("Welcome to the Registrar section. Manage courses, enrollment, and student records.")
        elif registrar_option == "Student Academic Standing Report":
            st.subheader("📊 Student Academic Standing Report")
            student_academic_view()
            st.write("Generate and view academic standing reports for students.")
        elif registrar_option == "Subject Pass/Fail Distribution":
            st.subheader("📈 Subject Pass/Fail Distribution")
            pass_fail_view()
        elif registrar_option == "Enrollment Trend Analysis":
            st.subheader("📊 Enrollment Trend Analysis")
            enrollment_view()
        elif registrar_option == "Incomplete Grades Report":
            st.subheader("📋 Incomplete Grades Report")
            incomplete_view()
        elif registrar_option == "Retention and Dropout Rates":
            st.subheader("📉 Retention and Dropout Rates")
            retention_view()
        elif registrar_option == "Top Performers per Program":
            st.subheader("🏅 Top Performers per Program")
            highest_view()
        elif registrar_option == "Curriculum Progress and Advising":
            st.subheader("📘 Curriculum Progress and Advising")
            curriculum_view()

    # ==========================
    # Faculty Dashboard
    # ==========================
    elif menu == "Faculty":
        st.title("👨‍🏫 Faculty Dashboard")

        faculty_option = st.sidebar.radio(
            "Faculty Options",
            [
                "Overview",
                "Class Grade Distribution",
                "Student Progress Tracker",
                "Subject Difficulty Heatmap",
                "Intervention Candidates List",
                "Grade Submission Status",
                "Custom Query Builder",
                "Grades Analytics (Per Teacher)"
            ]
        )

        if faculty_option == "Overview":
            st.write("Welcome to the Faculty section. View faculty profiles, schedules, and assignments.")
        elif faculty_option == "Class Grade Distribution":
            st.subheader("📊 Class Grade Distribution")
            class_distribution_view()
        elif faculty_option == "Student Progress Tracker":
            st.subheader("📈 Student Progress Tracker")
            display_student_progress()
        elif faculty_option == "Subject Difficulty Heatmap":
            st.subheader("🔥 Subject Difficulty Heatmap")
            display_subject_difficulty()
        elif faculty_option == "Intervention Candidates List":
            st.subheader("🚨 Intervention Candidates List")
            display_intervention_candidates()
        elif faculty_option == "Grade Submission Status":
            st.subheader("✅ Grade Submission Status")
            display_submission_status()
        elif faculty_option == "Custom Query Builder":
            st.subheader("🛠 Custom Query Builder")
            display_query_builder()
        elif faculty_option == "Grades Analytics (Per Teacher)":
            st.subheader("📑 Grades Analytics (Per Teacher)")
            grade_analytics()

    # ==========================
    # Student Dashboard
    # ==========================
    elif menu == "Student":
        st.title("🎓 Student Dashboard")

        student_option = st.sidebar.radio(
            "Student Options",
            [
                "Overview",
                "Academic Transcript Viewer",
                "Performance Trend Over Time",
                "Subject Difficulty Ratings",
                "Comparison with Class Average",
                "Passed vs Failed Summary",
                "Curriculum and Subject Viewer"
            ]
        )

        if student_option == "Overview":
            st.write("Welcome to the Student section. View student records, grades, and enrollment info.")
        elif student_option == "Academic Transcript Viewer":
            st.subheader("📜 Academic Transcript Viewer")
            display_transcript_viewer()
        elif student_option == "Performance Trend Over Time":
            st.subheader("📈 Performance Trend Over Time")
            display_trend_viewer()
        elif student_option == "Subject Difficulty Ratings":
            st.subheader("⭐ Subject Difficulty Ratings")
            student_subject_difficulty()
        elif student_option == "Comparison with Class Average":
            st.subheader("📊 Comparison with Class Average")
            comparison_with_class_average()
        elif student_option == "Passed vs Failed Summary":
            st.subheader("✅❌ Passed vs Failed Summary")
            passed_vs_failed_summary()
        elif student_option == "Curriculum and Subject Viewer":
            st.subheader("✅ Curriculum and Subject Viewer")
            student_curriculum_viewer()

    # ==========================
    # General Curriculum Toggle (Admins only)
    # ==========================
    if role == "admin":
        st.sidebar.markdown("---")
        st.sidebar.subheader("📚 Curriculum View")

        toggle = st.sidebar.toggle(
            f"Switch to {'Old' if st.session_state.curriculum_type == 'New Curriculum' else 'New'} Curriculum",
            value=(st.session_state.curriculum_type == "New Curriculum"),
            key="curriculum_toggle_sidebar"
        )

        new_type = "New Curriculum" if toggle else "Old Curriculum"

        if new_type != st.session_state.curriculum_type:
            st.session_state.curriculum_type = new_type
            st.session_state.page = 1
            st.rerun()

        st.sidebar.success(f"Currently Selected: **{st.session_state.curriculum_type}**")
    else:
        # ✅ Force Faculty/Students to New Curriculum (no toggle shown)
        st.session_state.curriculum_type = "New Curriculum"

    # ==========================
    # Logout button
    # ==========================
    if st.sidebar.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.role = ""
        st.switch_page("app.py")
