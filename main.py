import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from app.api.routes import router
from contextlib import asynccontextmanager
from app.db import init_db
from app.logging_config import setup_logging


setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


# Initialize FastAPI app
app = FastAPI(
    title="Address Extraction Web App",
    lifespan=lifespan,
)

# Get path of current file directory
base_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(base_dir, "app", "static")

# Mount static files at /static
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include router from routes.py
app.include_router(router)

# Serve index.html at GET /
@app.get("/", response_class=HTMLResponse)
async def read_index():
    index_path = os.path.join(static_dir, "templates", "index.html")
    return FileResponse(index_path)

if __name__ == "__main__":
    # Run the server on host 0.0.0.0, port 8000
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
