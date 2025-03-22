from fastapi import FastAPI
from api.processing.routes import router as processing_router
from api.data.routes import router as data_router
from api.config.routes import router as config_router
import logging

app = FastAPI()

app.include_router(processing_router)
app.include_router(data_router)
app.include_router(config_router)

logging.basicConfig(level=logging.INFO)
