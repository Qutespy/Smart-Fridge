from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from core.database import get_db
from models.device import DeviceModel, SensorDataModel
from api.v1.auth import get_current_user

router = APIRouter()


class DeviceCreate(BaseModel):
    serial_number: str


class SensorDataCreate(BaseModel):
    temperature: float
    humidity: float


@router.post("/", status_code=201)
def register_device(
    data: DeviceCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    family_id = current_user.family_id or 0
    device = DeviceModel(
        serial_number=data.serial_number,
        family_id=family_id,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return {"id": device.id, "serial_number": device.serial_number}


@router.get("/")
def get_devices(
    db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    family_id = current_user.family_id or 0
    devices = (
        db.query(DeviceModel).filter(DeviceModel.family_id == family_id).all()
    )
    return [
        {
            "id": d.id,
            "serial_number": d.serial_number,
            "is_active": d.is_active,
            "last_seen": str(d.last_seen) if d.last_seen else None,
        }
        for d in devices
    ]


@router.post("/{device_id}/sensor")
def submit_sensor_data(
    device_id: int,
    data: SensorDataCreate,
    db: Session = Depends(get_db),
):
    device = db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    sensor = SensorDataModel(
        device_id=device_id,
        temperature=data.temperature,
        humidity=data.humidity,
    )
    db.add(sensor)
    device.last_seen = datetime.utcnow()
    db.commit()
    return {"status": "recorded", "timestamp": str(sensor.timestamp)}
