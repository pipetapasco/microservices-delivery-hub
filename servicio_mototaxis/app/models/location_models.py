import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LocationData(BaseModel):
    """
    Modelo para los datos de ubicación enviados por el conductor.
    """

    latitude: float = Field(..., example=10.46314, description="Latitud del conductor")
    longitude: float = Field(..., example=-73.25322, description="Longitud del conductor")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp de la actualización de ubicación (UTC)",
    )
    accuracy: float | None = Field(
        None, example=5.0, description="Precisión de la ubicación en metros (opcional)"
    )
    speed: float | None = Field(None, example=45.5, description="Velocidad en km/h (opcional)")


class DriverLocation(BaseModel):
    """
    Modelo para representar la ubicación de un conductor almacenada o devuelta.
    """

    id_conductor: uuid.UUID
    latitude: float
    longitude: float
    last_updated: datetime

    model_config = ConfigDict(from_attributes=True)
