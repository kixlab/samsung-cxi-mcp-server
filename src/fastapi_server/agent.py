from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import BaseTool
from langchain.schema.messages import HumanMessage, AIMessage
from dotenv import load_dotenv
from pathlib import Path
import os
import re
import json
from .model_factory import get_model
from config import load_config

load_dotenv()

CONFIG = load_config()
models = CONFIG.get("models", [])
if not models:
    raise ValueError("No models defined in config.yaml")
model = get_model(models[0])

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = str(Path(current_dir).parent)

server_params = StdioServerParameters(
    command="node",
    args=[f"{parent_dir}/talk_to_figma_mcp/dist/server.js"],
)

# Global references for reuse
agent = None
session = None
stdio_context = None
tool_dict = {}

async def startup():
    global agent, session, stdio_context, tool_dict
    stdio_context = stdio_client(server_params)
    read, write = await stdio_context.__aenter__()
    session = await ClientSession(read, write).__aenter__()
    await session.initialize()
    tools = await load_mcp_tools(session)
    tool_dict = {tool.name: tool for tool in tools if isinstance(tool, BaseTool)}
    agent = create_react_agent(model, tools)

async def shutdown():
    global session, stdio_context
    if session:
        await session.__aexit__(None, None, None)
    if stdio_context:
        await stdio_context.__aexit__(None, None, None)

async def run_agent(user_input: list):
    global agent

    human_message = HumanMessage(content=user_input)
    return await agent.ainvoke(
            {"messages": [human_message]},
            config={"recursion_limit": 100}
        )

async def call_tool(tool_name: str, args: dict = {}):
    global tool_dict, root_frame_id
    try:
        if tool_name not in tool_dict:
            return {"status": "error", "message": f"Tool '{tool_name}' not found"}
        tool = tool_dict[tool_name]
        result = await tool.ainvoke(args)
        return {"status": "success", "message": result, }
    
    except Exception as e:
        return {"status": "error", "message": str(e)}
