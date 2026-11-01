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
from mysql.connector.abstracts import (
    MySQLConnectionAbstract,
    MySQLCursorAbstract
)
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import unicodedata

load_dotenv()


# --- ENVIRONMENT & DATABASE CONFIGURATION ---
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_USER: str = os.getenv("DB_USER", "root")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
DB_NAME: str = os.getenv("DB_NAME", "defaultdb")
DB_PORT: int = int(os.getenv("DB_PORT", 3306))


db = cast(
    MySQLConnectionAbstract,
    mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    ),
)

# Define globals
ROLE_REPWARDS: dict[int, int] = {1: 1565183458060537887}
MY_GUILD = discord.Object(id=1564821894081941534)
FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "NotoSans-Regular.ttf")
DAILY_COOLDOWN: int = 86400  # 24 hours: minimum time between claims
STREAK_WINDOW: int = 172800

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# --- DUMMY WEB SERVER TO SATISFY RENDER FREE TIER ---
async def handle_ping(request: web.Request) -> web.Response:
    if bot.is_ready():
        return web.Response(text="Bot is alive and connected!")
    return web.Response(
        text="Web server up, but bot is NOT connected to Discord", status=503
    )


async def start_web_server() -> None:
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()

    # Render assigns a PORT dynamically via environment variable
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server running on port {port}")


