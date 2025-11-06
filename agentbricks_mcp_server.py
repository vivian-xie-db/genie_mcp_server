import contextlib
import logging
from collections.abc import AsyncIterator
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.types import Receive, Scope, Send
import uvicorn
from dotenv import load_dotenv
import os
import json
from pydantic import AnyUrl
from pathlib import Path
from model_serving_utils import query_endpoint, endpoint_supports_feedback
load_dotenv()
SERVING_ENDPOINT = os.getenv('SERVING_ENDPOINT')
app = Server("mcp-server")

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    ctx = app.request_context
    query = arguments.get("query")
    if not query:
        raise ValueError("'query' is required in arguments")

    
    input_messages = [{"role": "user", "content": query}]

    try:
        messages, request_id = query_endpoint(
            endpoint_name=SERVING_ENDPOINT,
            messages=input_messages,
            return_traces=False
        )
        # Extract response content
        response = ""
        for msg in messages:
            if isinstance(msg, dict) and msg.get("content"):
                response += msg.get("content", "")
        
    except Exception as err:
        # Stream an error notification
        raise
    return [
        types.TextContent(type="text", text=response),
    ]


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="agent-bricks",
            description="agent bricks",
            inputSchema={
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query to be answered by the agent-bricks",
                    }
                },
            },
        )
    ]

session_manager = StreamableHTTPSessionManager(
    app=app,
    event_store=None,  
    stateless=True,
)

async def handle_streamable_http(scope: Scope, receive: Receive, send: Send) -> None:
    await session_manager.handle_request(scope, receive, send)

@contextlib.asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[None]:
    async with session_manager.run():
        try:
            yield
        finally:
            pass

starlette_app = Starlette(
    debug=False,
    routes=[Mount("/api/mcp", app=handle_streamable_http)],
    lifespan=lifespan,
)

if __name__ == "__main__":
    uvicorn.run(starlette_app, port=8000)