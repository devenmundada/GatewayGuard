"""
Shared FastAPI dependencies.
"""
from fastapi import HTTPException, Request, status


def get_current_user_id(request: Request) -> int:
    """
    The authenticated user's id, as set by AuthMiddleware from a verified JWT.
    Raises 401 if the middleware did not authenticate this request.
    """
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id
