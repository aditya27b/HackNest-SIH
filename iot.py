from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class IoTDevice(Base):
    """
    IoT devices registered to farms (simplified model).
    Stores minimal essential information for management.
    """
    __tablename__ = "iot_devices"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id", ondelete="CASCADE"), nullable=False)
    
    # Essential Identification
    device_id = Column(String(100), unique=True, nullable=False, index=True)  # Hardware ID
    
    # Status and Connectivity
    is_online = Column(Boolean, default=True)
    last_seen = Column(DateTime(timezone=True))
    mqtt_topic = Column(String(200), unique=True) # Topic this device publishes to
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    farm = relationship("Farm", back_populates="devices")
    readings = relationship("SensorReading", back_populates="device", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<IoTDevice {self.device_id}>"


class SensorReading(Base):
    """
    Time-series sensor data with fixed, required metrics.
    """
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("iot_devices.id", ondelete="CASCADE"), nullable=True)
    
    # Essential time field
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Specific Sensor Data (Fixed Fields)
    feed_rate = Column(Float, nullable=True)     # Rate or current level
    water_intake = Column(Float, nullable=True)  # Rate or current level
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    avg_weight = Column(Float, nullable=True)
    ammonia_level = Column(Float, nullable=True)
    lux_level = Column(Float, nullable=True)

    # Relationships
    device = relationship("IoTDevice", back_populates="readings")

    def __repr__(self):
        return f"<SensorReading device_id={self.device_id} at {self.timestamp}>"