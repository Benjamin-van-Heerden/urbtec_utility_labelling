from pydantic import BaseModel


class SessionState(BaseModel):
    username: str = ""

    @property
    def is_authenticated(self) -> bool:
        return self.username != ""
