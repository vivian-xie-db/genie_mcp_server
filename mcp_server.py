import contextlib
import logging
from collections.abc import AsyncIterator
import pandas as pd
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.types import Receive, Scope, Send
from genie_room import genie_query
import uvicorn
from dotenv import load_dotenv
import os

load_dotenv()
DATABRICKS_APP_PORT = os.getenv("DATABRICKS_APP_PORT")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("genie-mcp-server")

app = Server("genie-mcp-server")

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle genie tool call."""
    ctx = app.request_context
    query = arguments.get("query")
    if not query:
        raise ValueError("'query' is required in arguments")

    # Stream a log message
    await ctx.session.send_log_message(
        level="info",
        data=f"Fetching an answer for {query} from genie…",
        logger="genie-mcp-server",
        related_request_id=ctx.request_id,
    )

    try:
        response, _ = await genie_query(query)
        if isinstance(response, pd.DataFrame):
            # turn pandas dataframe into a json
            response = response.to_json(orient="records")
    except Exception as err:
        # Stream an error notification
        await ctx.session.send_log_message(
            level="error",
            data=str(err),
            logger="genie-mcp-server",
            related_request_id=ctx.request_id,
        )
        raise

    # Stream a success notification
    await ctx.session.send_log_message(
        level="info",
        data="Answer fetched successfully!",
        logger="genie-mcp-server",
        related_request_id=ctx.request_id,
    )

    return [
        types.TextContent(type="text", text=response),
    ]

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="genie-query",
            description="Query the genie room to get an answer to supply chain and distribution questions",
            inputSchema={
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query to be answered by the genie room",
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
        logger.info("Genie MCP server started!")
        try:
            yield
        finally:
            logger.info("Genie MCP server stopped!")


starlette_app = Starlette(
    debug=False,
    routes=[Mount("/api/mcp", app=handle_streamable_http)],
    lifespan=lifespan,
)


if __name__ == "__main__":
    uvicorn.run(starlette_app, host="0.0.0.0", port=DATABRICKS_APP_PORT)



