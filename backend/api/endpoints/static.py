from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

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
    return templates.TemplateResponse("annotator.html", {"request": request})


@router.get("/faq", response_class=HTMLResponse)
async def faq(request: Request) -> HTMLResponse:
    """Сторінка FAQ з інформацією про дрони"""
    return templates.TemplateResponse("faq.html", {"request": request})


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
    """JS файли включаючи новий common.js"""
    return FileResponse(f"frontend/js/{file_name}", media_type="application/javascript")


@router.get("/data/{file_name}")
async def serve_data(file_name: str) -> FileResponse:
    """JSON файли з даними (наприклад drones.json)"""
    return FileResponse(f"frontend/data/{file_name}", media_type="application/json")


@router.get("/favicon.png")
async def serve_favicon_png() -> FileResponse:
    """Favicon PNG"""
    return FileResponse("frontend/static/images/favicon.png", media_type="image/png")


@router.get("/favicon.ico")
async def serve_favicon_ico() -> FileResponse:
    """Favicon ICO"""
    return FileResponse("frontend/static/images/favicon.png", media_type="image/png")