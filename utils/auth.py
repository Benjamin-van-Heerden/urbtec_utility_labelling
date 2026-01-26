import streamlit as st

from utils.session_state import (
    clear_auth_token,
    get_session_state,
    set_auth_token,
    update_session_state,
)

USERS = {
    "Benjamin": "Password456",
    "Zelda": "Password123",
}


def login(user_name: str, password: str):
    session_state = get_session_state(login_page=True)
    if user_name in USERS and USERS[user_name] == password:
        session_state.username = user_name
        update_session_state(session_state)
        set_auth_token(user_name)
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
