from __future__ import annotations

import json

import pytest

from silly_teamwork.ai.llm import MockProvider
from silly_teamwork.ai.schemas import RiskLevel
from silly_teamwork.ai.service import AIAssistantService
from silly_teamwork.ai.tools import AIToolLayer

pytestmark = pytest.mark.asyncio


async def test_risk_analysis_service_with_mock_llm(ai_context) -> None:
    payload = {
        "risk_level": "high",
        "summary": "项目存在延期风险",
        "reasons": ["文献综述还有3天到期但未开始"],
        "suggestions": ["提高优先级", "重新分配任务"],
    }
    provider = MockProvider(default_response=json.dumps(payload))
    service = AIAssistantService(provider=provider, tool_layer=AIToolLayer())

    async with ai_context.session_factory() as session:
        result = await service.analyze_project_risk(
            session,
            ai_context.member,
            ai_context.project.id,
        )

    assert result.risk_level is RiskLevel.HIGH
    assert result.summary == "项目存在延期风险"
    assert len(result.reasons) == 1
    assert len(result.suggestions) == 2
    assert len(provider.calls) == 1


async def test_task_suggestion_service_with_mock_llm(ai_context) -> None:
    payload = {
        "suggestions": [
            {
                "title": "撰写开题报告",
                "description": "完成课程论文开题",
                "priority": "high",
                "starts_at": "2026-08-20T00:00:00Z",
                "due_at": "2026-08-25T00:00:00Z",
                "recommended_owner_user_id": str(ai_context.member.id),
                "reason": "该成员当前负载较低",
            }
        ]
    }
    provider = MockProvider(default_response=json.dumps(payload))
    service = AIAssistantService(provider=provider, tool_layer=AIToolLayer())

    async with ai_context.session_factory() as session:
        result = await service.suggest_tasks(
            session,
            ai_context.member,
            ai_context.project.id,
            instruction="帮我规划一个课程论文项目",
            count=1,
        )

    assert result.project_id == ai_context.project.id
    assert len(result.suggestions) == 1
    suggestion = result.suggestions[0]
    assert suggestion.title == "撰写开题报告"
    assert suggestion.recommended_owner_user_id == ai_context.member.id


async def test_weekly_report_service_with_mock_llm(ai_context) -> None:
    payload = {
        "summary": "本周项目推进正常",
        "highlights": ["完成文献收集"],
        "risks": ["下周截止任务较多"],
        "suggestions": ["提前开始撰写"],
    }
    provider = MockProvider(default_response=json.dumps(payload))
    service = AIAssistantService(provider=provider, tool_layer=AIToolLayer())

    async with ai_context.session_factory() as session:
        result = await service.generate_weekly_report(
            session,
            ai_context.member,
            ai_context.project.id,
        )

    assert result.period_start <= result.period_end
    assert result.summary == "本周项目推进正常"
    assert len(result.completed_tasks) == 0
    assert len(result.unfinished_tasks) == 2
    assert len(result.overdue_tasks) == 0
    assert len(result.file_updates) == 1


async def test_service_accepts_markdown_fenced_json(ai_context) -> None:
    provider = MockProvider(
        default_response=(
            "```json\n"
            '{"risk_level": "low", "summary": "ok", "reasons": [], "suggestions": []}\n'
            "```"
        )
    )
    service = AIAssistantService(provider=provider, tool_layer=AIToolLayer())

    async with ai_context.session_factory() as session:
        result = await service.analyze_project_risk(
            session,
            ai_context.member,
            ai_context.project.id,
        )

    assert result.risk_level is RiskLevel.LOW
