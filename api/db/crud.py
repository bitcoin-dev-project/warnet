import uuid

import bcrypt
from sqlalchemy.orm import Session

from ..auth import api_token
from . import models, schemas

salt = bcrypt.gensalt()


def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_user_by_id(db: Session, user_id: int):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        return None
    return user


def get_user_by_email(db: Session, user: schemas.UserCreate):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user is None:
        return None
    if verify_password(user.password, db_user.password):
        return db_user
    else:
        return None


def create_user(db: Session, user: schemas.UserCreate):
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user is not None:
        return None
    pwd = user.password.encode("utf-8")
    hashed_password = bcrypt.hashpw(pwd, salt)
    created_user = schemas.UserCreate(
        uuid=str(uuid.uuid4()), email=user.email, password=hashed_password.decode("utf-8")
    )
    db_user = models.User(
        email=created_user.email,
        password=hashed_password.decode("utf-8"),
        uuid=created_user.uuid,
        api_token=api_token.create_user_jwttoken(created_user),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()


def get_networks(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Network).offset(skip).limit(limit).all()


def create_user_network(db: Session, network: schemas.NetworkCreate, user_id: int):
    db_network = models.Network(**network.dict(), owner_id=user_id)
    db.add(db_network)
    db.commit()
    db.refresh(db_network)
    return db_network
