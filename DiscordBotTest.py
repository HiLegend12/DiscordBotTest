# Code: MTU2NDgyMTAyMzQwMzI4NjU5MA.GX_Rg6.3-xWZYUO4Z-1tB6Va4K0GZWPhnoptwZqglqIMg

import discord
from discord.ext import commands
import time
import random
from typing import cast
import mysql.connector

# Database connection setup
db = mysql.connector.connect(
    host="localhost", user="root", password="Redpenguin12*", database="discord_bot_test"
)
cursor = db.cursor()

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


def add_xp(user_id: int) -> int | None:
    """Add XP to a user and check for level up."""
    # Get the current time
    current_time: float = time.time()

    # Fetch the user's current XP, level, and last message time from the database
    cursor.execute(
        "SELECT xp, level, last_message FROM user_info WHERE user_id = %s", (user_id,)
    )
    result = cast(tuple[int, int, float] | None, cursor.fetchone())

    # If the user is not found in the database, insert a new record with initial values
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
            return None  # User has sent a message within the last minute, no XP awarded

    # Award XP and check for level up
    gained_xp: int = random.randint(10, 20)
    new_xp: int = xp + gained_xp
    needed_xp: int = 100 * (level**2)

    leveled_up: bool = False
    if new_xp >= needed_xp:
        level += 1
        leveled_up = True

    # Save the new XP, level, and last message time to the database
    cursor.execute(
        "UPDATE user_info SET xp = %s, level = %s, last_message = %s "
        + "WHERE user_id = %s",
        (new_xp, level, current_time, user_id),
    )
    db.commit()

    if leveled_up:
        return level  # Return the new level if the user leveled up
    return None  # Return None if the user did not level up


@bot.event
async def on_message(message: discord.Message) -> None:
    """Handle incoming messages and award XP to users."""
    if message.author == bot.user or not message.guild:
        return  # Ignore messages from the bot itself or DMs
    
    # Award XP to the user and check for level up
    new_level: int | None = add_xp(message.author.id)
    
    # If the user leveled up, send a congratulatory message
    if new_level is not None:
        await message.channel.send(
            f"Congratulations {message.author.mention}, you've leveled up to level {new_level}!"
        )
    await bot.process_commands(message)

@bot.command()
async def rank(ctx: commands.Context[commands.Bot], member: discord.Member | None = None) -> None:
    """Display the rank (level and XP) of a user."""
    # Determine the target user (either the mentioned member or the command invoker)
    target: discord.Member | discord.User = member or ctx.author

    # Fetch the user's XP and level from the database
    cursor.execute("SELECT xp, level FROM user_info WHERE user_id = %s", (target.id,))
    result = cast(tuple[int, int] | None, cursor.fetchone())

    # If the user is not found in the database, inform the command invoker
    if result is None:
        await ctx.send(f"{target.display_name} either doesn't exist or hasn't earned any XP yet.")
        return

    # Unpack the result and calculate needed XP for the next level
    xp, level = result
    needed_xp: int = 100 * (level**2)  

    # Create an embed to display the user's rank information
    embed = discord.Embed(
        title=f"{target.display_name}'s Rank",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Level", value=str(level), inline=True)
    embed.add_field(name="XP", value=f"{xp}/{needed_xp}", inline=True)

    await ctx.send(embed=embed)

@bot.command()
async def leaderboard(ctx: commands.Context[commands.Bot]) -> None:
    """Display the top 10 users on the leaderboard."""
    # Fetch the top 10 users from the database, ordered by level and XP
    cursor.execute("SELECT user_id, xp, level FROM user_info ORDER BY level DESC, xp DESC LIMIT 10")
    results = cast(list[tuple[int, int, int]] | None, cursor.fetchall())
    
    # If there are no results, inform the user that no data has been recorded yet
    if not results:
        await ctx.send("No data recorded yet.")
        return
    
    # Create an embed for the leaderboard
    embed = discord.Embed(title="Leaderboard", color=discord.Color.gold())
    
    # Build the leaderboard description with user mentions and their ranks
    description = ""
    for rank, (user_id, xp, level) in enumerate(results, start=1):
        user = await bot.fetch_user(user_id)
        description += f"{rank}. <@{user.id}> - **Level: {level}**, XP: {xp}\n"
    
    # Set the description of the embed and send it to the channel
    embed.description = description
    await ctx.send(embed=embed)


@bot.event
async def on_ready():
    print("Logged in")


if __name__ == "__main__":
    bot.run("MTU2NDgyMTAyMzQwMzI4NjU5MA.GX_Rg6.3-xWZYUO4Z-1tB6Va4K0GZWPhnoptwZqglqIMg")
