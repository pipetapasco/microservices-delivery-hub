class AppError(Exception):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(AppError):
    pass


class ServiceError(AppError):
    pass


class ResourceNotFound(AppError):
    pass


class SecurityError(AppError):
    pass


class ExternalAPIError(AppError):
    pass


class FileUploadError(AppError):
    pass
