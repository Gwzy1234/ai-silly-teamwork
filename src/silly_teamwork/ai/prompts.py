from __future__ import annotations

from datetime import date

from silly_teamwork.ai.llm import ChatMessage
from silly_teamwork.ai.schemas import AIProjectSnapshot

_SYSTEM_PROMPT = (
    "你是一个大学课程团队协作助手。你只根据用户提供的数据做分析和规划，"
    "不访问数据库，不修改数据。所有输出必须是严格的 JSON。"
)


def build_risk_analysis_prompt(snapshot: AIProjectSnapshot) -> list[ChatMessage]:
    user_content = (
        "请分析以下项目的风险。返回 JSON，格式为：\n"
        '{"risk_level": "high|medium|low", "summary": "一句话总结", '
        '"reasons": ["原因1"], "suggestions": ["建议1"]}\n\n'
        f"项目数据：\n{snapshot.model_dump_json()}"
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def build_task_suggestion_prompt(
    snapshot: AIProjectSnapshot,
    instruction: str,
    count: int,
) -> list[ChatMessage]:
    user_content = (
        f"用户需求：{instruction}\n"
        f"请生成 {count} 条任务建议。返回 JSON，格式为：\n"
        '{"suggestions": [{"title": "任务名", "description": "描述", '
        '"priority": "low|medium|high|urgent", "starts_at": "ISO时间或null", '
        '"due_at": "ISO时间或null", "recommended_owner_user_id": "用户ID或null", '
        '"reason": "推荐原因"}]}\n\n'
        f"项目数据：\n{snapshot.model_dump_json()}"
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def build_weekly_report_prompt(
    snapshot: AIProjectSnapshot,
    start_date: date,
    end_date: date,
) -> list[ChatMessage]:
    user_content = (
        f"请生成项目周报，周期为 {start_date.isoformat()} 至 {end_date.isoformat()}。"
        "返回 JSON，格式为：\n"
        '{"summary": "本周总结", "highlights": ["亮点"], "risks": ["风险"], '
        '"suggestions": ["建议"]}\n\n'
        f"项目数据：\n{snapshot.model_dump_json()}"
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
