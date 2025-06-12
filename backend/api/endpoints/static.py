from fastapi import APIRouter, Request, Depends
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from backend.api.dependencies import require_any_role

router = APIRouter(tags=["static"])

templates = Jinja2Templates(directory="frontend/html")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    """Сторінка логіна (доступна всім)"""
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/",
           response_class=HTMLResponse,
           dependencies=[Depends(require_any_role())])
async def index(request: Request) -> HTMLResponse:
    """Головна сторінка завантаження відео"""
    return templates.TemplateResponse("upload.html", {"request": request})


@router.get("/annotator",
           response_class=HTMLResponse,
           dependencies=[Depends(require_any_role())])
async def annotator(request: Request) -> HTMLResponse:
    """Сторінка анотування відео"""
    return templates.TemplateResponse("annotator.html", {"request": request})


@router.get("/faq",
           response_class=HTMLResponse,
           dependencies=[Depends(require_any_role())])
async def faq(request: Request) -> HTMLResponse:
    """Сторінка FAQ з інформацією про дрони"""
    return templates.TemplateResponse("faq.html", {"request": request})


# CSS та JS файли
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