"""
IoT Device & Sensor Management API
===================================
Handles IoT devices and sensor readings.

Endpoints:
Device Management:
- GET    /api/v1/iot/devices           - List all devices
- POST   /api/v1/iot/devices           - Register new device
- GET    /api/v1/iot/devices/{id}      - Get device details
- PUT    /api/v1/iot/devices/{id}      - Update device
- DELETE /api/v1/iot/devices/{id}      - Delete device

Farm Devices:
- GET    /api/v1/iot/farm/{farm_id}/devices  - Get farm's devices

Sensor Readings:
- POST   /api/v1/iot/readings          - Record sensor reading
- GET    /api/v1/iot/readings/{device_id} - Get device readings
- GET    /api/v1/iot/readings/{device_id}/latest - Get latest reading
- GET    /api/v1/iot/readings/{device_id}/stats  - Get reading statistics

Farm Readings:
- GET    /api/v1/iot/farm/{farm_id}/readings - Get farm's readings
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.schemas.iot import (
    IoTDeviceCreate,
    IoTDeviceUpdate,
    IoTDeviceResponse,
    IoTDeviceWithReadings,
    DeviceListResponse,
    SensorReadingCreate,
    SensorReadingResponse,
    SensorDataSummary
)
from app.crud import iot as iot_crud
from app.crud import farm as farm_crud

router = APIRouter(prefix="/iot", tags=["IoT & Sensors"])


# ============================================================================
# DEVICE MANAGEMENT
# ============================================================================

@router.get("/devices", response_model=DeviceListResponse)
async def list_devices(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    online_only: bool = Query(False, description="Show only online devices"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all IoT devices with their status.
    
    Query Parameters:
    - skip: Pagination offset
    - limit: Max results
    - online_only: If true, only show online devices
    
    Examples:
        GET /api/v1/iot/devices
        GET /api/v1/iot/devices?online_only=true
    """
    devices, total = await iot_crud.get_all_devices(
        db,
        online_only=online_only,
        skip=skip,
        limit=limit
    )
    
    # Get latest reading for each device
    devices_with_readings = []
    for device in devices:
        latest_reading = await iot_crud.get_latest_reading(db, device.id)
        
        devices_with_readings.append({
            **device.__dict__,
            "latest_reading": latest_reading,
            "readings_count": 0  # Could count if needed
        })
    
    # Count online/offline
    online_count = sum(1 for d in devices if d.is_online)
    offline_count = len(devices) - online_count
    
    return {
        "total": total,
        "devices": devices_with_readings,
        "skip": skip,
        "limit": limit,
        "online_count": online_count,
        "offline_count": offline_count
    }


