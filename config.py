import os
import discord
from dotenv import load_dotenv

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
ORES: dict[str, tuple[int, int]] = {
    "dirt": (50, 1),
    "stone": (25, 2),
    "coal": (12, 5),
    "iron": (8, 15),
    "gold": (4, 50),
    "diamond": (1, 200),
}
