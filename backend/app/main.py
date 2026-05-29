import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .router import router
from .services.embedded_scheduler import EmbeddedSchedulerService

settings = get_settings()
logger = logging.getLogger(__name__)

app = FastAPI(title="Xingka Monitor API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)

app.state.scheduler_service = EmbeddedSchedulerService(settings=settings)


@app.on_event("startup")
def _on_startup() -> None:
    logging.basicConfig(
        level="INFO",
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    if settings.embed_scheduler:
        logger.info("embedded scheduler is ready. Use the dashboard start button to run it.")


@app.on_event("shutdown")
def _on_shutdown() -> None:
    service: EmbeddedSchedulerService = app.state.scheduler_service
    service.stop(timeout_seconds=10.0)
