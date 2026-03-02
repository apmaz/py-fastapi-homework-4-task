from datetime import date
from pydantic import BaseModel

from database.models.accounts import GenderEnum


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: GenderEnum
    date_of_birth: date
    info: str
    avatar: str

    model_config = {"from_attributes": True}
