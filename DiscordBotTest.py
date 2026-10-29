import asyncio
import os
import random
import time
from typing import cast
from aiohttp import web
import discord
from discord.ext import commands
from dotenv import load_dotenv
import mysql.connector

load_dotenv()


# --- DUMMY WEB SERVER TO SATISFY RENDER FREE TIER ---
async def handle_ping(request):
    return web.Response(text="Bot is alive!")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()

    # Render assigns a PORT dynamically via environment variable
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server running on port {port}")


# --- ENVIRONMENT & DATABASE CONFIGURATION ---
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_USER: str = os.getenv("DB_USER", "root")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
DB_NAME: str = os.getenv("DB_NAME", "defaultdb")
DB_PORT: int = int(os.getenv("DB_PORT", 3306))

# Database connection object (initialized in main)
db = None
cursor = None

ROLE_REPWARDS: dict[int, int] = {1: 1565183458060537887}

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


def add_xp(user_id: int) -> int | None:
    """Add XP to a user and check for level up."""
    current_time: float = time.time()

    cursor.execute(
        "SELECT xp, level, last_message FROM user_info WHERE user_id = %s", (user_id,)
    )
    result = cast(tuple[int, int, float] | None, cursor.fetchone())

    if result is None:
        cursor.execute(
            "INSERT INTO user_info (user_id, xp, level, last_message) VALUES (%s, %s, %s, %s)",
            (user_id, 0, 0, current_time),
        )
        db.commit()
        xp, level, last_message = 0, 0, current_time
    else:
        xp, level, last_message = result

        if current_time - last_message < 10:
            return None

    gained_xp: int = random.randint(10, 20)
    new_xp: int = xp + gained_xp
    needed_xp: int = 100 * (level**2)

    leveled_up: bool = False
    if new_xp >= needed_xp:
        level += 1
        leveled_up = True

    cursor.execute(
        "UPDATE user_info SET xp = %s, level = %s, last_message = %s "
        + "WHERE user_id = %s",
        (new_xp, level, current_time, user_id),
    )
    db.commit()

    if leveled_up:
        return level
    return None


@bot.event
async def on_message(message: discord.Message) -> None:
    """Handle incoming messages and award XP to users."""
    if message.author == bot.user or not message.guild:
        return

    new_level: int | None = add_xp(message.author.id)

    if new_level is not None:
        await message.channel.send(
            f"Congratulations {message.author.mention}, you've leveled up to level {new_level}!"
        )

        if new_level in ROLE_REPWARDS:
            role_id: int = ROLE_REPWARDS[new_level]
            role: discord.Role | None = message.guild.get_role(role_id)
            if role and isinstance(message.author, discord.Member):
                await message.author.add_roles(role)
                await message.channel.send(
                    f"{message.author.mention} has been awarded the role {role.name} for reaching level {new_level}!"
                )
    await bot.process_commands(message)


@bot.command()
async def rank(
    ctx: commands.Context[commands.Bot], member: discord.Member | None = None
) -> None:
    """Display the rank (level and XP) of a user."""
    target: discord.Member | discord.User = member or ctx.author

    cursor.execute("SELECT xp, level FROM user_info WHERE user_id = %s", (target.id,))
    result = cast(tuple[int, int] | None, cursor.fetchone())

    if result is None:
        await ctx.send(
            f"{target.display_name} either doesn't exist or hasn't earned any XP yet."
        )
        return

    xp, level = result
    needed_xp: int = 100 * (level**2)

    embed_colour: discord.Color = (
        target.color if target.color.value != 0 else discord.Color.from_rgb(0, 0, 0)
    )

    embed = discord.Embed(title=f"{target.display_name}'s Rank", color=embed_colour)
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Level", value=str(level), inline=True)
    embed.add_field(name="XP", value=f"{xp}/{needed_xp}", inline=True)

    await ctx.send(embed=embed)


@bot.command()
async def leaderboard(ctx: commands.Context[commands.Bot]) -> None:
    """Display the top 10 users on the leaderboard."""
    cursor.execute(
        "SELECT user_id, xp, level FROM user_info ORDER BY level DESC, xp DESC LIMIT 10"
    )
    results = cast(list[tuple[int, int, int]] | None, cursor.fetchall())

    if not results:
        await ctx.send("No data recorded yet.")
        return

    embed = discord.Embed(title="Leaderboard", color=discord.Color.gold())

    description = ""
    for rank_num, (user_id, xp, level) in enumerate(results, start=1):
        user = await bot.fetch_user(user_id)
        description += f"{rank_num}. <@{user.id}> - **Level: {level}**, XP: {xp}\n"

    embed.description = description
    await ctx.send(embed=embed)


@bot.event
async def on_ready():
    print("Logged in as", bot.user)


async def main():
    global db, cursor

    # 1. Start the web server immediately for Render health checks
    asyncio.create_task(start_web_server())

    # 2. Connect to MySQL database using the correct port
    print(f"Connecting to database {DB_HOST}:{DB_PORT}...")
    db = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    )
    cursor = db.cursor()
    print("Database connected successfully!")

    # 3. Start Discord bot
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is missing!")
    await bot.start(BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
