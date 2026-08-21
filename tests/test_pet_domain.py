from __future__ import annotations

import time

from open_llm_vtuber.pet.artifacts import ArtifactService
from open_llm_vtuber.pet.memory import MemoryStore
from open_llm_vtuber.pet.personas import build_system_prompt, get_persona, list_personas
from open_llm_vtuber.pet.proactivity import PresenceEvent, ProactiveScheduler
from open_llm_vtuber.pet.state import PetAction, PetWorldService


def test_persona_is_system_prompt_and_has_distinct_media_contract() -> None:
    personas = list_personas()

    assert len(personas) == 4
    assert len({profile.voice_id for profile in personas}) == 4
    assert len({profile.live2d_model for profile in personas}) == 4
    prompt = build_system_prompt(
        get_persona("sunny"),
        state_summary="饥饿 20/100",
        memory_summary="主人喜欢海边",
    )

    assert prompt.startswith("你是一个 AI 宠物")
    assert "饥饿 20/100" in prompt
    assert "主人喜欢海边" in prompt
    assert "禁止辱骂" in prompt


def test_pet_state_actions_persist_and_grow(tmp_path) -> None:
    service = PetWorldService(tmp_path / "pet.sqlite3")
    initial = service.get_state("demo")

    fed = service.perform_action("demo", PetAction.FEED)
    played = service.perform_action("demo", PetAction.PLAY)
    studied = service.perform_action("demo", PetAction.STUDY)
    reopened = PetWorldService(tmp_path / "pet.sqlite3").get_state("demo")

    assert fed.state.hunger < initial.hunger
    assert played.state.mood > fed.state.mood
    assert played.state.intimacy > fed.state.intimacy
    assert studied.state.experience > fed.state.experience
    assert reopened == studied.state
    assert reopened.level >= 1


def test_play_intent_is_inferred_from_companion_language(tmp_path) -> None:
    service = PetWorldService(tmp_path / "pet.sqlite3")

    assert service.infer_action("过来让我摸摸") is PetAction.PLAY
    assert service.infer_action("陪我玩一会儿") is PetAction.PLAY


def test_state_refresh_applies_time_decay(tmp_path) -> None:
    service = PetWorldService(tmp_path / "pet.sqlite3")
    before = service.get_state("demo")
    service.store.update_timestamp("demo", time.time() - 3600)

    after = service.get_state("demo")

    assert after.hunger > before.hunger
    assert after.energy < before.energy


def test_long_term_memory_retrieves_fact_across_instances(tmp_path) -> None:
    db_path = tmp_path / "pet.sqlite3"
    MemoryStore(db_path).remember("demo", "zodiac", "天秤座", importance=0.9)

    matches = MemoryStore(db_path).recall("demo", "我是什么星座", limit=3)

    assert matches[0].key == "zodiac"
    assert matches[0].value == "天秤座"


def test_artifacts_are_saved_inside_workspace(tmp_path) -> None:
    service = ArtifactService(tmp_path / "pet.sqlite3", tmp_path / "artifacts")
    letter = service.write_letter("demo", "主人", "今天也要记得好好休息。")
    drawing = service.create_drawing("demo", "和主人一起看星星")

    assert letter.path.exists()
    assert letter.path.suffix == ".md"
    assert drawing.path.exists()
    assert drawing.path.suffix == ".svg"
    assert str(letter.path.resolve()).startswith(
        str((tmp_path / "artifacts").resolve())
    )


def test_proactive_scheduler_handles_presence_with_cooldown() -> None:
    scheduler = ProactiveScheduler(cooldown_seconds=60)

    first = scheduler.evaluate(PresenceEvent("entered", 100.0))
    second = scheduler.evaluate(PresenceEvent("entered", 120.0))

    assert first.should_trigger is True
    assert first.action == "wave"
    assert second.should_trigger is False
