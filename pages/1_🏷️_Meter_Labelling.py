import streamlit as st

from utils.session_state import get_session_state

st.set_page_config(
    page_title="Meter Labelling",
    page_icon="🏷️",
)

state = get_session_state()

st.title("🏷️ Label Meter Image")
