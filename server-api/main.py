from fastapi import FastAPI, Request, responses
from decouple import config
import query_string
import jwt
import requests

app = FastAPI()


RPC_HOST = config('RPC_HOST')

JWT_SECRET = config('JWT_SECRET')

ALLOWED_PATHS = ["/openapi.json", "/docs"]


## This middleware is to guard the API from unauthorized access in production.
# @app.middleware("http")
# async def add_process_time_header(request: Request, call_next):
#     url_parts = query_string.parse(request.url.query)
#     access_token = str(url_parts.get('api_key'))
#     user_id = url_parts.get('user_id')
    
#     if request.url.path in ALLOWED_PATHS:
#         return await call_next(request)
    
#     if not access_token:
#         return responses.JSONResponse(status_code=401, content={'reason': "api_key is required"})
    
#     if not user_id:
#         return responses.JSONResponse(status_code=401, content={'reason': "user_id is required"})
    
#     try:
#         decoded_token = jwt.decode(access_token, key=JWT_SECRET, algorithms=["HS256"])
#         uuid = decoded_token['uuid']
#         if user_id != uuid:
#             return responses.JSONResponse(status_code=401, content={'reason': "unauthorized user"})
        
#         response = await call_next(request)
#         response.headers["x-access-token"] = access_token
#         return response

#     except jwt.InvalidTokenError:
#         return responses.JSONResponse(status_code=401, content={'reason': "Invalid or expired token"})
#     except Exception as e:
#         return responses.JSONResponse(status_code=500, content={'reason': str(e)})

@app.get("/warnet")
def read_root(api_key: str, user_id: str):
    return {"logged in": True}

@app.post("/list_scenarios")
def list_scenarios(rpc_data: dict):
    rpc_url = RPC_HOST

    rpc_data = rpc_data

    try:
        response = requests.post(rpc_url, json=rpc_data)

        if response.status_code == 200:
            rpc_result = response.json()
            return {"result": rpc_result}
        else:
            return {"error": "RPC request failed"}
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}
    
@app.post("/list_acrive_scenarios") #This lists the active scenarios
def list_active_scenarios(rpc_data: dict):
    rpc_url = RPC_HOST

    rpc_data = rpc_data

    try:
        response = requests.post(rpc_url, json=rpc_data)

        if response.status_code == 200:
            rpc_result = response.json()
            return {"result": rpc_result}
        else:
            return {"error": "RPC request failed"}
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

    
@app.post("/start_warnet") #this starts the warnet service
def start_warnet(rpc_data:dict):
    rpc_url = RPC_HOST

    rpc_data = rpc_data

    try:
        response = requests.post(rpc_url, json=rpc_data)

        if response.status_code == 200:
            rpc_result = response.json()
            return {"result": rpc_result}
        else:
            return {"error": "RPC request failed"}
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}
    
    
@app.post("/stop_warnet") #this stops the warnet service
def stop_warnet(rpc_data:dict):
    rpc_url = RPC_HOST

    rpc_data = rpc_data

    try:
        response = requests.post(rpc_url, json=rpc_data)

        if response.status_code == 200:
            rpc_result = response.json()
            return {"result": rpc_result}
        else:
            return {"error": "RPC request failed"}
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}