@router.post("/devices", response_model=IoTDeviceResponse, status_code=status.HTTP_201_CREATED)
async def register_device(
    device_in: IoTDeviceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Register a new IoT device.
    
    Request Body:
        {
            "farm_id": 1,
            "device_id": "IOT-0001-M",
            "mqtt_topic": "farm/1/sensors"
        }
    
    Verifies that user owns the farm before registering device.
    """
    # Verify user owns the farm
    farm = await farm_crud.get_farm_by_id(
        db,
        farm_id=device_in.farm_id,
        owner_id=current_user.id
    )
    
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farm not found or access denied"
        )
    
    # Check if device_id already exists
    existing_device = await iot_crud.get_device_by_device_id(
        db,
        device_in.device_id
    )
    
    if existing_device:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Device with ID {device_in.device_id} already exists"
        )
    
    # Create device
    device = await iot_crud.create_device(db, device_in)
    await db.commit()
    
    return device


@router.get("/devices/{device_id}", response_model=IoTDeviceWithReadings)
async def get_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get device details with latest reading.
    
    Path Parameters:
    - device_id: Device's database ID
    """
    device = await iot_crud.get_device_by_id(db, device_id)
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Verify user owns the farm this device belongs to
    farm = await farm_crud.get_farm_by_id(
        db,
        farm_id=device.farm_id,
        owner_id=current_user.id
    )
    
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get latest reading
    latest_reading = await iot_crud.get_latest_reading(db, device_id)
    
    return {
        **device.__dict__,
        "latest_reading": latest_reading,
        "readings_count": 0
    }


@router.put("/devices/{device_id}", response_model=IoTDeviceResponse)
async def update_device(
    device_id: int,
    device_in: IoTDeviceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update device settings.
    
    Can update:
    - is_online status
    - mqtt_topic
    """
    device = await iot_crud.get_device_by_id(db, device_id)
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Verify ownership
    farm = await farm_crud.get_farm_by_id(
        db,
        farm_id=device.farm_id,
        owner_id=current_user.id
    )
    
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Update device
    updated_device = await iot_crud.update_device(db, device_id, device_in)
    await db.commit()
    
    return updated_device


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete an IoT device.
    
    CASCADE will also delete all sensor readings for this device.
    """
    device = await iot_crud.get_device_by_id(db, device_id)
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Verify ownership
    farm = await farm_crud.get_farm_by_id(
        db,
        farm_id=device.farm_id,
        owner_id=current_user.id
    )
    
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Delete device
    await iot_crud.delete_device(db, device_id)
    await db.commit()
    
    return None


# ============================================================================
# FARM DEVICES
# ============================================================================

@router.get("/farm/{farm_id}/devices", response_model=List[IoTDeviceWithReadings])
async def get_farm_devices(
    farm_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all devices for a specific farm.
    
    Path Parameters:
    - farm_id: Farm's database ID
    
    Example:
        GET /api/v1/iot/farm/1/devices
    """
    # Verify farm ownership
    farm = await farm_crud.get_farm_by_id(
        db,
        farm_id=farm_id,
        owner_id=current_user.id
    )
    
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farm not found"
        )
    
    # Get devices
    devices, _ = await iot_crud.get_devices_by_farm(db, farm_id)
    
    # Add latest reading for each
    devices_with_readings = []
    for device in devices:
        latest_reading = await iot_crud.get_latest_reading(db, device.id)
        
        devices_with_readings.append({
            **device.__dict__,
            "latest_reading": latest_reading,
            "readings_count": 0
        })
    
    return devices_with_readings


# ============================================================================
# SENSOR READINGS
# ============================================================================

@router.post("/readings", response_model=SensorReadingResponse, status_code=status.HTTP_201_CREATED)
async def record_sensor_reading(
    reading_in: SensorReadingCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Record a new sensor reading.
    
    This endpoint can be called by:
    - IoT devices directly (if they have API access)
    - MQTT subscriber service
    - Manual data entry
    
    Request Body:
        {
            "device_id": 1,
            "feed_rate": 80.0,
            "water_intake": 200.0,
            "temperature": 28.5,
            "humidity": 60.0,
            "avg_weight": 8.0
        }
    
    NOTE: No authentication required for IoT devices.
    You might want to add API key authentication later.
    """
    # Verify device exists
    device = await iot_crud.get_device_by_id(db, reading_in.device_id)
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Create reading
    reading = await iot_crud.create_sensor_reading(db, reading_in)
    await db.commit()
    
    return reading


@router.get("/readings/{device_id}", response_model=List[SensorReadingResponse])
async def get_device_readings(
    device_id: int,
    hours_back: Optional[int] = Query(24, ge=1, le=720, description="Hours to look back"),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get sensor readings for a device.
    
    Path Parameters:
    - device_id: Device's database ID
    
    Query Parameters:
    - hours_back: Get readings from last N hours (default: 24)
    - limit: Max results (default: 100)
    
    Examples:
        GET /api/v1/iot/readings/1
        GET /api/v1/iot/readings/1?hours_back=6
        GET /api/v1/iot/readings/1?hours_back=168&limit=500  (7 days)
    """
    # Verify device exists and user has access
    device = await iot_crud.get_device_by_id(db, device_id)
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    farm = await farm_crud.get_farm_by_id(
        db,
        farm_id=device.farm_id,
        owner_id=current_user.id
    )
    
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get readings
    readings = await iot_crud.get_readings_by_device(
        db,
        device_id=device_id,
        hours_back=hours_back,
        limit=limit
    )
    
    return readings


@router.get("/readings/{device_id}/latest", response_model=SensorReadingResponse)
async def get_latest_reading(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get latest sensor reading for a device.
    
    Path Parameters:
    - device_id: Device's database ID
    
    Example:
        GET /api/v1/iot/readings/1/latest
    """
    # Verify device and access
    device = await iot_crud.get_device_by_id(db, device_id)
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    farm = await farm_crud.get_farm_by_id(
        db,
        farm_id=device.farm_id,
        owner_id=current_user.id
    )
    
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get latest reading
    reading = await iot_crud.get_latest_reading(db, device_id)
    
    if not reading:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No readings found for this device"
        )
    
    return reading


@router.get("/readings/{device_id}/stats", response_model=SensorDataSummary)
async def get_reading_statistics(
    device_id: int,
    hours_back: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get statistics for sensor readings.
    
    Returns average, min, max for all sensor values.
    
    Path Parameters:
    - device_id: Device's database ID
    
    Query Parameters:
    - hours_back: Hours to analyze (default: 24)
    
    Examples:
        GET /api/v1/iot/readings/1/stats
        GET /api/v1/iot/readings/1/stats?hours_back=168  (7 days)
    
    Response:
        {
            "device_id": 1,
            "farm_id": 1,
            "readings_count": 96,
            "avg_temperature": 28.5,
            "min_temperature": 26.0,
            "max_temperature": 32.0,
            "avg_humidity": 60.0,
            ...
        }
    """
    # Verify device and access
    device = await iot_crud.get_device_by_id(db, device_id)
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    farm = await farm_crud.get_farm_by_id(
        db,
        farm_id=device.farm_id,
        owner_id=current_user.id
    )
    
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get statistics
    stats = await iot_crud.get_reading_stats(db, device_id, hours_back)
    
    # Get first and last reading timestamps
    readings = await iot_crud.get_readings_by_device(
        db, device_id, hours_back=hours_back, limit=1000
    )
    
    first_reading = readings[-1].timestamp if readings else None
    last_reading = readings[0].timestamp if readings else None
    
    return {
        "device_id": device_id,
        "farm_id": device.farm_id,
        "first_reading": first_reading,
        "last_reading": last_reading,
        **stats
    }


# ============================================================================
# FARM READINGS
# ============================================================================

@router.get("/farm/{farm_id}/readings", response_model=List[SensorReadingResponse])
async def get_farm_readings(
    farm_id: int,
    hours_back: int = Query(24, ge=1, le=720),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all sensor readings for a farm (from all devices).
    
    Path Parameters:
    - farm_id: Farm's database ID
    
    Query Parameters:
    - hours_back: Hours to look back (default: 24)
    - limit: Max results (default: 100)
    
    Example:
        GET /api/v1/iot/farm/1/readings
        GET /api/v1/iot/farm/1/readings?hours_back=6
    """
    # Verify farm ownership
    farm = await farm_crud.get_farm_by_id(
        db,
        farm_id=farm_id,
        owner_id=current_user.id
    )
    
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farm not found"
        )
    
    # Get readings
    readings = await iot_crud.get_readings_by_farm(
        db,
        farm_id=farm_id,
        hours_back=hours_back,
        limit=limit
    )
    
    return readings


# ============================================================================
# SYSTEM MAINTENANCE
# ============================================================================

@router.post("/maintenance/check-offline")
async def check_offline_devices_endpoint(
    timeout_minutes: int = Query(30, ge=5, le=1440),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Check for offline devices and mark them.
    
    Usually called by Celery task, but can be triggered manually.
    
    Query Parameters:
    - timeout_minutes: Mark offline after N minutes (default: 30)
    
    Example:
        POST /api/v1/iot/maintenance/check-offline
    """
    # Only admins should access this
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    marked_offline = await iot_crud.mark_offline_devices(db, timeout_minutes)
    await db.commit()
    
    return {
        "marked_offline": marked_offline,
        "message": f"Marked {marked_offline} devices as offline"
    }
