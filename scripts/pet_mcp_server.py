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


@mcp.tool()
def play_with_pet(
    game: str = "追激光笔",
    user_id: str = "default",
    request_id: str | None = None,
) -> dict:
    """Play with the pet once: spends energy, raises mood and intimacy."""

    return service.play_with_pet(
        user_id=user_id,
        game=game,
        request_id=request_id,
    ).to_dict()


@mcp.tool()
def clean_pet(
    method: str = "洗澡",
    user_id: str = "default",
    request_id: str | None = None,
) -> dict:
    """Clean the pet once: raises cleanliness and slightly improves mood."""

    return service.clean_pet(
        user_id=user_id,
        method=method,
        request_id=request_id,
    ).to_dict()


@mcp.tool()
def put_pet_to_sleep(
    user_id: str = "default",
    request_id: str | None = None,
) -> dict:
    """Put the pet to sleep so energy recovers over real elapsed time."""

    return service.put_pet_to_sleep(
        user_id=user_id,
        request_id=request_id,
    ).to_dict()


if __name__ == "__main__":
    mcp.run(transport="stdio")
