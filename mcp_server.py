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
import glob
import json
from pydantic import AnyUrl
from pathlib import Path
load_dotenv()

DATABRICKS_APP_PORT = os.getenv("DATABRICKS_APP_PORT",8000)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("genie-mcp-server")

app = Server("genie-mcp-server")

AGENT_CARDS_DIR = "agent_cards"

def load_agent_cards():
    """Loads agent card data from JSON files within a specified directory."""
    card_uris = []
    agent_cards = {}
    dir_path = Path(AGENT_CARDS_DIR)
    if not dir_path.is_dir():
        logger.error(f'Agent cards directory not found or is not a directory: {AGENT_CARDS_DIR}')
        return card_uris, agent_cards
    logger.info(f'Loading agent cards from card repo: {AGENT_CARDS_DIR}')
    for filename in os.listdir(AGENT_CARDS_DIR):
        if filename.lower().endswith('.json'):
            file_path = dir_path / filename
            card_name = Path(filename).stem
            uri = f'resource://agent_cards/{card_name}'
            if file_path.is_file():
                logger.info(f'Reading file: {filename}')
                try:
                    with file_path.open('r', encoding='utf-8') as f:
                        data = json.load(f)
                        card_uris.append(uri)
                        agent_cards[uri] = data
                except json.JSONDecodeError as jde:
                    logger.error(f'JSON Decoder Error {jde}')
                except OSError as e:
                    logger.error(f'Error reading file {filename}: {e}.')
                except Exception as e:
                    logger.error(f'An unexpected error occurred processing {filename}: {e}', exc_info=True)
    logger.info(f'Finished loading agent cards. Found {len(agent_cards)} cards.')
    return card_uris, agent_cards

# Preload agent cards at module load
tag_card_uris, AGENT_CARD_RESOURCES = load_agent_cards()

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
app = Server("genie-mcp-server")

@app.list_resources()
async def list_resources() -> list[types.Resource]:
    resources = []
    # Individual card endpoints
    for uri in tag_card_uris:
        card = AGENT_CARD_RESOURCES.get(uri, {})
        name = card.get("name", uri)
        resources.append(
            types.Resource(
                uri=uri,
                name=name,
                mimeType="application/json"
            )
        )
    return resources

@app.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    uri_str = str(uri)
    if uri_str in AGENT_CARD_RESOURCES:
        return json.dumps(AGENT_CARD_RESOURCES[uri_str], indent=2)
    raise ValueError("Resource not found")


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
    uvicorn.run(starlette_app, port=DATABRICKS_APP_PORT)



