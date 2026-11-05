import random
import time
from typing import cast

import discord

from config import ROLE_REWARDS
from database import ensure_user_exists, get_pool


def calculate_new_level(
    xp: int, current_level: int, base: int = 100
) -> tuple[int, bool]:
    """Calculate if the current XP pushes the user to one or more new levels."""
    new_level: int = current_level
    leveled_up: bool = False

    while xp >= base * (new_level**2):
        new_level += 1
        leveled_up = True

    return new_level, leveled_up


async def grant_level_roles(member: discord.Member, level: int) -> list[discord.Role]:
    """Give the member every reward role they've qualified for. Returns the roles newly granted."""
    granted: list[discord.Role] = []

    for required_level, role_id in ROLE_REWARDS.items():
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


async def announce_level_up(
    destination: discord.abc.Messageable,
    member: discord.User | discord.Member,
    new_level: int,
) -> None:
    """Announce a level up and any reward roles."""
    await destination.send(
        f"Congratulations {member.mention}, you've leveled up to level {new_level}!"
    )
    if isinstance(member, discord.Member):
        for role in await grant_level_roles(member, new_level):
            await destination.send(
                f"{member.mention} has been awarded the role {role.name} for reaching level {new_level}!"
            )


async def add_xp(user_id: int) -> int | None:
    """Add XP to a user and check for level up."""
    async with get_pool().acquire() as conn:
        async with conn.cursor() as cursor:
            await ensure_user_exists(cursor, user_id)
            await cursor.execute(
                "SELECT xp, level, last_message FROM user_info WHERE user_id = %s",
                (user_id,),
            )
            xp, level, last_message = cast(
                tuple[int, int, float], await cursor.fetchone()
            )

            # Ignore messages sent within 10 seconds of the last XP gain
            current_time = time.time()
            if current_time - last_message < 10:
                return None

            new_xp = xp + random.randint(10, 20)
            new_level, leveled_up = calculate_new_level(new_xp, level)

            await cursor.execute(
                "UPDATE user_info SET xp = %s, level = %s, last_message = %s "
                "WHERE user_id = %s",
                (new_xp, new_level, current_time, user_id),
            )
            return new_level if leveled_up else None
