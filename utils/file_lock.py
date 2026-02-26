import fcntl
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

PROJECT_ROOT = Path(__file__).parent.parent
UNCLASSIFIED_QUEUE_PATH = PROJECT_ROOT / "unclassified_queue.json"
UNCLASSIFIED_LOCK_PATH = PROJECT_ROOT / "unclassified_queue.json.lock"


@contextmanager
def queue_lock() -> Generator[None, None, None]:
    UNCLASSIFIED_LOCK_PATH.touch(exist_ok=True)
    with open(UNCLASSIFIED_LOCK_PATH) as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def read_queue() -> list[dict]:
    if not UNCLASSIFIED_QUEUE_PATH.exists():
        return []
    with open(UNCLASSIFIED_QUEUE_PATH) as f:
        return json.load(f)


def write_queue(queue: list[dict]) -> None:
    with open(UNCLASSIFIED_QUEUE_PATH, "w") as f:
        json.dump(queue, f, indent=2)
