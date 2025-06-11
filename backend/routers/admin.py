from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import cast, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import String

from backend.autorization.dependencies import get_current_user
from backend.autorization.utils import require_admin_or_owner
from backend.database.connector import get_db
from backend.database.models import ProductPhoto
from backend.gcp_tools.logging import get_logger
from backend.schemas import (
    AdminPhotoRequest,
    DeletePhotoResponse,
    GetPhotoResponse,
    PhotoData,
    PhotoUploadResponse,
)
from backend.search import prepare_description

logger = get_logger()
router = APIRouter()


@router.get("/photo/{product_photo_id}/", status_code=200, response_model=GetPhotoResponse)
async def get_photo(
    product_photo_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ Retrieve a photo by product_photo_id """
    await require_admin_or_owner(current_user)
    try:
        logger.info(f"📸 Fetching photo {product_photo_id} requested by {current_user['email']}")

        query = await db.execute(
            select(ProductPhoto).where(cast(ProductPhoto.product_photo_id, String) == product_photo_id)
        )
        photo_record = query.scalars().first()

        if not photo_record:
            logger.warning(f"❌ Photo {product_photo_id} not found")
            raise HTTPException(status_code=404, detail="Photo not found")

        logger.info(f"✅ Photo {product_photo_id} successfully retrieved")
        return GetPhotoResponse(
            product_photo_id=photo_record.product_photo_id,
            photo_description=photo_record.photo_description
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"🚨 Error fetching photo {product_photo_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching photo")


@router.post("/photo/", status_code=201, response_model=PhotoUploadResponse)
async def create_or_update_photo(
    request: AdminPhotoRequest = Body(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ Upload or update a product photo """
    await require_admin_or_owner(current_user)

    if not request.image_base64:
        logger.warning(f"⚠️ Missing image data in request for product {request.product_photo_id}")
        raise HTTPException(status_code=400, detail="No image data provided")

    logger.info(f"🖼️ Processing photo {request.product_photo_id} by {current_user['email']}")

    # Analyze the image (retrieve only the description)
    description_or_error = await prepare_description(request.image_base64)

    # If an error is returned, propagate it in the response
    if isinstance(description_or_error, dict) and "error" in description_or_error:
        logger.error(f"❌ Error generating description for {request.product_photo_id}: {description_or_error['error']}")
        raise HTTPException(status_code=500, detail=description_or_error["error"])

    photo_description = description_or_error

    # Check if the photo already exists in the database
    query = await db.execute(select(ProductPhoto).where(
        cast(ProductPhoto.product_photo_id, String) == request.product_photo_id)
    )
    photo_record = query.scalars().first()

    if photo_record:
        # Update existing record
        logger.info(f"♻️ Updating photo {request.product_photo_id}")
        photo_record.photo_description = photo_description
    else:
        # Create a new record
        logger.info(f"✅ Creating new photo {request.product_photo_id}")
        photo_record = ProductPhoto(
            product_photo_id=request.product_photo_id,
            photo_description=photo_description
        )
        db.add(photo_record)

    await db.commit()

    return PhotoUploadResponse(
        message="Photo updated successfully" if photo_record else "Photo uploaded successfully",
        data=PhotoData(
            product_photo_id=request.product_photo_id,
            photo_description=photo_description
        )
    )


@router.delete("/photo/{product_photo_id}/", status_code=200, response_model=DeletePhotoResponse)
async def delete_photo(
    product_photo_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ Delete a photo by product_photo_id """
    await require_admin_or_owner(current_user)
    try:
        logger.info(f"🗑️ Deleting photo {product_photo_id} requested by {current_user['email']}")

        result = await db.execute(
            delete(ProductPhoto).where(cast(ProductPhoto.product_photo_id, String) == product_photo_id)
        )
        await db.commit()

        if result.rowcount == 0:
            logger.warning(f"⚠️ Attempt to delete non-existent photo {product_photo_id}")
            raise HTTPException(status_code=404, detail="Photo not found")

        logger.info(f"✅ Photo {product_photo_id} successfully deleted")
        return DeletePhotoResponse(message=f"Photo {product_photo_id} deleted successfully")

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"🚨 Error deleting photo {product_photo_id}: {e}")
        raise HTTPException(status_code=500, detail="Error deleting photo")
