import streamlit as st

from utils.session_state import (
    clear_auth_token,
    get_session_state,
    set_auth_token,
    update_session_state,
)


def login(user_name: str, password: str):
    session_state = get_session_state(login_page=True)
    if user_name == "Benjamin" and password == "password":
        session_state.username = "Benjamin"
        update_session_state(session_state)
        set_auth_token("Benjamin")
        st.toast("Logged in successfully")
        st.rerun()
    else:
        st.toast("Invalid credentials")


def logout():
    session_state = get_session_state(login_page=True)
    session_state.username = ""
    update_session_state(session_state)
    clear_auth_token()
    st.toast("Logged out successfully")
