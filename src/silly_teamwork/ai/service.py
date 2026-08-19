from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.ai.llm import (
    AIResponseError,
    LLMProvider,
    create_llm_provider,
)
from silly_teamwork.ai.prompts import (
    build_risk_analysis_prompt,
    build_task_suggestion_prompt,
    build_weekly_report_prompt,
)
from silly_teamwork.ai.schemas import (
    RiskAnalysisResponse,
    TaskSuggestion,
    TaskSuggestionResponse,
    WeeklyReportResponse,
)
from silly_teamwork.ai.tools import AIToolLayer, get_ai_tool_layer
from silly_teamwork.models.user import User

_OPEN_TASK_STATUSES = {"todo", "in_progress", "in_review"}


class AIAssistantService:
    """Orchestrates tool data gathering, prompt building, and LLM inference."""

    def __init__(
        self,
        *,
        provider: LLMProvider | None = None,
        tool_layer: AIToolLayer | None = None,
        max_tokens: int = 2000,
    ) -> None:
        self.provider = provider or create_llm_provider()
        self.tools = tool_layer or get_ai_tool_layer()
        self.max_tokens = max_tokens

    async def analyze_project_risk(
        self,
        session: AsyncSession,
        current_user: User,
        project_id: UUID,
    ) -> RiskAnalysisResponse:
        snapshot = await self.tools.get_project_snapshot(
            session,
            current_user,
            project_id,
        )
        messages = build_risk_analysis_prompt(snapshot)
        content = await self.provider.complete(
            messages,
            max_tokens=self.max_tokens,
            temperature=0.2,
        )
        data = self._parse_json(content)
        return RiskAnalysisResponse(
            project_id=project_id,
            risk_level=data["risk_level"],
            summary=data["summary"],
            reasons=data["reasons"],
            suggestions=data["suggestions"],
            generated_at=datetime.now(UTC),
        )

    async def suggest_tasks(
        self,
        session: AsyncSession,
        current_user: User,
        project_id: UUID,
        *,
        instruction: str,
        count: int = 5,
    ) -> TaskSuggestionResponse:
        snapshot = await self.tools.get_project_snapshot(
            session,
            current_user,
            project_id,
        )
        messages = build_task_suggestion_prompt(snapshot, instruction, count)
        content = await self.provider.complete(
            messages,
            max_tokens=self.max_tokens,
            temperature=0.4,
        )
        data = self._parse_json(content)
        suggestions_data = data["suggestions"]
        if not isinstance(suggestions_data, list):
            raise AIResponseError("LLM response 'suggestions' must be a list")
        suggestions = [TaskSuggestion.model_validate(item) for item in suggestions_data]
        return TaskSuggestionResponse(project_id=project_id, suggestions=suggestions)

    async def generate_weekly_report(
        self,
        session: AsyncSession,
        current_user: User,
        project_id: UUID,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> WeeklyReportResponse:
        period_end = end_date or datetime.now(UTC).date()
        period_start = start_date or (period_end - timedelta(days=6))
        if period_start > period_end:
            raise ValueError("start_date must not be after end_date")

        snapshot = await self.tools.get_project_snapshot(
            session,
            current_user,
            project_id,
            include_files=True,
            start_date=period_start,
            end_date=period_end,
        )
        messages = build_weekly_report_prompt(snapshot, period_start, period_end)
        content = await self.provider.complete(
            messages,
            max_tokens=self.max_tokens,
            temperature=0.3,
        )
        data = self._parse_json(content)

        now = datetime.now(UTC)
        completed_tasks = [
            task for task in snapshot.tasks if task.status == "done"
        ]
        unfinished_tasks = [
            task for task in snapshot.tasks if task.status in _OPEN_TASK_STATUSES
        ]
        overdue_tasks = [
            task
            for task in unfinished_tasks
            if task.due_at is not None and self._as_utc(task.due_at) < now
        ]
        return WeeklyReportResponse(
            project_id=project_id,
            period_start=period_start,
            period_end=period_end,
            completed_tasks=completed_tasks,
            unfinished_tasks=unfinished_tasks,
            overdue_tasks=overdue_tasks,
            file_updates=snapshot.files,
            summary=data["summary"],
            highlights=data["highlights"],
            risks=data["risks"],
            suggestions=data["suggestions"],
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise AIResponseError("LLM response is not valid JSON") from error
        if not isinstance(data, dict):
            raise AIResponseError("LLM response must be a JSON object")
        return data


def get_ai_assistant_service() -> AIAssistantService:
    return AIAssistantService()
