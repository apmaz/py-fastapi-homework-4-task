from datetime import date

from fastapi import UploadFile, Form, File, HTTPException
from pydantic import BaseModel, field_validator, HttpUrl, Field

from database.models.accounts import GenderEnum, UserModel
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date,
    validate_info,
)


class ProfileRequestSchema(BaseModel):
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str
    avatar: str

    @field_validator("first_name")
    @classmethod
    def check_first_name(cls, value):
        return validate_name(value)

    @field_validator("last_name")
    @classmethod
    def check_last_name(cls, value):
        return validate_name(value)

    @field_validator("gender")
    @classmethod
    def check_gender(cls, value):
        return validate_gender(value)

    @field_validator("date_of_birth")
    @classmethod
    def check_date_of_birth(cls, value):
        return validate_birth_date(value)

    @field_validator("info")
    @classmethod
    def check_info(cls, value):
        return validate_info(value)

    # @field_validator("avatar")
    # @classmethod
    # def check_date_of_birth(cls, value):
    #     return validate_image(value)


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str
    avatar: str
