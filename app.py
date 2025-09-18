import streamlit as st
from data_collection import data_collections

# Page configuration
st.set_page_config(
    page_title="Login",
    page_icon="🔑",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 🔒 Hide Streamlit’s default sidebar + collapse button (login only)
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {display: none;} 
    [data-testid="stSidebarNav"] {display: none;}
    [data-testid="stSidebarCollapseButton"] {display: none;}
    </style>
    """,
    unsafe_allow_html=True
)

# Session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "role" not in st.session_state:
    st.session_state.role = ""


def authenticate_user(username, password):
    """Check user credentials from MongoDB collections"""
    for user in data_collections.get("newAdmin", []):
        if user["username"] == username and user["password"] == password:
            return "admin"
    for user in data_collections.get("newProfessors", []):
        if user["username"] == username and user["password"] == password:
            return "professor"
    for user in data_collections.get("newStudents", []):
        if user["username"] == username and user["password"] == password:
            return "student"
    return None


# Login page
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>🔐 Registrar System</h1>", unsafe_allow_html=True)
    st.write("Please log in to continue")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        role = authenticate_user(username, password)
        if role:
            st.success(f"✅ Welcome, {username} ({role.title()})!")
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.role = role

            # Redirect to dashboard (inside pages/ folder)
            st.switch_page("pages/dashboard.py")
        else:
            st.error("❌ Invalid username or password")
