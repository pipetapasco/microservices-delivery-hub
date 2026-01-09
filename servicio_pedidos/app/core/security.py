# servicio_pedidos/app/core/security.py
"""
Security layer for API authentication.
This is a stub/skeleton that can be extended with actual token validation.
"""

import jwt
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings
from .logging_config import get_logger

logger = get_logger(__name__)

# HTTP Bearer token security scheme
bearer_scheme = HTTPBearer(auto_error=False)


async def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> dict:
    """
    Verify the bearer token from the Authorization header.

    This is a STUB implementation. In production, replace with actual JWT validation:
    - Decode and verify JWT signature
    - Check expiration
    - Validate issuer/audience
    - Extract user claims

    Args:
        credentials: The HTTP Bearer credentials

    Returns:
        dict: User information extracted from token

    Raises:
        HTTPException: If token is missing or invalid
    """
    if credentials is None:
        logger.warning("Missing authentication credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        # Decode and verify the JWT token
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        user_id = payload.get("sub")
        if user_id is None:
            logger.warning("Token missing 'sub' claim")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token claims",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Return user info from token
        return {"user_id": user_id, "roles": payload.get("roles", []), "token": token}

    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as e:
        logger.warning(f"Invalid token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def verify_token_optional(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> dict | None:
    """
    Optional token verification - returns None if no token provided.
    Useful for endpoints that work differently for authenticated vs anonymous users.
    """
    if credentials is None:
        return None

    return await verify_token(credentials)
