from botocore.exceptions import HTTPClientError, NoCredentialsError, BotoCoreError
from fastapi import APIRouter, HTTPException, UploadFile, File

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_s3_storage_client, get_jwt_auth_manager
from database import get_db, UserModel, UserProfileModel
from exceptions import TokenExpiredError, InvalidTokenError
from schemas.profiles import ProfileRequestSchema, ProfileResponseSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface
from validation import validate_image

from fastapi import Depends

router = APIRouter()


@router.post("/users/me/avatar/", response_model=ProfileResponseSchema)
async def upload_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_storage_client: S3StorageInterface = Depends(get_s3_storage_client),
):
    try:
        decode_token = jwt_manager.decode_access_token(token=token)
    except TokenExpiredError:
        raise HTTPException(status_code=400, detail="Token has expired.")
    except InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid token")

    current_user = int(decode_token["user_id"])
    validate_image(file)

    filename = f"user_{current_user}.{file.filename.split('.')[-1]}"
    contents = await file.read()

    stmt = select(UserProfileModel).where(UserProfileModel.user_id == int(current_user))
    result = await db.execute(stmt)
    user_profile_db = result.scalar_one_or_none()

    try:
        await s3_storage_client.upload_file(file_name=filename, file_data=contents)
    except (ConnectionError, HTTPClientError, NoCredentialsError, BotoCoreError):
        raise HTTPException(
            status_code=500, detail="Failed to upload avatar. Please try again later."
        )

    file_url = await s3_storage_client.get_file_url(file_name=filename)

    if user_profile_db is None:
        raise HTTPException(status_code=400, detail="User profile does not exist.")

    user_profile_db.avatar = file_url
    db.add(user_profile_db)
    await db.commit()
    await db.refresh(user_profile_db)

    return user_profile_db


@router.post("/users/{user_id}/profile/", response_model=ProfileResponseSchema)
async def user_profile(
    user_id: str,
    user_data: ProfileRequestSchema,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
):

    try:
        decode_token = jwt_manager.decode_access_token(token=token)
    except TokenExpiredError:
        raise HTTPException(status_code=400, detail="Token has expired.")
    except InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid token")

    if int(user_id) != decode_token["user_id"]:
        raise HTTPException(
            status_code=403, detail="You don't have permission to edit this profile."
        )

    stmt = select(UserModel).where(UserModel.id == int(user_id))
    result = await db.execute(stmt)
    user_db = result.scalar_one_or_none()

    if user_db is None or not user_db.is_active:
        raise HTTPException(status_code=401, detail="User not found or not active.")

    stmt = select(UserProfileModel).where(UserProfileModel.user_id == int(user_id))
    result = await db.execute(stmt)
    user_profile_db = result.scalar_one_or_none()

    if user_profile_db:
        raise HTTPException(status_code=403, detail="User already has a profile.")

    create_user_profile = UserProfileModel(
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        gender=user_data.gender,
        date_of_birth=user_data.date_of_birth,
        info=user_data.info,
        avatar="",
        user=user_db,
    )

    db.add(create_user_profile)
    await db.commit()
    await db.refresh(create_user_profile)

    return create_user_profile
