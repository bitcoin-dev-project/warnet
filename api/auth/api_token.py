import jwt
from ..db import crud, models, schemas, database
from decouple import config
JWT_SECRET =  config("JWT_SECRET");

def create_user_jwttoken(user:schemas.User):
	payload_data = {
	    "uuid": user.uuid,
	    "email":user.email
	}

	my_secret = JWT_SECRET;

	token = jwt.encode(
	    payload=payload_data,
	    key=my_secret
	)
	return token
