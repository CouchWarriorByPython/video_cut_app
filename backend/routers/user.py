from fastapi import APIRouter, HTTPException
from backend.schemas import ImageRequest, SearchResponse
from backend.gcp_tools.logging import get_logger
from backend.search import process_image_search

logger = get_logger()
router = APIRouter()


@router.post("/search/", status_code=200, response_model=SearchResponse)
async def search_by_image(request: ImageRequest):
    """ Upload a user photo for search """
    try:
        image = request.image_base64
        if not image:
            logger.warning("⚠️ Missing image data in request")
            raise HTTPException(status_code=400, detail="No image data provided")

        logger.info("🔍 Initiating image processing for search")

        result = await process_image_search(image=image)

        if "error" in result:
            logger.error(f"❌ Error processing image: {result['error']}")
            raise HTTPException(status_code=500, detail=result["error"])

        similar_images = result.get("similar_images", [])
        logger.info(f"✅ Search completed, found {len(similar_images)} results")
        return SearchResponse(results=similar_images)

    except HTTPException as he:
        logger.warning(f"⚠️ HTTPException: {he.detail}")
        raise he

    except Exception as e:
        logger.error(f"🚨 Unexpected error in search: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")
