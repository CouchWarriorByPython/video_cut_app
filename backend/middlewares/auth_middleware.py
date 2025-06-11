from fastapi import Request
from fastapi.responses import JSONResponse
from backend.config import config
from backend.gcp_tools.logging import get_logger
from backend.autorization.utils import decode_token

logger = get_logger()


async def auth_middleware(request: Request, call_next):
    """ Middleware for authorization via JWT """
    public_paths = [
        f"{config.API_VERSION}/auth/login/",
        f"{config.API_VERSION}/auth/token/refresh/",
        "/docs",
        "/openapi.json"
    ]

    if request.scope["path"] in public_paths:
        return await call_next(request)

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        logger.warning(f"❌ Missing Authorization header for {request.method} {request.url}")
        return JSONResponse(status_code=401, content={"error": "Not authenticated"})

    try:
        scheme, token = auth_header.split(" ", 1)
        if scheme.lower() != "bearer":
            logger.warning(f"⚠️ Invalid authentication scheme: {auth_header} for {request.url}")
            return JSONResponse(status_code=401, content={"error": "Invalid authentication scheme"})

        payload = await decode_token(token)

        if not payload:
            return JSONResponse(status_code=401, content={"error": "Token has expired or is invalid"})

        email, role = payload.get("sub"), payload.get("role")
        if not email or not role:
            logger.error(f"❌ Invalid token payload for {request.url}")
            return JSONResponse(status_code=401, content={"error": "Invalid token payload"})

        request.state.user = {"email": email, "role": role}
        logger.info(f"✅ Authorization successful: {email} ({role}) for {request.url}")

    except Exception as e:
        logger.exception(f"⚠️ Unexpected error in auth_middleware: {str(e)}")
        return JSONResponse(status_code=500, content={"error": "Internal server error"})

    return await call_next(request)
