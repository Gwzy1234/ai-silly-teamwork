from __future__ import annotations

import json
import logging
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
    AIHistoryResponse,
    RiskAnalysisResponse,
    TaskSuggestion,
    TaskSuggestionResponse,
    WeeklyReportResponse,
)
from silly_teamwork.ai.tools import AIToolLayer, get_ai_tool_layer
from silly_teamwork.models.ai_generation import AIGeneration
from silly_teamwork.models.enums import AIGenerationType
from silly_teamwork.models.user import User
from silly_teamwork.repositories import ai_generations

logger = logging.getLogger(__name__)

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
        result = RiskAnalysisResponse(
            project_id=project_id,
            risk_level=data["risk_level"],
            summary=data["summary"],
            reasons=data["reasons"],
            suggestions=data["suggestions"],
            generated_at=datetime.now(UTC),
        )
        await self._save_generation(
            session,
            user_id=current_user.id,
            project_id=project_id,
            generation_type=AIGenerationType.RISK_ANALYSIS,
            request_data={},
            response_data=result.model_dump(mode="json"),
        )
        return result

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
        result = TaskSuggestionResponse(project_id=project_id, suggestions=suggestions)
        await self._save_generation(
            session,
            user_id=current_user.id,
            project_id=project_id,
            generation_type=AIGenerationType.TASK_SUGGESTIONS,
            request_data={"instruction": instruction, "count": count},
            response_data=result.model_dump(mode="json"),
        )
        return result

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
        result = WeeklyReportResponse(
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
        await self._save_generation(
            session,
            user_id=current_user.id,
            project_id=project_id,
            generation_type=AIGenerationType.WEEKLY_REPORT,
            request_data={
                "start_date": period_start.isoformat(),
                "end_date": period_end.isoformat(),
            },
            response_data=result.model_dump(mode="json"),
        )
        return result

    async def get_ai_history(
        self,
        session: AsyncSession,
        current_user: User,
        project_id: UUID,
    ) -> AIHistoryResponse:
        await self.tools.require_project_access(session, current_user, project_id)
        latest = await ai_generations.list_latest_by_type(
            session,
            project_id,
            current_user.id,
        )

        risk_generation = latest.get(AIGenerationType.RISK_ANALYSIS)
        task_generation = latest.get(AIGenerationType.TASK_SUGGESTIONS)
        weekly_generation = latest.get(AIGenerationType.WEEKLY_REPORT)

        return AIHistoryResponse(
            risk_analysis=(
                RiskAnalysisResponse.model_validate(risk_generation.response_data)
                if risk_generation is not None
                else None
            ),
            task_suggestions=(
                TaskSuggestionResponse.model_validate(task_generation.response_data)
                if task_generation is not None
                else None
            ),
            weekly_report=(
                WeeklyReportResponse.model_validate(weekly_generation.response_data)
                if weekly_generation is not None
                else None
            ),
        )

    async def _save_generation(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        project_id: UUID,
        generation_type: AIGenerationType,
        request_data: dict[str, Any],
        response_data: dict[str, Any],
    ) -> None:
        try:
            generation = AIGeneration(
                project_id=project_id,
                user_id=user_id,
                type=generation_type,
                request_data=request_data,
                response_data=response_data,
            )
            ai_generations.add(session, generation)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception(
                "Failed to persist AI generation type=%s",
                generation_type.value,
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
