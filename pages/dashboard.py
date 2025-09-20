import streamlit as st
from ..includes.sidebar import sidebar_menu 

def dashboard():
    """Main Dashboard that includes the sidebar"""
    st.set_page_config(
        page_title="Registrar System Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # 🔥 Hide Streamlit default multipage navigation (the "app / dashboard" on top)
    st.markdown(
        """
        <style>
        [data-testid="stSidebarNav"] {display: none;} 
        </style>
        """,
        unsafe_allow_html=True
    )

    # Protect dashboard (redirect if not logged in)
    if "logged_in" not in st.session_state or not st.session_state.logged_in:
        st.warning("⚠️ Please log in first.")
        st.switch_page("app.py")

    # Call the sidebar menu (which also renders the main content)
    sidebar_menu()


if __name__ == "__main__":
    dashboard()
