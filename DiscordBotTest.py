import asyncio
import os
import random
import time
from typing import cast
from aiohttp import web
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import mysql.connector

load_dotenv()


# --- DUMMY WEB SERVER TO SATISFY RENDER FREE TIER ---
async def handle_ping(request):
    if bot.is_ready():
        return web.Response(text="Bot is alive and connected!")
    return web.Response(
        text="Web server up, but bot is NOT connected to Discord", status=503
    )


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


db: mysql.connector.MySQLConnection | None = None

ROLE_REPWARDS: dict[int, int] = {1: 1565183458060537887}
MY_GUILD = discord.Object(id=1564821894081941534)

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


def get_cursor():
    """Ping the DB (reconnecting if needed) and return a fresh cursor."""
    assert db is not None, "Database not connected"
    db.ping(reconnect=True, attempts=3, delay=1)
    return db.cursor()


def add_xp(user_id: int) -> int | None:
    """Add XP to a user and check for level up."""
    cursor = get_cursor()
    try:
        current_time: float = time.time()

        cursor.execute(
            "SELECT xp, level, last_message FROM user_info WHERE user_id = %s",
            (user_id,),
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
        
        # Replace the manual math with your new helper function
        level, leveled_up = calculate_new_level(new_xp, level)

        cursor.execute(
            "UPDATE user_info SET xp = %s, level = %s, last_message = %s "
            "WHERE user_id = %s",
            (new_xp, level, current_time, user_id),
        )
        db.commit()

        return level if leveled_up else None
    finally:
        cursor.close()


@bot.event
async def on_message(message: discord.Message) -> None:
    """Handle incoming messages and award XP to users."""
    print(f"on_message fired: {message.author} said {message.content!r}")
    if message.author.bot or not message.guild:
        return

    # Commands and bot pings don't earn XP
    ctx = await bot.get_context(message)
    is_command = ctx.valid or message.content.startswith("!")
    is_bot_ping = bot.user is not None and bot.user in message.mentions

    # Award XP if it's a regular message
    if not is_command and not is_bot_ping:
        new_level: int | None = add_xp(message.author.id)

        # If the user leveled up, send a congratulatory message and check for role rewards
        if new_level is not None:
            await message.channel.send(
                f"Congratulations {message.author.mention}, you've leveled up to level {new_level}!"
            )

            # Check for role rewards
            if new_level in ROLE_REPWARDS:
                role_id: int = ROLE_REPWARDS[new_level]
                role: discord.Role | None = message.guild.get_role(role_id)
                if role and isinstance(message.author, discord.Member):
                    try:
                        await message.author.add_roles(role)
                        await message.channel.send(
                            f"{message.author.mention} has been awarded the role {role.name} for reaching level {new_level}!"
                        )
                    except discord.Forbidden:
                        print(
                            f"Can't assign {role.name}: move the bot's role above it."
                        )

    await bot.process_commands(message)


@bot.hybrid_command(
    name="rank", description="Display the rank (level and XP) of a user."
)
async def rank(
    ctx: commands.Context[commands.Bot], member: discord.Member | None = None
) -> None:
    """Display the rank (level and XP) of a user."""
    target: discord.Member | discord.User = member or ctx.author
    cursor = get_cursor()
    try:
        cursor.execute(
            "SELECT xp, level FROM user_info WHERE user_id = %s", (target.id,)
        )
        result = cast(tuple[int, int] | None, cursor.fetchone())
    finally:
        cursor.close()

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


@bot.hybrid_command(
    name="leaderboard",
    description="Display the top 10 users on the leaderboard.",
    aliases=["lb"],
)
async def leaderboard(ctx: commands.Context[commands.Bot]) -> None:
    """Display the top 10 users on the leaderboard."""
    cursor = get_cursor()
    try:
        cursor.execute(
            "SELECT user_id, xp, level FROM user_info ORDER BY level DESC, xp DESC LIMIT 10"
        )
        results = cast(list[tuple[int, int, int]] | None, cursor.fetchall())
    finally:
        cursor.close()
    if not results:
        await ctx.send("No data recorded yet.")
        return

    embed = discord.Embed(title="Leaderboard", color=discord.Color.gold())

    description = ""
    for rank_num, (user_id, xp, level) in enumerate(results, start=1):
        description += f"{rank_num}. <@{user_id}> - **Level: {level}**, XP: {xp}\n"

    embed.description = description
    await ctx.send(embed=embed)


@bot.hybrid_command(name="delay", description="Check the bot's latency.")
async def delay(ctx: commands.Context[commands.Bot]) -> None:
    """Check the bot's latency."""
    latency_ms: float = bot.latency * 1000
    await ctx.send(f"Latency is {latency_ms:.2f} ms.")


@bot.hybrid_command(name="daily", description="Claim your daily XP reward.")
@commands.cooldown(1, 86400, commands.BucketType.user)
async def daily(ctx: commands.Context[commands.Bot]) -> None:
    user_id: int = ctx.author.id
    daily_reward: int = random.randint(100, 175)
    current_time: float = time.time()

    cursor = get_cursor()
    try:
        cursor.execute("SELECT xp, level FROM user_info WHERE user_id = %s", (user_id,))
        result = cast(tuple[int, int] | None, cursor.fetchone())

        if result is None:
            cursor.execute(
                "INSERT INTO user_info (user_id, xp, level, last_message) VALUES (%s, %s, %s, %s)",
                (user_id, daily_reward, 1, current_time) 
            )
            db.commit()
            await ctx.send(f"Welcome {ctx.author.mention}! You claimed your first daily reward of **{daily_reward} XP** and reached **Level 1**!")
            return

        xp, level = result
        new_xp: int = xp + daily_reward
        level, leveled_up = calculate_new_level(new_xp, level)

        cursor.execute(
            "UPDATE user_info SET xp = %s, level = %s, last_message = %s WHERE user_id = %s",
            (new_xp, level, current_time, user_id)
        )
        db.commit()
        await ctx.send(f"Daily reward claimed! You received **{daily_reward} XP**.")

    finally:
        cursor.close()
        
@daily.error
async def daily_error(ctx: commands.Context[commands.Bot], error: commands.CommandError) -> None:
    if isinstance(error, commands.CommandOnCooldown):
        remaining_time: float = error.retry_after
        hours, remainder = divmod(remaining_time, 3600)
        minutes, seconds = divmod(remainder, 60)
        await ctx.send(
            f"Daily reward is on cooldown. Please try again in {int(hours)}h {int(minutes)}m {int(seconds)}s."
        )
    else:
        await ctx.send("An error occurred while trying to claim your daily reward.")


@bot.event
async def on_ready():
    print("Logged in as", bot.user)
    try:
        # Sync to a specific server instantly
        bot.tree.copy_global_to(guild=MY_GUILD)
        synced = await bot.tree.sync(guild=MY_GUILD)
        print(f"Synced {len(synced)} command(s) to test server.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


async def main():
    global db

    # Start the web server in the background
    asyncio.create_task(start_web_server())

    # Connect to the database
    print(f"Connecting to database {DB_HOST}:{DB_PORT}...")
    db = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    )
    print("Database connected successfully!")

    # Start the Discord bot with retry logic for rate limiting
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is missing!")

    delay = 600  # start with 10 minutes
    while True:
        try:
            await bot.start(BOT_TOKEN)
            break
        except discord.HTTPException as e:
            if e.status == 429:
                print(f"Rate limited by Cloudflare. Retrying in {delay}s...")
                await bot.close()  # closes the leftover aiohttp connector
                await asyncio.sleep(delay)
                bot.clear()  # lets the bot log in again
                delay = min(delay * 2, 3600)
            else:
                raise

def calculate_new_level(xp: int, current_level: int) -> tuple[int, bool]:
    """Calculate if the current XP pushes the user to one or more new levels."""
    new_level: int = current_level
    leveled_up: bool = False
    
    # Using a while loop catches massive XP bursts that span multiple levels
    while xp >= 100 * (new_level ** 2):
        new_level += 1
        leveled_up = True
        
    return new_level, leveled_up


if __name__ == "__main__":
    asyncio.run(main())
