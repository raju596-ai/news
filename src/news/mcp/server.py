import asyncio
import json
from mcp.server.fastmcp import FastMCP
from ..agents.single_agent import NewsRetrievalAgent

# Initialize MCP server
mcp = FastMCP("NewsIntelligenceServer")


@mcp.tool()
async def get_top_news_last_24h() -> str:
    """Retrieve top 5 worldwide and top 5 India news stories from the last 24 hours."""
    agent = NewsRetrievalAgent()
    report = await agent.run()
    return report.model_dump_json(indent=2)


if __name__ == "__main__":
    mcp.run()
