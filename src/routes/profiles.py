from datetime import date
from fastapi import Depends
from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_s3_storage_client, get_jwt_auth_manager
from database import get_db, UserModel, UserProfileModel
from exceptions import TokenExpiredError, InvalidTokenError, S3FileUploadError
from schemas.profiles import ProfileResponseSchema

from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface
from validation import validate_image, validate_birth_date, validate_name, validate_gender, validate_info


router = APIRouter()


def check_field(
        first_name: str = Form(...),
        last_name: str = Form(...),
        date_of_birth: date = Form(...),
        gender: str = Form(...),
        info: str = Form(...),
        avatar: UploadFile = File(...),
):

    try:
        validate_name(first_name)
        validate_name(last_name)
        validate_birth_date(date_of_birth)
        validate_gender(gender)
        validate_info(info)
        validate_image(avatar)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return (
        first_name.lower(),
        last_name.lower(),
        date_of_birth,
        gender,
        info,
        avatar
    )


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=201
)
async def create_user_profile(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_storage_client: S3StorageInterface = Depends(get_s3_storage_client),
    user_data: tuple = Depends(check_field),
):

    first_name, last_name, date_of_birth, gender, info, avatar = user_data

    try:
        decode_token = jwt_manager.decode_access_token(token=token)

    except TokenExpiredError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired."
        )

    except InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )

    stmt = select(UserModel).where(UserModel.id == decode_token["user_id"])
    result = await db.execute(stmt)
    current_user = result.scalar_one_or_none()

    if current_user is None or not current_user.is_active:
        raise HTTPException(
            status_code=401,
            detail="User not found or not active."
        )

    stmt = select(UserModel).where(UserModel.id == int(user_id))
    result = await db.execute(stmt)
    target_user = result.scalar_one_or_none()

    if target_user is None or not target_user.is_active:
        raise HTTPException(
            status_code=401,
            detail="User not found or not active."
        )

    if current_user.id == target_user.id or current_user.group_id == 3:
        stmt = select(UserProfileModel).where(UserProfileModel.user_id == int(user_id))
        result = await db.execute(stmt)
        user_profile_db = result.scalar_one_or_none()

        if user_profile_db:
            raise HTTPException(
                status_code=400,
                detail="User already has a profile."
            )

        target_user_id = int(user_id)
        avatar_key = f"avatars/{target_user_id}_avatar.{avatar.filename.split('.')[-1]}"
        contents = await avatar.read()

        try:
            await s3_storage_client.upload_file(file_name=avatar_key, file_data=contents)
        except S3FileUploadError:
            raise HTTPException(
                status_code=500,
                detail="Failed to upload avatar. Please try again later."
            )

        avatar_url = await s3_storage_client.get_file_url(avatar_key)

        try:
            user_profile = UserProfileModel(
                first_name=first_name,
                last_name=last_name,
                gender=gender,
                date_of_birth=date_of_birth,
                info=info,
                avatar=avatar_url,
                user=target_user,
            )
            db.add(user_profile)
            await db.commit()
            await db.refresh(user_profile)

            return user_profile

        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=400, detail="Invalid input data.")

    raise HTTPException(
        status_code=403, detail="You don't have permission to edit this profile."
    )
