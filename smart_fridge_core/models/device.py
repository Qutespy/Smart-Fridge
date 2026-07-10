from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from core.database import Base


class DeviceModel(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    serial_number = Column(String(100), unique=True, nullable=False)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    last_seen = Column(DateTime, nullable=True)

    family = relationship("FamilyModel", back_populates="devices")
    sensor_data = relationship("SensorDataModel", back_populates="device")


class SensorDataModel(Base):
    __tablename__ = "sensor_data"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    temperature = Column(Float, nullable=False)
    humidity = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    device = relationship("DeviceModel", back_populates="sensor_data")
