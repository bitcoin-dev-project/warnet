from pydantic import BaseModel


class NetworkBase(BaseModel):
    name: str
    status: bool = False

class NetworkCreate(NetworkBase):
    pass

class Network(NetworkBase):
    id: int
    owner_id: int

    class Config:
        orm_mode = True

class UserBase(BaseModel):
    email: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    networks: list[Network] = []

    class Config:
        orm_mode = True
