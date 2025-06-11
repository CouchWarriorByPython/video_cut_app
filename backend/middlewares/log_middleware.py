import time
from fastapi import Request
from backend.gcp_tools.logging import get_logger

logger = get_logger()


async def log_middleware(request: Request, call_next):
    """ Middleware for logging requests """
    start_time = time.time()
    client_ip = request.client.host
    logger.info(f"Request from {client_ip}: {request.method} {request.url}")

    response = await call_next(request)

    process_time = time.time() - start_time
    logger.info(f"Request from {client_ip} completed in {process_time:.2f} sec with status {response.status_code}")

    return response
