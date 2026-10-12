from fastapi import APIRouter
router = APIRouter()

@router.get("/")
async def list_materials():
    return [
        {"id": "Z21000", "name": "Z 21000 (MI 09)", "type": "EMU", "v_max_kmh": 140, "p_max_kw": 5200, "system": "AC25kV"},
        {"id": "Z2M", "name": "Z 2M (Diesel-Electric)", "type": "DMU", "v_max_kmh": 160, "p_max_kw": 1860, "system": "diesel"},
        {"id": "E1400", "name": "E1400 (Alstom Prima)", "type": "Locomotive", "v_max_kmh": 220, "p_max_kw": 5500, "system": "AC25kV"},
        {"id": "Al_Boraq", "name": "Al Boraq (TGV M)", "type": "TGV", "v_max_kmh": 320, "p_max_kw": 9280, "system": "AC25kV"},
    ]
