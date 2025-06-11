from fastapi import APIRouter, HTTPException, Depends
from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select, cast

from backend.gcp_tools.logging import get_logger
from backend.autorization import utils
from backend.database.connector import get_db
from backend.database.models import User as DBUser
from backend.schemas import CreateUserRequest
from backend.autorization.utils import require_owner, validate_email
from sqlalchemy.types import String

logger = get_logger()
router = APIRouter()


@router.get("/users/", tags=["Owner"])
async def get_all_users(
    _current_user: dict = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    """ Retrieve a list of all users (accessible only to Owner) """
    try:
        logger.info("📋 Retrieving all users requested by the owner")

        result = await db.execute(select(DBUser))
        users = [{"email": user.email, "role": user.role} for user in result.scalars().all()]

        logger.info(f"✅ Found {len(users)} users")
        return {"users": users}
    except Exception as e:
        logger.error(f"🚨 Error retrieving user list: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving users")


@router.post("/users/", tags=["Owner"])
async def create_user(
    request: CreateUserRequest,
    _current_user: dict = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    """ Add a new user (accessible only to Owner) """
    try:
        validated_email = await validate_email(request.email)

        roles = ["admin", "user"]
        if request.role not in roles:
            logger.warning(f"⚠️ Invalid role '{request.role}' for user creation {validated_email}")
            raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of {roles}")

        hashed_password = await utils.get_password_hash(request.password)

        new_user = DBUser(
            email=validated_email,
            hashed_password=hashed_password,
            role=request.role,
        )

        db.add(new_user)
        await db.commit()

        logger.info(f"✅ User {validated_email} created with role {request.role}")
        return {"message": f"User {validated_email} with role {request.role} added successfully"}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"🚨 Error creating user {request.email}: {e}")
        raise HTTPException(status_code=500, detail="Error creating user")


@router.delete("/users/{email}/", tags=["Owner"])
async def delete_user(
    email: EmailStr,
    _current_user: dict = Depends(require_owner),
    db: AsyncSession = Depends(get_db)
):
    """ Delete a user (accessible only to Owner) """
    try:
        logger.info(f"🗑️ Deleting user {email} requested by the owner")

        result = await db.execute(delete(DBUser).where(cast(DBUser.email, String) == str(email)))
        await db.commit()

        if result.rowcount == 0:
            logger.warning(f"⚠️ Attempt to delete a non-existent user {email}")
            raise HTTPException(status_code=404, detail="User not found")

        logger.info(f"✅ User {email} successfully deleted")
        return {"message": f"User {email} deleted successfully"}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"🚨 Error deleting user {email}: {e}")
        raise HTTPException(status_code=500, detail="Error deleting user")