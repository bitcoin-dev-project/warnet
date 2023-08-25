import jwt
from decouple import config
from ..db import schemas

JWT_SECRET =  config("JWT_SECRET");

def create_user_jwttoken(user: schemas.User):
	if JWT_SECRET is None:
		raise Exception("Add JWT_SECRET to .env")
		
	payload_data = {
	    "uuid": user.uuid,
	    "email":user.email
	}

	token = jwt.encode(
	    payload=payload_data,
	    key=JWT_SECRET,
	    algorithm="HS256"
	)
	return token
