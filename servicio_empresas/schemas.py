from pydantic import BaseModel, EmailStr, Field, field_validator


class OpcionModificador(BaseModel):
    nombre_opcion: str = Field(..., min_length=1)
    precio_adicional: float = Field(..., ge=0)
    disponible_opcion: bool = True

    @field_validator("nombre_opcion")
    @classmethod
    def nombre_opcion_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("nombre_opcion no puede estar vacío")
        return v.strip()


class GrupoModificadores(BaseModel):
    nombre_grupo: str = Field(..., min_length=1)
    tipo_seleccion: str = Field(..., pattern=r"^(single|multiple)$")
    min_seleccion: int = Field(..., ge=0)
    max_seleccion: int = Field(..., ge=1)
    opciones: list[OpcionModificador] = Field(..., min_length=1)

    @field_validator("nombre_grupo")
    @classmethod
    def nombre_grupo_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("nombre_grupo no puede estar vacío")
        return v.strip()


class ItemMenu(BaseModel):
    nombre: str = Field(..., min_length=1)
    descripcion: str = Field(...)
    precio_base: float = Field(..., ge=0)
    moneda: str = Field(..., min_length=1, max_length=3)
    categoria_nombre: str = Field(..., min_length=1)
    disponible: bool = True
    grupos_modificadores: list[GrupoModificadores] | None = None
    id_externo_item: str | None = None
    imagen_url: str | None = None
    item_uuid: str | None = None

    @field_validator("nombre", "categoria_nombre")
    @classmethod
    def not_empty_string(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El campo no puede estar vacío")
        return v.strip()


class ItemMenuUpdate(BaseModel):
    nombre: str | None = None
    descripcion: str | None = None
    precio_base: float | None = Field(None, ge=0)
    moneda: str | None = Field(None, min_length=1, max_length=3)
    categoria_nombre: str | None = None
    disponible: bool | None = None
    grupos_modificadores: list[GrupoModificadores] | None = None
    id_externo_item: str | None = None
    imagen_url: str | None = None

    @field_validator("nombre", "categoria_nombre", mode="before")
    @classmethod
    def validate_optional_strings(cls, v):
        if v is not None and isinstance(v, str) and not v.strip():
            raise ValueError("El campo no puede estar vacío si se proporciona")
        return v.strip() if isinstance(v, str) and v else v


class EmpresaRegistro(BaseModel):
    id_empresa: str = Field(..., min_length=1, description="Company unique identifier")
    nombre_empresa: str = Field(..., min_length=1)
    email: EmailStr = Field(...)
    password: str = Field(..., min_length=6)

    @field_validator("id_empresa", "nombre_empresa", "password")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


class EmpresaLogin(BaseModel):
    email: EmailStr = Field(...)
    password: str = Field(..., min_length=1)

    @field_validator("email", "password")
    @classmethod
    def not_empty_login(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()
