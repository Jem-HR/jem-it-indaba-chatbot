"""Phone catalog for the game."""

from typing import List
from app.models import Phone


PHONE_CATALOG: List[Phone] = [
    Phone(
        name="Samsung Galaxy S24 Ultra",
        price=24999,
        description="256GB, Titanium Gray, S Pen included"
    ),
    Phone(
        name="iPhone 15 Pro Max",
        price=25999,
        description="256GB, Natural Titanium, A17 Pro chip"
    ),
    Phone(
        name="Google Pixel 8 Pro",
        price=18999,
        description="128GB, Obsidian, AI-powered camera"
    ),
    Phone(
        name="OnePlus 12",
        price=15999,
        description="256GB, Flowy Emerald, 120Hz display"
    ),
    Phone(
        name="Xiaomi 14 Ultra",
        price=16999,
        description="512GB, Black, Leica camera system"
    ),
    Phone(
        name="Huawei Pura 70 Ultra",
        price=17999,
        description="512GB, Black, XMAGE camera"
    ),
    Phone(
        name="Nothing Phone (2)",
        price=11999,
        description="256GB, White, Glyph Interface"
    ),
]


def get_phone_catalog_text() -> str:
    """Format the phone catalog as text for WhatsApp."""
    text = "*🎁 Prize Phone Catalog 🎁*\n\n"
    for i, phone in enumerate(PHONE_CATALOG, 1):
        text += f"{i}. *{phone.name}*\n"
        text += f"   💰 R{phone.price:,}\n"
        text += f"   📱 {phone.description}\n\n"
    return text