# ----------- USER COMMANDS -----------
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
            if isinstance(message.author, discord.Member):
                for role in await grant_level_roles(message.author, new_level):
                    await message.channel.send(
                        f"{message.author.mention} has been awarded the role {role.name} for reaching level {new_level}!"
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

    # Optional: Send a "thinking" state since image generation takes a split second
    await ctx.defer()

    cursor = get_cursor()
    try:
        cursor.execute(
            "SELECT xp, level FROM user_info WHERE user_id = %s", (target.id,)
        )
        result = cast(tuple[int, int] | None, cursor.fetchone())
    finally:
        cursor.close()

    # If the user has no data, default to 0 XP and level 0
    if result is None:
        xp = 0
        level = 0
    else:
        xp, level = result

    # Find username colour, defaulting to white if no color is set
    user_colour: tuple[int, int, int] = (
        target.color.to_rgb() if target.color.value != 0 else (255, 255, 255)
    )

    # Fetch the avatar as raw bytes directly from Discord
    avatar_bytes = await target.display_avatar.with_size(256).with_format("png").read()

    # Generate the rank card image in a separate thread to avoid blocking the event loop
    print(f"Raw username: {ascii(target.display_name)}")
    image_buffer = await asyncio.to_thread(
        generate_rank_card, target.display_name, avatar_bytes, xp, level, user_colour
    )

    # Convert the buffer into a Discord File object and send it
    file = discord.File(fp=image_buffer, filename="rank_card.png")
    await ctx.send(file=file)


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
async def daily(ctx: commands.Context[commands.Bot]) -> None:
    user_id: int = ctx.author.id
    now: float = time.time()

    cursor = get_cursor()
    try:
        ensure_user_exists(cursor, user_id)
        cursor.execute(
            "SELECT xp, level, last_daily, daily_streak FROM user_info WHERE user_id = %s",
            (user_id,),
        )
        xp, level, last_daily, streak = cast(
            tuple[int, int, float, int], cursor.fetchone()
        )

        # Still on cooldown? Tell them how long is left and stop.
        elapsed = now - last_daily
        if elapsed < DAILY_COOLDOWN:
            hours, remainder = divmod(DAILY_COOLDOWN - elapsed, 3600)
            minutes, seconds = divmod(remainder, 60)
            await ctx.send(
                f"Daily reward is on cooldown. Please try again in "
                f"{int(hours)}h {int(minutes)}m {int(seconds)}s."
            )
            return

        # Claimed within 48h of the last claim keeps the streak; otherwise restart at 1
        is_first_claim = last_daily == 0
        streak = streak + 1 if elapsed < STREAK_WINDOW else 1

        streak_bonus = min(streak, 10) * 5
        daily_reward = random.randint(100, 175) + streak_bonus

        new_xp = xp + daily_reward
        new_level, leveled_up = calculate_new_level(new_xp, level)

        cursor.execute(
            "UPDATE user_info SET xp = %s, level = %s, last_daily = %s, daily_streak = %s "
            "WHERE user_id = %s",
            (new_xp, new_level, now, streak, user_id),
        )
        get_db().commit()

        if leveled_up and isinstance(ctx.author, discord.Member):
            await grant_level_roles(ctx.author, new_level)

        if is_first_claim:
            await ctx.send(
                f"Welcome {ctx.author.mention}! You claimed your first daily reward of **{daily_reward} XP**!"
            )
        else:
            await ctx.send(
                f"Daily reward claimed! You received **{daily_reward} XP** "
                f"(streak: **{streak}**, bonus: +{streak_bonus} XP)."
            )
    finally:
        cursor.close()


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
    db = cast(
        MySQLConnectionAbstract,
        mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
        )
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


# ----------- ADMIN COMMANDS -----------
@bot.hybrid_command(name="givexp", description="[ADMIN] Give XP to a user.")
@commands.has_permissions(administrator=True)
async def givexp(
    ctx: commands.Context[commands.Bot], member: discord.Member, xp_amount: int
) -> None:
    """[ADMIN] Give XP to a user."""
    # Check if the XP amount is positive
    if xp_amount <= 0:
        await ctx.send("Please provide a positive amount of XP to give.")
        return

    cursor = get_cursor()
    try:
        current_time: float = time.time()

        # Check if the user exists in the database
        cursor.execute(
            "SELECT xp, level FROM user_info WHERE user_id = %s", (member.id,)
        )
        result = cast(tuple[int, int] | None, cursor.fetchone())

        # If the user doesn't exist, insert them into the database with the given XP
        if result is None:
            ensure_user_exists(cursor, member.id)
            new_xp: int = xp_amount
            new_level, _ = calculate_new_level(new_xp, 0)
            cursor.execute(
                "UPDATE user_info SET xp = %s, level = %s, last_message = %s WHERE user_id = %s",
                (new_xp, new_level, current_time, member.id),
            )

        # If the user exists, update their XP and level
        else:
            xp, level = result
            new_xp: int = xp + xp_amount
            new_level, _ = calculate_new_level(new_xp, level)
            cursor.execute(
                "UPDATE user_info SET xp = %s, level = %s WHERE user_id = %s",
                (new_xp, new_level, member.id),
            )

        # Commit the changes to the database
        db.commit()
        await ctx.send(
            f"Successfully gave **{xp_amount} XP** to {member.mention}. They are now **Level {new_level}** with **{new_xp} XP**."
        )

    finally:
        cursor.close()


@bot.hybrid_command(name="setlevel", description="[ADMIN] Set a user's level.")
@commands.has_permissions(administrator=True)
async def setlevel(
    ctx: commands.Context[commands.Bot], member: discord.Member, new_level: int
) -> None:
    """[ADMIN] Set a user's level."""
    # Check if the new level is negative
    if new_level < 0:
        await ctx.send("Level cannot be negative.")
        return

    cursor = get_cursor()
    try:
        current_time: float = time.time()

        base_xp: int = 100 * ((new_level - 1) ** 2)
        cursor.execute("SELECT xp FROM user_info WHERE user_id = %s", (member.id,))
        result = cursor.fetchone()

        # If the user doesn't exist, insert them into the database with the new level and corresponding XP
        if result is None:
            ensure_user_exists(cursor, member.id)
            cursor.execute(
                "UPDATE user_info SET xp = %s, level = %s, last_message = %s WHERE user_id = %s",
                (base_xp, new_level, current_time, member.id),
            )
        # If the user exists, update their level and XP
        else:
            cursor.execute(
                "UPDATE user_info SET xp = %s, level = %s WHERE user_id = %s",
                (base_xp, new_level, member.id),
            )

        # Commit the changes to the database
        db.commit()
        await ctx.send(
            f"Successfully set {member.mention} to **Level {new_level}** ({base_xp} XP)."
        )

    finally:
        cursor.close()


@givexp.error
@setlevel.error
async def admin_command_error(
    ctx: commands.Context[commands.Bot], error: commands.CommandError
) -> None:
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You do not have permission to use this command.")


# ----------- HELPER FUNCTIONS -----------
async def grant_level_roles(member: discord.Member, level: int) -> list[discord.Role]:
    """Give the member every reward role they've qualified for. Returns the roles newly granted."""
    granted: list[discord.Role] = []

    for required_level, role_id in ROLE_REPWARDS.items():
        if level < required_level:
            continue  # not high enough for this reward yet

        role = member.guild.get_role(role_id)
        if role is None or role in member.roles:
            continue  # role was deleted, or they already have it

        try:
            await member.add_roles(role)
            granted.append(role)
        except discord.Forbidden:
            print(f"Can't assign {role.name}: move the bot's role above it.")

    return granted


def ensure_user_exists(cursor: MySQLCursorAbstract, user_id: int) -> None:
    """Create a row for this user if one doesn't exist yet. Does nothing otherwise."""
    cursor.execute(
        "INSERT IGNORE INTO user_info (user_id, xp, level, last_message) "
        "VALUES (%s, 0, 0, 0)",
        (user_id,),
    )


def calculate_new_level(xp: int, current_level: int) -> tuple[int, bool]:
    """Calculate if the current XP pushes the user to one or more new levels."""
    new_level: int = current_level
    leveled_up: bool = False

    # Using a while loop catches massive XP bursts that span multiple levels
    while xp >= 100 * (new_level**2):
        new_level += 1
        leveled_up = True

    return new_level, leveled_up


def generate_rank_card(
    username: str,
    avatar_bytes: bytes,
    xp: int,
    level: int,
    user_colour: tuple[int, int, int],
) -> BytesIO:
    # Generate a rank card image for the user.
    background = Image.new(
        "RGB", (800, 250), color=(43, 45, 49)
    )  # Standard Discord dark theme color
    draw = ImageDraw.Draw(background)

    # Load fonts, with a fallback to default if the specified font is not found
    try:
        font_large = ImageFont.truetype(FONT_PATH, 40)
        font_small = ImageFont.truetype(FONT_PATH, 25)
    except OSError:
        # Fallback just in case the file gets moved
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Normalize the username to ensure consistent rendering
    clean_username = username.replace("\u0454", "e")
    clean_username = unicodedata.normalize("NFKC", clean_username)

    # Calculate XP and level details for the progress bar
    current_level_xp = 100 * ((level - 1) ** 2) if level > 0 else 0
    needed_xp = 100 * (level**2)

    # Calculate how much XP the user has into the current level and the total XP needed for the next level
    xp_into_level = xp - current_level_xp
    xp_range = needed_xp - current_level_xp

    # Progress bar percentage (0.0 to 1.0)
    percentage = xp_into_level / xp_range if xp_range > 0 else 0
    percentage = max(0.0, min(percentage, 1.0))

    # Draw the avatar
    avatar = Image.open(BytesIO(avatar_bytes)).convert("RGBA")
    avatar = avatar.resize((150, 150))

    # Create a circular mask for the avatar to make it round
    mask = Image.new("L", (150, 150), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, 150, 150), fill=255)
    background.paste(avatar, (40, 50), mask)

    # Draw the username and XP/level text
    draw.text((230, 50), clean_username, font=font_large, fill=(255, 255, 255))
    xp_text = (
        f"Level {level}  |  {xp:,} Total XP  |  {xp_into_level:,} / {xp_range:,} XP"
    )
    draw.text((230, 115), xp_text, font=font_small, fill=(185, 187, 190))

    # Draw the progress bar
    bar_x, bar_y = 230, 165
    bar_width, bar_height = 500, 30
    fill_width = int(bar_width * percentage)
    draw.rounded_rectangle(
        [bar_x, bar_y, bar_x + bar_width, bar_y + bar_height],
        radius=15,
        fill=(30, 31, 34),
    )
    if fill_width > 15:
        draw.rounded_rectangle(
            [bar_x, bar_y, bar_x + fill_width, bar_y + bar_height],
            radius=15,
            fill=user_colour,
        )

    # Save the image to a BytesIO buffer and return it
    buffer = BytesIO()
    background.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer


def get_db() -> MySQLConnectionAbstract:
    """Return the live DB connection, or fail loudly if it isn't connected yet."""
    assert db is not None, "Database not connected"
    return db


def get_cursor() -> MySQLCursorAbstract:
    """Ping the DB (reconnecting if needed) and return a fresh cursor."""
    conn = get_db()
    conn.ping(reconnect=True, attempts=3, delay=1)
    return conn.cursor()


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
            ensure_user_exists(cursor, user_id)
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


if __name__ == "__main__":
    asyncio.run(main())
