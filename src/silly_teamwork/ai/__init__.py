"""AI assistant infrastructure for the Silly Teamwork agent features."""

from silly_teamwork.ai.llm import (
    AIConfigurationError,
    AIProviderError,
    AIResponseError,
    LLMProvider,
    MiMoProvider,
    MockProvider,
    create_llm_provider,
)
from silly_teamwork.ai.schemas import (
    AIFileUpdate,
    AIMemberWorkload,
    AIProjectSnapshot,
    AIProjectSummary,
    AITaskInfo,
    RiskAnalysisResponse,
    RiskLevel,
    TaskSuggestion,
    TaskSuggestionRequest,
    TaskSuggestionResponse,
    WeeklyReportRequest,
    WeeklyReportResponse,
)
from silly_teamwork.ai.service import AIAssistantService, get_ai_assistant_service
from silly_teamwork.ai.tools import AIToolLayer, get_ai_tool_layer

__all__ = [
    "AIConfigurationError",
    "AIFileUpdate",
    "AIMemberWorkload",
    "AIProjectSnapshot",
    "AIProjectSummary",
    "AIProviderError",
    "AIResponseError",
    "AIAssistantService",
    "AITaskInfo",
    "AIToolLayer",
    "LLMProvider",
    "MiMoProvider",
    "MockProvider",
    "RiskAnalysisResponse",
    "RiskLevel",
    "TaskSuggestion",
    "TaskSuggestionRequest",
    "TaskSuggestionResponse",
    "WeeklyReportRequest",
    "WeeklyReportResponse",
    "create_llm_provider",
    "get_ai_assistant_service",
    "get_ai_tool_layer",
]
