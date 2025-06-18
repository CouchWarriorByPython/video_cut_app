from typing import Dict, List, Any

DRONE_TYPES: Dict[str, Any] = {
    "autel": {
        "name": "Autel",
        "images": [
            {"src": "autel_1.jpeg"},
            {"src": "autel_2.jpeg"}
        ]
    },
    "dji": {
        "name": "DJI",
        "images": [
            {"src": "dji_1.jpeg", "modification": "DJI Fly"},
            {"src": "dji_2.jpeg", "modification": "DJI Pilot"},
            {"src": "dji_3.jpeg", "modification": "DJI Pilot"}
        ]
    },
    "flyeye": {
        "name": "FlyEye",
        "images": [
            {"src": "flyeye_1.jpeg"},
            {"src": "flyeye_2.jpeg"}
        ]
    },
    "fpv": {
        "name": "FPV",
        "description": "В цю категорію входять FPV-камікадзе або (рідше) саморобні FPV-бомбери. Note: інколи відео може бути не тільки аналоговим, а і цифровим!",
        "images": [
            {"src": "fpv_1.png"},
            {"src": "fpv_2.png"}
        ]
    },
    "furia": {
        "name": "Furia",
        "images": [
            {"src": "furia_1.jpeg"},
            {"src": "furia_2.jpeg"}
        ]
    },
    "leleka": {
        "name": "Leleka",
        "images": [
            {"src": "leleka_1.jpeg"},
            {"src": "leleka_2.jpeg"}
        ]
    },
    "gor": {
        "name": "Gor",
        "images": [
            {"src": "gor.jpeg"}
        ]
    },
    "poseidon": {
        "name": "Poseidon",
        "images": [
            {"src": "poseidon.jpeg"}
        ]
    },
    "heidrun": {
        "name": "Heidrun",
        "images": [
            {"src": "heidrun.jpeg"}
        ]
    },
    "interceptor": {
        "name": "Interceptor",
        "images": [
            {"src": "interceptor_1.png"},
            {"src": "interceptor_2.png"}
        ]
    },
    "other_bomber": {
        "name": "Other Bomber",
        "description": "У дронів можуть бути інші довільні інтерфейси або може взагалі не бути OSD, але видно скид боєприпасу (і це не DJI/Autel).",
        "images": [
            {"src": "nemezis.jpeg", "modification": "Nemezis"},
            {"src": "vampire.jpeg", "modification": "Vampire"}
        ]
    },
    "other_recon": {
        "name": "Other Recon",
        "description": "У дронів можуть бути інші довільні інтерфейси.",
        "images": [
            {"src": "hermes.jpeg", "modification": "Hermes"},
            {"src": "shark.png", "modification": "Shark"}
        ]
    }
}

UAV_TYPES: List[Dict[str, str]] = [
    {"value": "", "label": "Оберіть тип дрона"},
    {"value": "autel", "label": "Autel"},
    {"value": "dji", "label": "DJI"},
    {"value": "flyeye", "label": "FlyEye"},
    {"value": "fpv", "label": "FPV"},
    {"value": "furia", "label": "Furia"},
    {"value": "leleka", "label": "Leleka"},
    {"value": "gor", "label": "Gor"},
    {"value": "poseidon", "label": "Poseidon"},
    {"value": "heidrun", "label": "Heidrun"},
    {"value": "interceptor", "label": "Interceptor"},
    {"value": "nemezis", "label": "Nemezis"},
    {"value": "vampire", "label": "Vampire"},
    {"value": "hermes", "label": "Hermes"},
    {"value": "shark", "label": "Shark"},
    {"value": "other_bomber", "label": "Other Bomber"},
    {"value": "other_recon", "label": "Other Recon"}
]

VIDEO_CONTENT_TYPES: List[Dict[str, str]] = [
    {"value": "", "label": "Оберіть тип контенту"},
    {"value": "recon", "label": "Recon"},
    {"value": "interception", "label": "Interception"},
    {"value": "bombing", "label": "Bombing"},
    {"value": "strike", "label": "Strike"},
    {"value": "panoramic", "label": "Panoramic"},
    {"value": "other", "label": "Other"}
]