import os
import discord
from dotenv import load_dotenv
from typing import TypedDict

class Pickaxe(TypedDict):
    name: str
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


MINE_COOLDOWN = 3
ORES: dict[str, tuple[int, int, float]] = {
    "dirt": (1, 0, 0),
    "stone": (2, 1, 0.5),
    "coal": (5, 1, 1),
    "iron": (15, 2, 2),
    "gold": (50, 3, 3.5),
    "diamond": (200, 3, 5),
}
PICKAXES: dict[str, Pickaxe] = {
    "hand": {"name": "Bare Hands", "tier": 0, "price": 0, "center": 0.0, "spread": 1.0},
    "wooden": {
        "name": "Wooden Pickaxe",
        "tier": 1,
        "price": 50,
        "center": 0.7,
        "spread": 0.8,
    },
    "stone": {
        "name": "Stone Pickaxe",
        "tier": 2,
        "price": 250,
        "center": 1.3,
        "spread": 0.8,
    },
    "iron": {
        "name": "Iron Pickaxe",
        "tier": 3,
        "price": 1000,
        "center": 2.3,
        "spread": 1.0,
    },
    "diamond": {
        "name": "Diamond Pickaxe",
        "tier": 4,
        "price": 5000,
        "center": 3.5,
        "spread": 1.2,
    }
}
