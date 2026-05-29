import logging
import threading
from dataclasses import asdict, dataclass
from typing import Optional

from ..core.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SchedulerRuntimeState:
    enabled: bool
    active: bool
    running: bool
    completed: bool
    thread_name: Optional[str]
    last_error: str


class EmbeddedSchedulerService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._last_error = ""
        self._active = False
        self._completed = False

    def start(self) -> bool:
        if not self.settings.embed_scheduler:
            logger.info("embedded scheduler disabled by BACKEND_EMBED_SCHEDULER.")
            return False
        with self._lock:
            self._active = True
            if self._thread is not None and self._thread.is_alive():
                return False

            from .scheduler_engine import create_scheduler_from_env, load_dotenv

            load_dotenv(str(self.settings.env_file))
            # Keep embedded scheduler and API reader on the same state/event files.
            import os

            os.environ["TASK_STATE_FILE"] = str(self.settings.state_file)
            os.environ["TASK_EVENT_FILE"] = str(self.settings.event_file)
            scheduler = create_scheduler_from_env()
            self._stop_event.clear()
            self._last_error = ""
            self._completed = False

            def _run() -> None:
                try:
                    scheduler.run_forever(stop_event=self._stop_event)
                    self._completed = scheduler.is_complete()
                except Exception as exc:
                    self._last_error = str(exc)
                    logger.exception("embedded scheduler crashed")

            self._thread = threading.Thread(target=_run, name="embedded-scheduler", daemon=True)
            self._thread.start()
            logger.info("embedded scheduler started.")
            return True

    def stop(self, timeout_seconds: float = 10.0) -> bool:
        with self._lock:
            if self._thread is None:
                return False
            if not self._thread.is_alive():
                self._thread = None
                return False

            self._stop_event.set()
            self._thread.join(timeout=timeout_seconds)
            alive = self._thread.is_alive()
            if not alive:
                self._thread = None
                self._active = False
                logger.info("embedded scheduler stopped.")
                return True
            logger.warning("embedded scheduler did not stop within %.1fs", timeout_seconds)
            return False

    def restart(self, timeout_seconds: float = 10.0) -> bool:
        self.stop(timeout_seconds=timeout_seconds)
        return self.start()

    def status(self) -> SchedulerRuntimeState:
        thread = self._thread
        running = bool(thread and thread.is_alive())
        return SchedulerRuntimeState(
            enabled=self.settings.embed_scheduler,
            active=self._active,
            running=running,
            completed=self._completed,
            thread_name=thread.name if thread else None,
            last_error=self._last_error,
        )

    def status_dict(self) -> dict:
        return asdict(self.status())
