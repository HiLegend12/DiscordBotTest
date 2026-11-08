import os
import discord
from dotenv import load_dotenv
from typing import TypedDict


class Pickaxe(TypedDict):
    name: str
    description: str
    tier: int
    price: int
    center: float
    spread: float


load_dotenv()

# Configuration variables
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_USER: str = os.getenv("DB_USER", "root")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
DB_NAME: str = os.getenv("DB_NAME", "defaultdb")
DB_PORT: int = int(os.getenv("DB_PORT", 3306))

DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

ROLE_REWARDS: dict[int, int] = {1: 1565183458060537887}
MY_GUILD = discord.Object(id=1564821894081941534)

FONT_PATH = os.path.join(os.path.dirname(__file__), "NotoSans-Regular.ttf")

DAILY_COOLDOWN: int = 86400
STREAK_WINDOW: int = 172800

MINING_XP_BASE: int = 50
MINE_COOLDOWN = 3
ORE_XP: dict[str, int] = {
    "dirt": 1,
    "stone": 2,
    "coal": 4,
    "copper": 6,
    "iron": 8,
    "gold": 15,
    "diamond": 40,
}
ORES: dict[str, tuple[int, int, float]] = {
    "dirt": (1, 0, 0),
    "stone": (2, 1, 0.5),
    "coal": (5, 1, 1),
    "copper": (8, 1, 1.5),
    "iron": (15, 2, 2),
    "gold": (50, 4, 3.5),
    "diamond": (200, 4, 5),
}
PICKAXES: dict[str, Pickaxe] = {
    "hand": {
        "name": "Bare Hands",
        "description": "Your Hands",
        "tier": 0,
        "price": 0,
        "center": 0.0,
        "spread": 1.0,
    },
    "wooden": {
        "name": "Wooden Pickaxe",
        "description": "A basic wooden pickaxe.",
        "tier": 1,
        "price": 50,
        "center": 0.7,
        "spread": 0.8,
    },
    "stone": {
        "name": "Stone Pickaxe",
        "description": "A sturdy stone pickaxe.",
        "tier": 2,
        "price": 250,
        "center": 1.3,
        "spread": 0.8,
    },
    "copper": {
        "name": "Copper Pickaxe",
        "description": "A shiny copper pickaxe.",
        "tier": 3,
        "price": 500,
        "center": 1.8,
        "spread": 0.9,
    },
    "iron": {
        "name": "Iron Pickaxe",
        "description": "A strong iron pickaxe.",
        "tier": 4,
        "price": 1000,
        "center": 2.3,
        "spread": 1.0,
    },
    "diamond": {
        "name": "Diamond Pickaxe",
        "description": "A rare diamond pickaxe.",
        "tier": 5,
        "price": 5000,
        "center": 3.5,
        "spread": 1.2,
    },
}

SMELTING: dict[str, tuple[str, int, int, int]] = {
    "copper": ("copper_bar", 3, 1, 40),
    "iron": ("iron_bar", 3, 1, 70),
    "gold": ("gold_bar", 3, 1, 200),
}
SELL_PRICES: dict[str, int] = {
    **{name: data[0] for name, data in ORES.items()},
    **{bar: price for bar, _, _, price in SMELTING.values()},
}

SMELT_SECONDS_PER_BAR: int = 30
FORGE_COUNT_COSTS: list[int] = [500, 2000, 8000]
FORGE_SIZE_COSTS: list[int] = [300, 1000, 4000]
