from enum import StrEnum


class TeamRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class ProjectRole(StrEnum):
    OWNER = "owner"
    MEMBER = "member"


class TaskRole(StrEnum):
    OWNER = "owner"
    COLLABORATOR = "collaborator"
    REVIEWER = "reviewer"


class ProjectStatus(StrEnum):
    PLANNING = "planning"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskType(StrEnum):
    COLLABORATIVE = "collaborative"
    PERSONAL = "personal"


class AttachmentMode(StrEnum):
    SHARED = "shared"
    INDIVIDUAL = "individual"


class InvitationStatus(StrEnum):
    ACTIVE = "active"
    USED = "used"
    REVOKED = "revoked"
    EXPIRED = "expired"


class SystemAdminRole(StrEnum):
    SUPER_ADMIN = "super_admin"


class NotificationType(StrEnum):
    TASK_DUE_SOON = "task_due_soon"
    TASK_OVERDUE = "task_overdue"
    PROJECT_DUE_SOON = "project_due_soon"
    SYSTEM = "system"
    PROJECT_CREATED = "project_created"
    TASK_CREATED = "task_created"
    FILE_UPLOADED = "file_uploaded"


class NotificationScheduleStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    CANCELLED = "cancelled"
    FAILED = "failed"


class AIGenerationType(StrEnum):
    RISK_ANALYSIS = "risk_analysis"
    TASK_SUGGESTIONS = "task_suggestions"
    WEEKLY_REPORT = "weekly_report"
