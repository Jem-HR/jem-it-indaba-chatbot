"""Phone catalog for the game."""

from typing import List
from app.models import Phone


PHONE_CATALOG: List[Phone] = [
    Phone(
        name="Huawei Nova Y73 128GB",
        price=0,  # Prize - no price displayed
        description="✨ 8GB RAM | 128GB storage | 6620mAh battery | 6.67\" 90Hz display | Dual SIM"
    ),
    Phone(
        name="Samsung Galaxy A16 LTE 128GB",
        price=0,
        description="✨ 4GB RAM | 128GB storage | 5000mAh battery | 6.7\" Super AMOLED 90Hz | Dual SIM"
    ),
    Phone(
        name="Oppo A40 4GB 128GB",
        price=0,
        description="✨ 4GB RAM (expandable to 8GB) | 128GB storage | 5100mAh battery | 45W fast charging | Military-grade shock resistance | IP54 rated | Dual SIM"
    ),
]


def get_phone_catalog_text() -> str:
    """Format the phone catalog as text for WhatsApp."""
    text = "*🏆 THE PRIZES*\n\n"
    for i, phone in enumerate(PHONE_CATALOG, 1):
        text += f"{i}. *{phone.name}*\n"
        text += f"{phone.description}\n\n"
    return text
