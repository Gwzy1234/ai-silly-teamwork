from fastapi import APIRouter

from silly_teamwork.api.v1.endpoints import (
    admin,
    ai,
    auth,
    deadlines,
    files,
    health,
    notifications,
    personal_tasks,
    projects,
    tasks,
    teams,
    users,
)

router = APIRouter()
router.include_router(health.router)
router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(users.router, prefix="/users", tags=["Users"])
router.include_router(admin.router, prefix="/admin", tags=["System Administration"])
router.include_router(teams.router, prefix="/teams", tags=["Teams"])
router.include_router(projects.team_router, prefix="/teams", tags=["Projects"])
router.include_router(projects.router, prefix="/projects", tags=["Projects"])
router.include_router(ai.router, prefix="/projects", tags=["AI"])
router.include_router(files.project_router, prefix="/projects", tags=["Files"])
router.include_router(tasks.project_router, prefix="/projects", tags=["Tasks"])
router.include_router(
    personal_tasks.project_router, prefix="/projects", tags=["Personal Tasks"]
)
# /tasks/my must be registered before the dynamic /tasks/{task_id} routes.
router.include_router(
    personal_tasks.my_tasks_router, prefix="/tasks", tags=["Personal Tasks"]
)
# Static deadline paths must be registered before the dynamic /tasks/{task_id} routes.
router.include_router(deadlines.router, prefix="/tasks", tags=["Deadlines"])
router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
router.include_router(files.task_router, prefix="/tasks", tags=["Files"])
router.include_router(files.router, prefix="/files", tags=["Files"])
router.include_router(
    personal_tasks.personal_task_router,
    prefix="/personal-tasks",
    tags=["Personal Tasks"],
)
router.include_router(
    personal_tasks.assignment_router,
    prefix="/task-assignments",
    tags=["Personal Tasks"],
)
router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
