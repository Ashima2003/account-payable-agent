import shutil
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import ListToolsResult

import config

# The server exposes ~84 tools (backups, changefeeds, user/role management,
# DDL, ...) -- far more than a helpdesk query needs, and Gemini's function
# schema validation rejects the *entire* tool list if even one unrelated
# tool's schema is malformed (observed: a couple of admin tools have an
# array param with no `items`). execute_query is the only one actually
# needed -- list_tables/describe_table were tried too, but both read
# crdb_internal/system catalogs that ap_helpdesk_readonly can't access
# without a broader VIEWACTIVITY system privilege, so the schema is given
# to the model directly in the prompt (services/helpdesk_query_service.py)
# instead of via introspection.
_ALLOWED_TOOLS = {"execute_query"}


# Optional array-typed params (declared as `anyOf: [{type: array, items:
# {}}, {type: null}]`, the standard shape for an Optional[list] field) --
# google-genai's MCP-to-Gemini schema converter drops the `items` key when
# flattening that anyOf, and Gemini's API then rejects the whole tool list
# with "items: missing field". We never need parameterized queries here
# (the LLM just inlines literal values into the SQL text it writes), so
# the field is dropped rather than worked around.
_DROP_PROPERTIES = {"params", "where_params"}


class _FilteredClientSession(ClientSession):
    async def list_tools(self, *args, **kwargs) -> ListToolsResult:
        result = await super().list_tools(*args, **kwargs)
        result.tools = [t for t in result.tools if t.name in _ALLOWED_TOOLS]
        for tool in result.tools:
            properties = tool.inputSchema.get("properties", {})
            for name in _DROP_PROPERTIES:
                properties.pop(name, None)
        return result

# The community CockroachDB MCP server (github.com/amineelkouhen/mcp-cockroachdb),
# run via `uvx` so it needs no separate install/build step -- just uv. Always
# pointed at CRDB_READONLY_URL (a role with SELECT-only grants, see
# invoice-helpdesk-workflow-schema.sql) and started with --read-only, so
# LLM-generated SQL driven by untrusted inbound email text can never write
# to the database, even if a bug let a write-shaped query through.
_UVX_PATH = shutil.which("uvx")


def _server_params() -> StdioServerParameters:
    if not _UVX_PATH:
        raise RuntimeError("uvx not found on PATH -- install it with `brew install uv`.")
    if not config.CRDB_READONLY_URL:
        raise RuntimeError(
            "COCKROACHDB_READONLY_CONNECTION is not set -- cannot open the CockroachDB MCP session."
        )
    return StdioServerParameters(
        command=_UVX_PATH,
        args=[
            "--from", "git+https://github.com/amineelkouhen/mcp-cockroachdb.git",
            # The server's own pyproject pins "mcp[cli]>=1.9.4" with no
            # upper bound, so an unconstrained `uvx` resolves the newest
            # mcp (2.x), which removed mcp.server.fastmcp and breaks the
            # server outright (ModuleNotFoundError at startup). Force the
            # pre-2.0 API it was actually built against.
            "--with", "mcp<2",
            "cockroachdb-mcp-server",
            "--url", config.CRDB_READONLY_URL,
            "--read-only",
        ],
    )


@asynccontextmanager
async def open_session():
    async with stdio_client(_server_params()) as (read, write):
        async with _FilteredClientSession(read, write) as session:
            await session.initialize()
            yield session
