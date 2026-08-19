class AuthenticationError(Exception):
    """Base class for expected authentication use-case failures."""


class InvalidInvitationError(AuthenticationError):
    pass


class RegistrationConflictError(AuthenticationError):
    pass


class InvalidCredentialsError(AuthenticationError):
    pass


class TeamError(Exception):
    """Base class for expected Team use-case failures."""


class TeamNotFoundError(TeamError):
    pass


class TeamAccessDeniedError(TeamError):
    pass


class AlreadyTeamMemberError(TeamError):
    pass


class AdminTargetNotFoundError(Exception):
    pass


class CollaborationError(Exception):
    """Base class for Project and Task collaboration failures."""


class ProjectNotFoundError(CollaborationError):
    pass


class ProjectAccessDeniedError(CollaborationError):
    pass


class ProjectMemberConflictError(CollaborationError):
    pass


class ProjectMemberNotFoundError(CollaborationError):
    pass


class TaskNotFoundError(CollaborationError):
    pass


class TaskAccessDeniedError(CollaborationError):
    pass


class TaskMemberConflictError(CollaborationError):
    pass


class TaskMemberNotFoundError(CollaborationError):
    pass


class InvalidStatusTransitionError(CollaborationError):
    pass


class InvalidDeadlineError(CollaborationError):
    pass


class PersonalTaskValidationError(CollaborationError):
    pass


class TaskAssignmentNotFoundError(CollaborationError):
    pass


class TaskAssignmentAccessDeniedError(CollaborationError):
    pass


class FileServiceError(Exception):
    """Base class for expected file use-case failures."""


class FileNotFoundError(FileServiceError):
    pass


class FileAccessDeniedError(FileServiceError):
    pass


class FileTooLargeError(FileServiceError):
    pass


class FileStorageError(FileServiceError):
    pass


class NotificationError(Exception):
    """Base class for expected notification use-case failures."""


class NotificationNotFoundError(NotificationError):
    pass


class InvalidNotificationError(NotificationError):
    pass


class UserProfileError(Exception):
    """Base class for expected account profile failures."""


class InvalidCurrentPasswordError(UserProfileError):
    pass


class PasswordReuseError(UserProfileError):
    pass


class AvatarNotFoundError(UserProfileError):
    pass


class InvalidAvatarError(UserProfileError):
    pass


class AvatarTooLargeError(UserProfileError):
    pass
