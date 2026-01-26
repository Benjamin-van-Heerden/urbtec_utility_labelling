import jwt
import streamlit as st
from streamlit_cookies_controller import CookieController

from env_settings import ENV_SETTINGS
from utils.models.session_state import SessionState

cookie_controller = CookieController()

JWT_ALGORITHM = "HS256"


def initialize_session_state():
    if "state" not in st.session_state:
        reset_session_state()
    elif not isinstance(st.session_state["state"], SessionState):
        old_state = st.session_state["state"]
        state_dict = old_state.__dict__ if hasattr(old_state, "__dict__") else {}
        st.session_state["state"] = SessionState(**state_dict)

    if not st.session_state["state"].is_authenticated:
        # Check session state first (hot reload)
        auth_token = st.session_state.get("auth_token")
        cookie_token = cookie_controller.get("auth_cookie")

        # Debug: uncomment to see what's happening
        # st.write(f"DEBUG: auth_token={auth_token is not None}, cookie_token={cookie_token is not None}")

        if auth_token and not cookie_token:
            cookie_controller.set("auth_cookie", auth_token, max_age=60 * 60 * 24 * 7)

        if not auth_token:
            # Check cookie (browser restart)
            auth_token = cookie_token

        if auth_token:
            try:
                payload = jwt.decode(
                    auth_token, ENV_SETTINGS.jwt_salt, algorithms=[JWT_ALGORITHM]
                )
                username = payload.get("username")
                if username:
                    st.session_state["state"].username = username
                    st.session_state["auth_token"] = auth_token
            except (
                jwt.InvalidTokenError,
                jwt.DecodeError,
                jwt.ExpiredSignatureError,
            ):
                # Clear invalid token
                cookie_controller.remove("auth_cookie")
                st.session_state.pop("auth_token", None)


def get_session_state(login_page: bool = False) -> SessionState:
    initialize_session_state()
    state = st.session_state["state"]
    assert isinstance(state, SessionState)

    if not login_page:
        if not state.is_authenticated:
            st.switch_page("__🏠_Home.py")
    return state


def update_session_state(new_state: SessionState):
    st.session_state["state"] = new_state


def reset_session_state():
    st.session_state["state"] = SessionState()


def set_auth_token(username: str):
    """Create and store JWT token for authenticated user"""
    payload = {"username": username}
    token = jwt.encode(payload, ENV_SETTINGS.jwt_salt, algorithm=JWT_ALGORITHM)
    # Store in session state first (immediate)
    st.session_state["auth_token"] = token
    # Store in cookie for persistence across browser restarts
    # Note: This is async, so we also store in session state above
    cookie_controller.set("auth_cookie", token, max_age=60 * 60 * 24 * 7)  # 7 days


def clear_auth_token():
    """Clear authentication token from cookie and session"""
    cookie_controller.remove("auth_cookie")
    st.session_state.pop("auth_token", None)
