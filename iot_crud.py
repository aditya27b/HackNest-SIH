"""
CRUD Operations for IoT Devices and Sensor Readings
====================================================
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, update
from typing import Optional, List, Tuple, Dict
from datetime import UTC, datetime, timedelta

from app.models.iot import IoTDevice, SensorReading
from app.schemas.iot import IoTDeviceCreate, IoTDeviceUpdate, SensorReadingCreate


# ============ IOT DEVICE CRUD ============

async def get_device_by_id(db: AsyncSession, device_id: int) -> Optional[IoTDevice]:
    """Get device by ID"""
    result = await db.execute(select(IoTDevice).where(IoTDevice.id == device_id))
    return result.scalar_one_or_none()


async def get_device_by_device_id(db: AsyncSession, device_id_str: str) -> Optional[IoTDevice]:
    """Get device by device_id string"""
    result = await db.execute(select(IoTDevice).where(IoTDevice.device_id == device_id_str))
    return result.scalar_one_or_none()


async def get_devices_by_farm(db: AsyncSession, farm_id: int, skip: int = 0, limit: int = 100) -> Tuple[List[IoTDevice], int]:
    """Get all devices for a farm"""
    count_result = await db.execute(select(func.count(IoTDevice.id)).where(IoTDevice.farm_id == farm_id))
    total = count_result.scalar()
    
    result = await db.execute(
        select(IoTDevice).where(IoTDevice.farm_id == farm_id)
        .order_by(IoTDevice.created_at.desc()).offset(skip).limit(limit)
    )
    devices = result.scalars().all()
    return devices, total


async def get_all_devices(db: AsyncSession, online_only: bool = False, skip: int = 0, limit: int = 100) -> Tuple[List[IoTDevice], int]:
    """Get all devices"""
    query = select(IoTDevice)
    count_query = select(func.count(IoTDevice.id))
    
    if online_only:
        query = query.where(IoTDevice.is_online == True)
        count_query = count_query.where(IoTDevice.is_online == True)
    
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    query = query.order_by(IoTDevice.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    devices = result.scalars().all()
    return devices, total


async def create_device(db: AsyncSession, device_in: IoTDeviceCreate) -> IoTDevice:
    """Create new device"""
    mqtt_topic = device_in.mqtt_topic or f"farm/{device_in.farm_id}/sensors"
    
    db_device = IoTDevice(
        farm_id=device_in.farm_id,
        device_id=device_in.device_id,
        mqtt_topic=mqtt_topic,
        is_online=True,
        last_seen=datetime.now(UTC),
        created_at=datetime.now(UTC)
    )
    
    db.add(db_device)
    await db.flush()
    await db.refresh(db_device)
    return db_device


async def update_device(db: AsyncSession, device_id: int, device_in: IoTDeviceUpdate) -> Optional[IoTDevice]:
    """Update device"""
    db_device = await get_device_by_id(db, device_id)
    if not db_device:
        return None
    
    update_data = device_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_device, field, value)
    
    await db.flush()
    await db.refresh(db_device)
    return db_device


async def update_device_status(db: AsyncSession, device_id: int, is_online: bool) -> Optional[IoTDevice]:
    """Update device status"""
    result = await db.execute(
        update(IoTDevice).where(IoTDevice.id == device_id)
        .values(is_online=is_online, last_seen=datetime.utcnow())
        .returning(IoTDevice)
    )
    return result.scalar_one_or_none()


async def delete_device(db: AsyncSession, device_id: int) -> bool:
    """Delete device"""
    db_device = await get_device_by_id(db, device_id)
    if not db_device:
        return False
    await db.delete(db_device)
    return True


# ============ SENSOR READING CRUD ============

async def create_sensor_reading(db: AsyncSession, reading_in: SensorReadingCreate) -> SensorReading:
    """Create sensor reading"""
    db_reading = SensorReading(
        device_id=reading_in.device_id,
        timestamp=datetime.now(UTC),
        feed_rate=reading_in.feed_rate,
        water_intake=reading_in.water_intake,
        temperature=reading_in.temperature,
        humidity=reading_in.humidity,
        avg_weight=reading_in.avg_weight
        ,ammonia_level=reading_in.ammonia_level
        ,lux_level=reading_in.lux_level
    )
    
    db.add(db_reading)
    await db.flush()
    await db.refresh(db_reading)
    
    await update_device_status(db, reading_in.device_id, is_online=True)
    return db_reading


async def get_latest_reading(db: AsyncSession, device_id: int) -> Optional[SensorReading]:
    """Get latest reading"""
    result = await db.execute(
        select(SensorReading).where(SensorReading.device_id == device_id)
        .order_by(desc(SensorReading.timestamp)).limit(1)
    )
    return result.scalar_one_or_none()


async def get_readings_by_device(
    db: AsyncSession, device_id: int, hours_back: Optional[int] = None, limit: int = 100
) -> List[SensorReading]:
    """Get readings for device"""
    query = select(SensorReading).where(SensorReading.device_id == device_id)
    
    if hours_back is not None:
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        query = query.where(SensorReading.timestamp >= cutoff_time)
    
    query = query.order_by(desc(SensorReading.timestamp)).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def get_readings_by_farm(
    db: AsyncSession, farm_id: int, hours_back: Optional[int] = None, limit: int = 100
) -> List[SensorReading]:
    """Get all readings for farm"""
    devices_result = await db.execute(select(IoTDevice.id).where(IoTDevice.farm_id == farm_id))
    device_ids = [d[0] for d in devices_result.all()]
    
    if not device_ids:
        return []
    
    query = select(SensorReading).where(SensorReading.device_id.in_(device_ids))
    
    if hours_back is not None:
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        query = query.where(SensorReading.timestamp >= cutoff_time)
    
    query = query.order_by(desc(SensorReading.timestamp)).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def get_reading_stats(db: AsyncSession, device_id: int, hours_back: int = 24) -> Dict:
    """Get reading statistics"""
    cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
    
    result = await db.execute(
        select(
            func.count(SensorReading.id).label('count'),
            func.avg(SensorReading.temperature).label('avg_temp'),
            func.min(SensorReading.temperature).label('min_temp'),
            func.max(SensorReading.temperature).label('max_temp'),
            func.avg(SensorReading.humidity).label('avg_humidity'),
            func.avg(SensorReading.feed_rate).label('avg_feed'),
            func.avg(SensorReading.water_intake).label('avg_water'),
            func.avg(SensorReading.avg_weight).label('avg_weight'),
            func.avg(SensorReading.ammonia_level).label('avg_ammonia'),
            func.avg(SensorReading.lux_level).label('avg_lux')
        ).where(and_(SensorReading.device_id == device_id, SensorReading.timestamp >= cutoff_time))
    )
    
    row = result.one()
    return {
        "readings_count": row.count,
        "avg_temperature": float(row.avg_temp) if row.avg_temp else None,
        "min_temperature": float(row.min_temp) if row.min_temp else None,
        "max_temperature": float(row.max_temp) if row.max_temp else None,
        "avg_humidity": float(row.avg_humidity) if row.avg_humidity else None,
        "avg_feed_rate": float(row.avg_feed) if row.avg_feed else None,
        "avg_water_intake": float(row.avg_water) if row.avg_water else None,
        "avg_weight": float(row.avg_weight) if row.avg_weight else None,
        "avg_ammonia_level": float(row.avg_ammonia) if row.avg_ammonia else None,
        "avg_lux_level": float(row.avg_lux) if row.avg_lux else None,
        "hours_back": hours_back
    }


async def mark_offline_devices(db: AsyncSession, timeout_minutes: int = 30) -> int:
    """Mark devices offline if haven't reported"""
    cutoff_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)
    result = await db.execute(
        update(IoTDevice).where(and_(IoTDevice.is_online == True, IoTDevice.last_seen < cutoff_time))
        .values(is_online=False)
    )
    return result.rowcount
