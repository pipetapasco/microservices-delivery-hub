import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.logger import get_logger
from ...db.session import get_db
from ...models.driver_models import Driver, DriverCreateRequest, DriverInDB
from ...models.token_models import Token
from ...services import auth_service as current_auth_service

logger = get_logger("auth_endpoint")

router = APIRouter(
    tags=["Authentication"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login/access-token")


async def get_current_driver_from_token(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> DriverInDB:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY_MOTOTAXIS, algorithms=[settings.JWT_ALGORITHM]
        )
        id_conductor_str: str = payload.get("sub")
        if id_conductor_str is None:
            logger.warning("id_conductor (sub) no encontrado en el payload del token")
            raise credentials_exception

        try:
            id_conductor_uuid = uuid.UUID(id_conductor_str)
        except ValueError:
            logger.warning(f"id_conductor '{id_conductor_str}' en el token no es un UUID válido")
            raise credentials_exception

        conductor = await current_auth_service.get_driver_by_id_service(
            db=db, driver_id=id_conductor_uuid
        )

        if conductor is None:
            logger.warning(
                f"Conductor con ID '{id_conductor_uuid}' del token no encontrado en la DB"
            )
            raise credentials_exception

        return conductor

    except JWTError as e:
        logger.warning(f"Error decodificando JWT: {e}")
        raise credentials_exception


@router.post("/register", response_model=Driver)
async def register_driver(driver_in: DriverCreateRequest, db: Session = Depends(get_db)):
    conductor_registrado_db_obj = await current_auth_service.registrar_nuevo_conductor(
        db=db, driver_data=driver_in
    )

    if not conductor_registrado_db_obj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo registrar el conductor. El email o ID podrían ya estar en uso, o datos inválidos.",
        )
    return Driver.model_validate(conductor_registrado_db_obj)


@router.post("/login/access-token", response_model=Token)
async def login_for_access_token(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
):
    conductor_db_obj = await current_auth_service.autenticar_conductor(
        db=db, email=form_data.username, password=form_data.password
    )
    if not conductor_db_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    token_data_to_encode = {"sub": str(conductor_db_obj.id_conductor)}

    access_token = current_auth_service.create_access_token(
        data=token_data_to_encode, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}
