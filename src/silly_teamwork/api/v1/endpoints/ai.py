from __future__ import annotations

from typing import NoReturn
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from silly_teamwork.ai.llm import AIProviderError
from silly_teamwork.ai.schemas import (
    AIHistoryResponse,
    RiskAnalysisResponse,
    TaskSuggestionRequest,
    TaskSuggestionResponse,
    WeeklyReportRequest,
    WeeklyReportResponse,
)
from silly_teamwork.api.dependencies import (
    AIAssistantServiceDep,
    CurrentUser,
    DbSession,
)
from silly_teamwork.services.exceptions import ProjectNotFoundError

router = APIRouter()


def _raise_ai_http_error(error: Exception) -> NoReturn:
    if isinstance(error, ProjectNotFoundError):
        # The AI endpoint follows the requested 403 semantics for users without
        # project access. The underlying authorization is still CollaborationAccessService.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
    if isinstance(error, AIProviderError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service temporarily unavailable",
        ) from error
    raise error


@router.post(
    "/{project_id}/ai/risk-analysis",
    response_model=RiskAnalysisResponse,
    summary="Analyze project risk with AI",
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Project access required"},
        502: {"description": "AI service error"},
    },
)
async def analyze_project_risk(
    project_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    ai_service: AIAssistantServiceDep,
) -> RiskAnalysisResponse:
    try:
        return await ai_service.analyze_project_risk(
            session,
            current_user,
            project_id,
        )
    except Exception as error:
        _raise_ai_http_error(error)


@router.post(
    "/{project_id}/ai/task-suggestions",
    response_model=TaskSuggestionResponse,
    summary="Generate AI task suggestions",
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Project access required"},
        422: {"description": "Validation error"},
        502: {"description": "AI service error"},
    },
)
async def suggest_tasks(
    project_id: UUID,
    payload: TaskSuggestionRequest,
    session: DbSession,
    current_user: CurrentUser,
    ai_service: AIAssistantServiceDep,
) -> TaskSuggestionResponse:
    try:
        return await ai_service.suggest_tasks(
            session,
            current_user,
            project_id,
            instruction=payload.instruction,
            count=payload.count,
        )
    except Exception as error:
        _raise_ai_http_error(error)


@router.post(
    "/{project_id}/ai/weekly-report",
    response_model=WeeklyReportResponse,
    summary="Generate AI weekly report",
    responses={
        400: {"description": "Invalid date range"},
        401: {"description": "Authentication required"},
        403: {"description": "Project access required"},
        422: {"description": "Validation error"},
        502: {"description": "AI service error"},
    },
)
async def generate_weekly_report(
    project_id: UUID,
    payload: WeeklyReportRequest,
    session: DbSession,
    current_user: CurrentUser,
    ai_service: AIAssistantServiceDep,
) -> WeeklyReportResponse:
    try:
        return await ai_service.generate_weekly_report(
            session,
            current_user,
            project_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except Exception as error:
        _raise_ai_http_error(error)


@router.get(
    "/{project_id}/ai/history",
    response_model=AIHistoryResponse,
    summary="Get the current user's latest AI generation results for a project",
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Project access required"},
    },
)
async def get_ai_history(
    project_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    ai_service: AIAssistantServiceDep,
) -> AIHistoryResponse:
    try:
        return await ai_service.get_ai_history(
            session,
            current_user,
            project_id,
        )
    except Exception as error:
        _raise_ai_http_error(error)
