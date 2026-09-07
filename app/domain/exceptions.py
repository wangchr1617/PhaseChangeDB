"""PhaseChangeDB 领域异常类定义。"""

from __future__ import annotations


class WorkflowDomainError(Exception):
    """领域错误基类。"""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class DomainValidationError(WorkflowDomainError):
    def __init__(self, message: str):
        super().__init__(message, status_code=400)


class DomainConflictError(WorkflowDomainError):
    def __init__(self, message: str):
        super().__init__(message, status_code=409)


class EntityNotFoundError(WorkflowDomainError):
    def __init__(self, message: str):
        super().__init__(message, status_code=404)


class PreconditionFailedError(WorkflowDomainError):
    def __init__(self, message: str):
        super().__init__(message, status_code=412)


class ServiceUnavailableError(WorkflowDomainError):
    def __init__(self, message: str):
        super().__init__(message, status_code=503)


class UnauthorizedError(WorkflowDomainError):
    def __init__(self, message: str):
        super().__init__(message, status_code=401)
