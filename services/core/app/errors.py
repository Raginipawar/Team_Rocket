from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

def err_response(status: int, code: str, message: str, details: dict = {}):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "details": details}})

class GHError(Exception):
    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

class NotFound(GHError): status_code=404; code="NOT_FOUND"
class Forbidden(GHError): status_code=403; code="FORBIDDEN"
class VersionConflict(GHError): status_code=409; code="VERSION_CONFLICT"
class RoomReserved(GHError): status_code=409; code="ROOM_RESERVED"
class ResourceUnavailable(GHError): status_code=409; code="RESOURCE_UNAVAILABLE"
class AlreadyTaken(GHError): status_code=409; code="ALREADY_TAKEN"
class InvalidTransition(GHError): status_code=409; code="INVALID_TRANSITION"
class IdempotencyMismatch(GHError): status_code=422; code="IDEMPOTENCY_MISMATCH"
class RateLimited(GHError): status_code=429; code="RATE_LIMITED"
class DependencyUnavailable(GHError): status_code=503; code="DEPENDENCY_UNAVAILABLE"

def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(GHError)
    async def gh_error_handler(request: Request, exc: GHError):
        return err_response(exc.status_code, exc.code, exc.message, exc.details)
    
    @app.exception_handler(Exception)
    async def general_error_handler(request: Request, exc: Exception):
        return err_response(500, "INTERNAL_ERROR", "An unexpected error occurred.")
