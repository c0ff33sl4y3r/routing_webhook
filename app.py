import fastapi, traceback
from fastapi import BackgroundTasks, FastAPI, Request, HTTPException, Query
from fastapi.responses import Response, JSONResponse
from config import *
import sqlite3, httpx
import validators, json
app = FastAPI()

client = httpx.AsyncClient()

db = sqlite3.connect('database.db', check_same_thread=False)
cursor = db.cursor()

# Verify facebook messenger subcription
def verify_token(hub_mode, hub_challenge, hub_verify_token):
    if hub_verify_token == META_VERIFY_TOKEN and hub_mode == 'subscribe':
        return int(hub_challenge)
    # Return Error 404 not found
    raise HTTPException(status_code=404, detail="Not found")

# Setup a client to send requests
@app.get("/")
async def index(request: Request):
    query_params = request.query_params
    hub_mode = query_params.get("hub.mode")
    hub_challenge = query_params.get("hub.challenge")
    hub_verify_token = query_params.get("hub.verify_token")
    return verify_token(hub_mode, hub_challenge, hub_verify_token)

@app.get("/port/{port}/{path:path}")
@app.post("/port/{port}/{path:path}")
@app.patch("/port/{port}/{path:path}")
@app.put("/port/{port}/{path:path}")
@app.delete("/port/{port}/{path:path}")
@app.options("/port/{port}/{path:path}")
async def dynamic_url(request: Request, port: int, path:str):
    # Sending request
    try:
        body = await request.body()        
        headers = dict(request.headers)
        # Get url from database     
        url = cursor.execute("SELECT url FROM callback WHERE port = ?", (port,)).fetchone()
        if not url:
            return {
                "status": "error",
                "message": "Port is not registered"
            }
        url = url[0]
        query_params = request.query_params
        access_token = query_params.get("access_token")
        # Check if access_token is correct
  
        ACCESS_TOKEN = cursor.execute("SELECT access_token FROM callback WHERE port = ?", (port,)).fetchone()[0]
        if not access_token and ACCESS_TOKEN:
            return {
                "status": "error",
                "message": "Parameter field access_token is required for this port"
            }
        if access_token != ACCESS_TOKEN:
            return {
                "status": "error",
                "message": "Access token is different from the one registered"
            }
        # Send request
        if path: url = url + '/' + path
        if query_params:
            url += "?"
            for key in query_params:
                url += f"{key}={query_params[key]}&"
            url = url[:-1]
        response = await client.request(request.method, url, headers=headers, data=body)
        print(url, body, response.headers)
        # Return response
        if isinstance(response.content, bytes):
            Content = response.content.decode('utf-8')
        try:
            Content = json.loads(Content)
        except:
            pass
        # Return the data
        return Content
    # If there is an error, log it to errlog.txt with trace
    except Exception as e:
        with open('errlog.txt', 'a') as f:
            f.write(str(e) + '\n')
            f.write(str(traceback.format_exc()) + '\n\n\n')
        # Return error with status 400
        return Response(status_code=400, content=str(e))

# @app.get("/port/{port}")
# @app.post("/port/{port}")
# @app.patch("/port/{port}")
# @app.put("/port/{port}")
# @app.delete("/port/{port}")
# @app.options("/port/{port}")
# async def static_url(request: Request, port: int):
#     return await dynamic_url(request, port, "")

# Return url of a page_id
@app.get("/get")
async def get(request: Request):
    # Get query params
    query_params = request.query_params
    port = query_params.get("port")
    # Handling error:
    try:
        data = cursor.execute("SELECT url, description FROM callback WHERE port = ?", (port,)).fetchone()
        data = {
            "url": data[0],
            "description": data[1]
        }
        return JSONResponse(status_code=200, content=data)
    # If there is an error, log it to errlog.txt with trace
    except Exception as e:
        with open('errlog.txt', 'a') as f:
            f.write(str(e) + '\n')
            f.write(str(traceback.format_exc()) + '\n\n\n')
        # Return error with status 400
        return Response(status_code=400, content="There was an error while retrieving the url.")

@app.post("/update")
async def update(request: Request):
    # Get the params of the request
    try:
        query_params = request.query_params
        port = query_params.get("port")
        access_token = query_params.get("access_token")
        description = query_params.get("description")
        url = query_params.get("url")
        # Remove beginning and ending spaces
        if url: url = url.strip()
        # Check if url is valid or not
        if not validators.url(url):
            raise Exception("A valid URL must be provided.")
        if not port or not url:
            raise Exception("Missing page_id or url")
        if not cursor.execute("SELECT * FROM callback WHERE port = ?", (port,)).fetchone():
            cursor.execute("INSERT INTO callback VALUES (?, ?, ?, ?)", (port, url, access_token, description))
        else:
            cursor.execute("UPDATE callback SET url = ?, access_token = ?, description = ? WHERE port = ?", (url, access_token, description, port))
        db.commit()
        return Response(status_code=200, content="Updated")
    # If there is an error, log it to errlog.txt with trace
    except Exception as e:
        with open('errlog.txt', 'a') as f:
            f.write(str(e) + '\n')
            f.write(str(traceback.format_exc()) + '\n\n\n')
        # Return error with status 400
        return Response(status_code=400, content=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8081, reload=True)