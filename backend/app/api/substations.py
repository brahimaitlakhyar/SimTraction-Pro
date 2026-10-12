from fastapi import APIRouter
router = APIRouter()

@router.get("/")
async def list_substations():
    return [
        {"id": "SST_AIN_SEBAA", "name": "SST Ain Sébaâ", "power_mva": 2 * 20, "type": "2x25kV", "position_km": 0},
        {"id": "SST_KENITRA", "name": "SST Kénitra", "power_mva": 2 * 20, "type": "2x25kV", "position_km": 140},
        {"id": "SST_SALE", "name": "SST Salé", "power_mva": 2 * 20, "type": "2x25kV", "position_km": 87},
    ]
