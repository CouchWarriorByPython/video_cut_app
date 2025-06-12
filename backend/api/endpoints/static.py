from fastapi import APIRouter, Request, Depends
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from backend.api.dependencies import require_any_role

router = APIRouter(tags=["static"])

templates = Jinja2Templates(directory="front/html")


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


@router.get("/faq", response_class=HTMLResponse)
async def faq(request: Request) -> HTMLResponse:
    """Сторінка FAQ з інформацією про дрони (доступна всім)"""
    return templates.TemplateResponse("faq.html", {"request": request})


# CSS та JS файли (доступні всім)
@router.get("/css/base.css")
async def serve_base_css() -> FileResponse:
    """Базовий CSS файл"""
    return FileResponse("front/css/base.css", media_type="text/css")


@router.get("/css/upload.css")
async def serve_upload_css() -> FileResponse:
    """CSS для сторінки завантаження"""
    return FileResponse("front/css/upload.css", media_type="text/css")


@router.get("/css/annotator.css")
async def serve_annotator_css() -> FileResponse:
    """CSS для сторінки анотування"""
    return FileResponse("front/css/annotator.css", media_type="text/css")


@router.get("/css/faq.css")
async def serve_faq_css() -> FileResponse:
    """CSS для сторінки FAQ"""
    return FileResponse("front/css/faq.css", media_type="text/css")


@router.get("/js/upload.js")
async def serve_upload_js() -> FileResponse:
    """JS для сторінки завантаження"""
    return FileResponse("front/js/upload.js", media_type="application/javascript")


@router.get("/js/annotator.js")
async def serve_annotator_js() -> FileResponse:
    """JS для сторінки анотування"""
    return FileResponse("front/js/annotator.js", media_type="application/javascript")


@router.get("/js/faq.js")
async def serve_faq_js() -> FileResponse:
    """JS для сторінки FAQ"""
    return FileResponse("front/js/faq.js", media_type="application/javascript")


@router.get("/favicon.png")
async def serve_favicon_png() -> FileResponse:
    """Favicon PNG"""
    return FileResponse("front/static/images/favicon.png", media_type="image/png")


@router.get("/favicon.ico")
async def serve_favicon_ico() -> FileResponse:
    """Favicon ICO (аліас для PNG)"""
    return FileResponse("front/static/images/favicon.png", media_type="image/png")