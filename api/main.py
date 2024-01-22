from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from .db import crud, database, models, schemas
from .validation import email

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


SESSION = Depends(get_db)


@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserLogin, db: Session = SESSION):
    """
    Create a new user.
    """
    result, error = email._validate_email(user.email)
    if error:
        raise HTTPException(status_code=400, detail=result)
    user.email = result
    db_user = crud.create_user(db, user)
    if db_user is None:
        raise HTTPException(status_code=400, detail="Email already registered")
    return db_user


@app.get("/users/", response_model=list[schemas.User])
def read_users(skip: int = 0, limit: int = 100, db: Session = SESSION):
    """
    Retrieve users.
    """
    users = crud.get_users(db, skip=skip, limit=limit)
    return users


@app.get("/users/{user_id}", response_model=schemas.User)
def read_user(user_id: int, db: Session = SESSION):
    """
    Get a specific user by id.
    """
    db_user = crud.get_user_by_id(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="email or password is incorrect")
    return db_user


@app.post("/users/{user_id}/networks/", response_model=schemas.Network)
def create_network_for_user(user_id: int, network: schemas.NetworkCreate, db: Session = SESSION):
    """
    Create a network for a specific user.
    """
    return crud.create_user_network(db=db, network=network, user_id=user_id)


@app.get("/networks/", response_model=list[schemas.Network])
def read_networks(skip: int = 0, limit: int = 100, db: Session = SESSION):
    """
    Retrieve networks.
    """
    netwworks = crud.get_networks(db, skip=skip, limit=limit)
    return netwworks
