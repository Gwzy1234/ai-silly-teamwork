from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from silly_teamwork.ai.llm import MockProvider
from silly_teamwork.ai.service import AIAssistantService
from silly_teamwork.ai.tools import AIToolLayer
from silly_teamwork.models.ai_generation import AIGeneration
from silly_teamwork.models.enums import AIGenerationType

pytestmark = pytest.mark.asyncio


def _risk_payload() -> str:
    return json.dumps(
        {
            "risk_level": "low",
            "summary": "项目风险较低",
            "reasons": [],
            "suggestions": [],
        }
    )


async def test_risk_generation_is_persisted(ai_context) -> None:
    service = AIAssistantService(
        provider=MockProvider(default_response=_risk_payload()),
        tool_layer=AIToolLayer(),
    )

    async with ai_context.session_factory() as session:
        await service.analyze_project_risk(
            session,
            ai_context.member,
            ai_context.project.id,
        )

    async with ai_context.session_factory() as session:
        rows = list(
            (
                await session.execute(
                    select(AIGeneration).order_by(AIGeneration.created_at)
                )
            ).scalars().all()
        )
        assert len(rows) == 1
        assert rows[0].project_id == ai_context.project.id
        assert rows[0].user_id == ai_context.member.id
        assert rows[0].type is AIGenerationType.RISK_ANALYSIS
        assert rows[0].response_data["risk_level"] == "low"


async def test_all_three_generations_are_persisted_and_history_returns_latest(ai_context) -> None:
    task_payload = json.dumps(
        {
            "suggestions": [
                {
                    "title": "撰写报告",
                    "description": None,
                    "priority": "medium",
                    "starts_at": None,
                    "due_at": None,
                    "recommended_owner_user_id": None,
                    "reason": "基础任务",
                }
            ]
        }
    )
    weekly_payload = json.dumps(
        {
            "summary": "本周正常",
            "highlights": [],
            "risks": [],
            "suggestions": [],
        }
    )
    provider = MockProvider(
        responses=[_risk_payload(), task_payload, weekly_payload]
    )
    service = AIAssistantService(provider=provider, tool_layer=AIToolLayer())

    async with ai_context.session_factory() as session:
        await service.analyze_project_risk(
            session,
            ai_context.member,
            ai_context.project.id,
        )
        await service.suggest_tasks(
            session,
            ai_context.member,
            ai_context.project.id,
            instruction="规划任务",
            count=1,
        )
        await service.generate_weekly_report(
            session,
            ai_context.member,
            ai_context.project.id,
        )

    async with ai_context.session_factory() as session:
        history = await service.get_ai_history(
            session,
            ai_context.member,
            ai_context.project.id,
        )
        assert history.risk_analysis is not None
        assert history.task_suggestions is not None
        assert history.weekly_report is not None

    async with ai_context.session_factory() as session:
        rows = list(
            (
                await session.execute(
                    select(AIGeneration).order_by(AIGeneration.created_at)
                )
            ).scalars().all()
        )
        assert len(rows) == 3
