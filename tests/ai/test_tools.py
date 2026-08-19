from __future__ import annotations

import pytest

from silly_teamwork.ai.tools import AIToolLayer
from silly_teamwork.services.exceptions import ProjectNotFoundError

pytestmark = pytest.mark.asyncio


async def test_tool_layer_builds_project_snapshot(ai_context) -> None:
    tool_layer = AIToolLayer()
    async with ai_context.session_factory() as session:
        snapshot = await tool_layer.get_project_snapshot(
            session,
            ai_context.member,
            ai_context.project.id,
            include_files=True,
        )

    assert snapshot.summary.project_name == "AI Course Project"
    assert snapshot.summary.member_count == 2
    assert snapshot.summary.total_tasks == 2
    assert snapshot.summary.open_tasks == 2
    assert len(snapshot.tasks) == 2
    assert len(snapshot.workloads) == 2
    assert len(snapshot.files) == 1

    member_workload = next(
        workload
        for workload in snapshot.workloads
        if workload.user_id == ai_context.member.id
    )
    assert member_workload.open_collaborative_tasks == 1
    assert member_workload.open_personal_tasks == 1
    assert member_workload.total_open_tasks == 2


async def test_tool_layer_rejects_outsider(ai_context) -> None:
    tool_layer = AIToolLayer()
    async with ai_context.session_factory() as session:
        with pytest.raises(ProjectNotFoundError):
            await tool_layer.get_project_snapshot(
                session,
                ai_context.outsider,
                ai_context.project.id,
            )
