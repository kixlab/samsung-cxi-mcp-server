from fastapi import FastAPI, Request, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from agent import startup, shutdown, run_agent, call_tool
from utils import jsonify_agent_response
import base64
from pydantic import BaseModel
import uvicorn
import os
import re
import json
from typing import Optional

class ChatRequest(BaseModel):
    message: str

# Define lifespan context
from contextlib import asynccontextmanager
@asynccontextmanager
async def lifespan_context():
    await startup()
    yield
    await shutdown()
    
# ========== Server State ==========

root_frame_id: Optional[str] = None
root_frame_width: Optional[int] = None
root_frame_height: Optional[int] = None

async def check_root_frame():
    # [1] Check if root_frame_id is set
    if root_frame_id is None:
        raise ValueError("Root frame ID is not set. Please create a root frame first.")
    
    # [2] Check if root_frame_id exists in the document structure
    response = await call_tool("get_document_info")
    document_info = json.loads(response["message"])
    
    root_frame_in_canvas = next(
        (child for child in document_info["children"] if child["id"] == root_frame_id), 
        None
    )
    if root_frame_in_canvas is None:
        raise ValueError("Root frame ID is not found in the document structure.")

# ========== FastAPI Setup & Static Hosting =========
    
# Create directory structure if it doesn't exist
static_dir = os.path.join(os.path.dirname(__file__), "static")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")

os.makedirs(static_dir, exist_ok=True)
os.makedirs(templates_dir, exist_ok=True)

app = FastAPI(lifespan=lambda app: lifespan_context())
    
# Mount static files directory
app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

# ========== Routes =========

@app.get("/", response_class=HTMLResponse)
async def get_homepage(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        await check_root_frame()
        
        if req.message:
            system_prompt_prefix = f"""
[ROOT FRAME ID]
Contain all creation (e.g., text, rectangle, frame.) in the root frame.
Root Frame ID: {root_frame_id}
Root Frame Width: {root_frame_width}
Root Frame Height: {root_frame_height}
            """
            full_message = system_prompt_prefix + req.message
            agent_input = [{"type": "text", "text": full_message}]
            response = await run_agent(agent_input)
            json_response = jsonify_agent_response(response)
            return {"response": str(response), "json_response": json_response}
      
    except Exception as e:
        return {"response": f"Error: {str(e)}"}

@app.post("/chat-img")
async def chat_img(image: UploadFile = File(None), message: str = Form(...)):
    try:
        await check_root_frame()
        
        base64_image = None
        if image:
            image_bytes = await image.read()
            base64_image = base64.b64encode(image_bytes).decode("utf-8")

        agent_input = []
        if message:
            system_prompt_prefix = f"""
[ROOT FRAME ID]
Contain all creation (e.g., text, rectangle, frame.) in the root frame.
Root Frame ID: {root_frame_id}
Root Frame Width: {root_frame_width}
Root Frame Height: {root_frame_height}
            """
            full_message = system_prompt_prefix + message
            agent_input.append({"type": "text", "text": full_message})
        if base64_image:
            agent_input.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{base64_image}",
                    "detail": "auto"
                }
            })

        response = await run_agent(agent_input)
        json_response = jsonify_agent_response(response)
        return {"response": str(response), "json_response": json_response}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/tool/get_selection")
async def get_selection():
    result = await call_tool("get_selection")
    return result

@app.post("/tool/create_root_frame")
async def create_root_frame_endpoint(
    x: int = Query(0),
    y: int = Query(0),
    width: int = Query(...),
    height: int = Query(...),
    name: str = Query("Frame")
):
    result = await call_tool("create_frame", {
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "name": name,
        "fillColor": {"r": 1, "g": 1, "b": 1, "a": 1}
    })
    global root_frame_width, root_frame_height, root_frame_id
    root_frame_width = width
    root_frame_height = height
    
    if isinstance(result, dict) and "message" in result:
        id_match = re.search(r'with ID: ([^\.]+)', result["message"])
        if id_match:
            root_frame_id = id_match.group(1)
            print(f"Set root_frame_id to {root_frame_id} and set width, height to {root_frame_width}, {root_frame_height}")
    return result

@app.post("/tool/create_text_in_root_frame")
async def create_text_in_root_frame():
    global root_frame_id
    if not root_frame_id:
        return {"status": "error", "message": "No root_frame_id set. Please call /tool/create_frame first."}

    result = await call_tool("create_text", {
        "parentId": root_frame_id,
        "x": 100,
        "y": 100,
        "text": "Hello in root!"
    })
    return result

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)