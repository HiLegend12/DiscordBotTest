import asyncio
import os

import discord
from aiohttp import web
from discord.ext import commands

from config import BOT_TOKEN, MY_GUILD

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

EXTENSIONS: tuple[str, ...] = ("cogs.general", "cogs.admin", "cogs.xp", "cogs.mining", "cogs.shop")


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


@bot.event
async def on_ready() -> None:
    print("Logged in as", bot.user)
    try:
        # Sync to a specific server instantly
        bot.tree.copy_global_to(guild=MY_GUILD)
        synced = await bot.tree.sync(guild=MY_GUILD)
        print(f"Synced {len(synced)} command(s) to test server.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


async def main() -> None:
    # Start the web server in the background
    asyncio.create_task(start_web_server())

    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is missing!")

    # Load each Cog file.
    for extension in EXTENSIONS:
        await bot.load_extension(extension)
        print(f"Loaded {extension}")

    # Start the Discord bot
    retry_delay = 600  # start with 10 minutes
    while True:
        try:
            await bot.start(BOT_TOKEN)
            break
        except discord.HTTPException as e:
            if e.status == 429:
                print(f"Rate limited by Cloudflare. Retrying in {retry_delay}s...")
                await bot.close()  # closes the leftover aiohttp connector
                await asyncio.sleep(retry_delay)
                bot.clear()  # lets the bot log in again
                retry_delay = min(retry_delay * 2, 3600)
            else:
                raise


if __name__ == "__main__":
    asyncio.run(main())
