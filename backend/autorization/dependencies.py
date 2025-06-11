from fastapi import Request, HTTPException
from typing import Any
from backend.gcp_tools.logging import get_logger

logger = get_logger()


async def get_current_user(request: Request) -> dict[str, Any]:
    """ Retrieve the current user from request.state """

    if not hasattr(request.state, "user"):
        logger.warning(f"🚫 Attempt to access without authentication: {request.url}")
        raise HTTPException(status_code=401, detail="Not authenticated")

    logger.info(f"✅ Authorized request from {request.state.user['email']}")
    return request.state.user
