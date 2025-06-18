from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from backend.data.static_data import DRONE_TYPES, UAV_TYPES, VIDEO_CONTENT_TYPES

router = APIRouter(tags=["static"])

templates = Jinja2Templates(directory="frontend/html")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    """Сторінка логіна (доступна всім)"""
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Головна сторінка завантаження відео"""
    return templates.TemplateResponse("upload.html", {"request": request})


@router.get("/annotator", response_class=HTMLResponse)
async def annotator(request: Request) -> HTMLResponse:
    """Сторінка анотування відео"""
    context = {
        "request": request,
        "uav_types": UAV_TYPES,
        "video_content_types": VIDEO_CONTENT_TYPES
    }
    return templates.TemplateResponse("annotator.html", context)


@router.get("/faq", response_class=HTMLResponse)
async def faq(request: Request) -> HTMLResponse:
    """Сторінка FAQ з інформацією про дрони"""
    context = {
        "request": request,
        "drone_types": DRONE_TYPES
    }
    return templates.TemplateResponse("faq.html", context)


@router.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request) -> HTMLResponse:
    """Адміністративна панель"""
    return templates.TemplateResponse("admin.html", {"request": request})


@router.get("/css/{file_name}")
async def serve_css(file_name: str) -> FileResponse:
    """CSS файли"""
    return FileResponse(f"frontend/css/{file_name}", media_type="text/css")


@router.get("/js/{file_name}")
async def serve_js(file_name: str) -> FileResponse:
    """JS файли"""
    return FileResponse(f"frontend/js/{file_name}", media_type="application/javascript")


@router.get("/favicon.png")
async def serve_favicon_png() -> FileResponse:
    """Favicon PNG"""
    return FileResponse("frontend/static/images/favicon.png", media_type="image/png")


@router.get("/favicon.ico")
async def serve_favicon_ico() -> FileResponse:
    """Favicon ICO"""
    return FileResponse("frontend/static/images/favicon.png", media_type="image/png")