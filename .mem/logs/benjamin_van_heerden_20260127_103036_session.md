---
created_at: '2026-01-27T10:30:36.587939'
username: benjamin_van_heerden
---
# Work Log - Fix Multi-User Authentication

## Overarching Goals

Fix the authentication system to allow multiple users to be logged in simultaneously. The previous implementation had a module-level `CookieController` singleton that caused session isolation issues between users.

## What Was Accomplished

### Diagnosed the Root Cause

The `CookieController` from `streamlit_cookies_controller` was instantiated at module level:
```python
cookie_controller = CookieController()
```

This created a shared instance across all users on the server process. When User A logged in and User B logged in afterward, the cookie state would get clobbered.

### Implemented Per-Session Cookie Controller

Replaced the module-level singleton with a function that creates a new `CookieController` instance per call, using a unique session state key:

```python
COOKIE_CONTROLLER_KEY = "auth_cookies"

def get_cookie_controller() -> CookieController:
    return CookieController(key=COOKIE_CONTROLLER_KEY)
```

### Fixed Cookie Initialization Timing

The `CookieController` returns `None` for cookies on the first render before the JS component has loaded. Added a guard to force a rerun when cookies haven't loaded yet:

```python
all_cookies = controller.getAll()
if all_cookies is None:
    st.rerun()
```

This ensures cookie persistence works across browser refreshes and restarts.

## Key Files Affected

- `utils/session_state.py` - Replaced module-level `cookie_controller` with `get_cookie_controller()` function; added cookie initialization check with `st.rerun()` fallback

## What Comes Next

- The todo "multiple users logged in at same time" has been resolved
- Deploy and verify multi-user authentication works in production
