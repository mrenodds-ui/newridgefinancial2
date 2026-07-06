from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import default_dev_auth_users_json, load_settings, runtime_warnings
from .routes import router

logger = logging.getLogger(__name__)

os.environ.setdefault("APP_AUTH_USERS_JSON", default_dev_auth_users_json())

settings = load_settings()

for warning in runtime_warnings(settings):
    logger.warning(warning)

app = FastAPI(
    title="New Ridge Family Financial Browser API",
    version="0.1.0",
    description="HAL browser chat API for the Vite/React dashboard.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
