import streamlit as st

from utils.auth import login, logout
from utils.session_state import get_session_state

st.set_page_config(
    page_title="Home",
    page_icon="🏠",
)

state = get_session_state(login_page=True)

st.title("🏠 Home")


st.divider()

if state.is_authenticated:
    st.success(f"Welcome, {state.username}!")
    if st.button("🏷️ Go to Meter Labelling", type="secondary", use_container_width=True):
        st.switch_page("pages/1_🏷️_Meter_Labelling.py")
    st.button("Logout", on_click=logout)
else:
    st.header("👤 Login to access the rest of the app")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input(
            "Password",
            type="password",
        )
        submit_button = st.form_submit_button("Login")
        if submit_button:
            login(username, password)
