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
    uuid: str 
    password: str

class UserLogin(UserBase):
    password:str

class User(UserBase):
    id: int
    uuid: str
    apiToken: str
    networks: list[Network] = []

    class Config:
        orm_mode = True
