import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
Config.validate()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from auth.database import init_db
from routes.chat import router as chat_router
from routes.auth import router as auth_router

app_dir      = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.join(os.path.dirname(app_dir), "frontend")

def create_app() -> FastAPI:
    app = FastAPI(title="NexusBot", version="2.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    init_db()

    app.include_router(chat_router, prefix="/api")
    app.include_router(auth_router, prefix="/api/auth")

    # Serve frontend static assets (css, js, images)
    assets_dir = os.path.join(frontend_dir, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # Serve generated images as static files
    gen_images_dir = os.path.join(app_dir, "static", "images")
    os.makedirs(gen_images_dir, exist_ok=True)
    app.mount("/static", StaticFiles(directory=os.path.join(app_dir, "static")), name="static")

    # Serve individual frontend files
    @app.get("/style.css")
    async def serve_css():
        return FileResponse(os.path.join(frontend_dir, "style.css"), media_type="text/css")

    @app.get("/script.js")
    async def serve_js():
        return FileResponse(os.path.join(frontend_dir, "script.js"), media_type="application/javascript")

    @app.get("/")
    async def index():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("  NexusBot — FastAPI + LangGraph + ReAct + Auth")
    print("  http://127.0.0.1:8000")
    print("=" * 50)
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
    