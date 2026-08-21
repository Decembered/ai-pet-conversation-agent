"""Local MCP server exposing the first safe SLAI Pet business tools."""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from open_llm_vtuber.pet_domain import PetStateRepository, PetStateService

DATABASE_PATH = os.getenv("SLAI_PET_DB_PATH", "data/pet.db")
repository = PetStateRepository(DATABASE_PATH)
service = PetStateService(repository)
mcp = FastMCP("slai-pet-state")


@mcp.tool()
def get_pet_state(user_id: str = "default") -> dict:
    """Get the pet's real persisted state before discussing its condition."""

    return {"success": True, "state": service.get_pet_state(user_id).to_dict()}


@mcp.tool()
def feed_pet(
    food: str = "小鱼干",
    user_id: str = "default",
    request_id: str | None = None,
) -> dict:
    """Feed the pet once and persist state changes; safe to retry with request_id."""

    return service.feed_pet(
        user_id=user_id,
        food=food,
        request_id=request_id,
    ).to_dict()


if __name__ == "__main__":
    mcp.run(transport="stdio")
