from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import BaseTool
from langchain.schema.messages import HumanMessage, AIMessage
from langsmith import traceable
from langchain.callbacks.tracers.langchain import LangChainTracer
from dotenv import load_dotenv
from pathlib import Path
import os
import re
import json
from .model_factory import get_model
from config import load_server_config

load_dotenv()

# Global references
model = None
agent = None
session = None
stdio_context = None
tool_dict = {}

def make_tracer():
    import os
    from langsmith.client import Client

    tags_str = os.getenv("LANGSMITH_EXPERIMENT_TAGS", "")
    tags = [t.strip() for t in tags_str.split(",") if t.strip()]
    project = os.getenv("LANGCHAIN_PROJECT", "canvasbench-default")

    return LangChainTracer(project_name=project, tags=tags)

tracer = make_tracer()

CONFIG = None

def initialize_model(agent_type: str = "single"):
    global CONFIG, model
    CONFIG = load_server_config(agent_type)
    models = CONFIG.get("models", [])
    if not models:
        raise ValueError("No models defined in config")
    model = get_model(models[0])

# Stdio MCP server path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = str(Path(current_dir).parent)

server_params = StdioServerParameters(
    command="node",
    args=[f"{parent_dir}/talk_to_figma_mcp/dist/server.js"],
)

async def startup(agent_type: str):
    global agent, session, stdio_context, tool_dict, model
    initialize_model(agent_type)

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

async def run_single_agent(user_input: list, metadata: dict = None):
    global agent
    human_message = HumanMessage(content=user_input)
    tags = [f"{k}={v}" for k, v in (metadata or {}).items()]

    return await agent.ainvoke(
        {"messages": [human_message]},
        config={
            "recursion_limit": 100,
            "callbacks": [tracer],
            "tags": tags,
            "metadata": metadata or {}
        }
    )

async def call_tool(tool_name: str, args: dict = {}):
    global tool_dict
    try:
        if tool_name not in tool_dict:
            return {"status": "error", "message": f"Tool '{tool_name}' not found"}
        tool = tool_dict[tool_name]
        result = await tool.ainvoke(args)
        return {"status": "success", "message": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}