import random
import time
from typing import cast

import discord

from config import ROLE_REWARDS
from database import ensure_user_exists, get_cursor, get_db


def calculate_new_level(xp: int, current_level: int) -> tuple[int, bool]:
    """Calculate if the current XP pushes the user to one or more new levels."""
    # Initialize the new level to the current level and a flag to track if the user leveled up
    new_level: int = current_level
    leveled_up: bool = False

    # Keep increasing the level as long as the XP meets the requirement for the next level
    while xp >= 100 * (new_level**2):
        new_level += 1
        leveled_up = True

    return new_level, leveled_up


async def grant_level_roles(member: discord.Member, level: int) -> list[discord.Role]:
    """Give the member every reward role they've qualified for. Returns the roles newly granted."""
    # Initialize a list to keep track of newly granted roles
    granted: list[discord.Role] = []

    # Loop through the ROLE_REWARDS dictionary to check which roles the user qualifies for based on their level
    for required_level, role_id in ROLE_REWARDS.items():
        if level < required_level:
            continue  # not high enough for this reward yet

        role = member.guild.get_role(role_id)
        if role is None or role in member.roles:
            continue  # role was deleted, or they already have it

        try:
            # Assign the role to the member and add it to the granted list
            await member.add_roles(role)
            granted.append(role)
        except discord.Forbidden:
            # The bot doesn't have permission to assign this role
            print(f"Can't assign {role.name}: move the bot's role above it.")

    return granted


def add_xp(user_id: int) -> int | None:
    """Add XP to a user and check for level up."""
    cursor = get_cursor()
    try:
        # Ensure the user exists in the database and fetch their current XP, level, and last message timestamp
        ensure_user_exists(cursor, user_id)
        cursor.execute(
            "SELECT xp, level, last_message FROM user_info WHERE user_id = %s",
            (user_id,),
        )
        # Fetch the user's current XP, level, and last message timestamp from the database
        xp, level, last_message = cast(tuple[int, int, float], cursor.fetchone())

        # Ignore messages sent within 10 seconds of the last XP gain
        current_time = time.time()
        if current_time - last_message < 10:
            return None

        # Add a random amount of XP between 10 and 20 to the user's current XP
        new_xp = xp + random.randint(10, 20)
        new_level, leveled_up = calculate_new_level(new_xp, level)

        # Update the database with the new XP, level, and last message timestamp
        cursor.execute(
            "UPDATE user_info SET xp = %s, level = %s, last_message = %s "
            "WHERE user_id = %s",
            (new_xp, new_level, current_time, user_id),
        )
        get_db().commit()

        return new_level if leveled_up else None
    finally:
        cursor.close()
