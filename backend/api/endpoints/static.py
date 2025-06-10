from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["static"])

templates = Jinja2Templates(directory="front")


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


@router.get("/styles.css")
async def serve_css() -> FileResponse:
    """Статичний CSS файл"""
    return FileResponse("front/styles.css", media_type="text/css")


@router.get("/upload.js")
async def serve_upload_js() -> FileResponse:
    """Статичний JS файл для завантаження"""
    return FileResponse("front/upload.js", media_type="application/javascript")


@router.get("/annotator.js")
async def serve_annotator_js() -> FileResponse:
    """Статичний JS файл для анотування"""
    return FileResponse("front/annotator.js", media_type="application/javascript")


@router.get("/faq.js")
async def serve_faq_js() -> FileResponse:
    """Статичний JS файл для FAQ"""
    return FileResponse("front/faq.js", media_type="application/javascript")


@router.get("/favicon.png")
async def serve_favicon_png() -> FileResponse:
    """Favicon PNG"""
    return FileResponse("front/static/images/favicon.png", media_type="image/png")


@router.get("/favicon.ico")
async def serve_favicon_ico() -> FileResponse:
    """Favicon ICO (аліас для PNG)"""
    return FileResponse("front/static/images/favicon.png", media_type="image/png")