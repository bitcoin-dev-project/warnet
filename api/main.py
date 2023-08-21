from typing import Union

from fastapi import FastAPI

app = FastAPI()

app = FastAPI(
    title="Warnet API",
    description="Warnet API",
    version="0.0.1",
)

@app.get("/")
def read_root():
    return {"Hello Viking": "Welcome to Warnet!"}

@app.post("/warnet")
def read_root():
    return {"Hello": "warnet"}

@app.get("/users/me")
def read_user_me():
    return {"user_id": "the current user"}

@app.get("/user/{user_id}")
def read_item(user_id: int, q: Union[str, None] = None):
    return {"user_id": user_id, "q": q}
