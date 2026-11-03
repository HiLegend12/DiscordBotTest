from typing import Any, cast

import discord
from discord import app_commands
from discord.ext import commands

from database import ensure_user_exists, get_cursor
from levels import calculate_new_level, grant_level_roles


class Admin(commands.Cog):
    """Admin-only commands."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the Admin cog with the bot instance."""
        self.bot = bot

    @commands.hybrid_command(name="givexp", description="[ADMIN] Give XP to a user.")
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def givexp(
        self,
        ctx: commands.Context[commands.Bot],
        member: discord.Member,
        xp_amount: int,
    ) -> None:
        """[ADMIN] Give XP to a user."""
        # Validate the XP amount
        if xp_amount <= 0:
            await ctx.send("Please provide a positive amount of XP to give.")
            return

        cursor = get_cursor()
        try:
            # Ensure the user exists in the database
            ensure_user_exists(cursor, member.id)
            cursor.execute(
                "SELECT xp, level FROM user_info WHERE user_id = %s", (member.id,)
            )
            xp, level = cast(tuple[int, int], cursor.fetchone())

            # Calculate the new XP and level
            new_xp = xp + xp_amount
            new_level, _ = calculate_new_level(new_xp, level)

            # Update the database with the new XP and level
            cursor.execute(
                "UPDATE user_info SET xp = %s, level = %s WHERE user_id = %s",
                (new_xp, new_level, member.id),
            )

            # Grant any new level roles if the user leveled up
            await grant_level_roles(member, new_level)
            await ctx.send(
                f"Successfully gave **{xp_amount} XP** to {member.mention}. They are now **Level {new_level}** with **{new_xp} XP**."
            )
        finally:
            cursor.close()

    @commands.hybrid_command(name="setlevel", description="[ADMIN] Set a user's level.")
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def setlevel(
        self,
        ctx: commands.Context[commands.Bot],
        member: discord.Member,
        new_level: int,
    ) -> None:
        """[ADMIN] Set a user's level."""
        # Validate the new level
        if new_level < 0:
            await ctx.send("Level cannot be negative.")
            return

        cursor = get_cursor()
        try:
            # Calculate the base XP for the new level. The formula is 100 * (level^2).
            base_xp: int = 100 * ((new_level - 1) ** 2) if new_level > 0 else 0

            # Ensure the user exists in the database
            ensure_user_exists(cursor, member.id)
            cursor.execute(
                "UPDATE user_info SET xp = %s, level = %s WHERE user_id = %s",
                (base_xp, new_level, member.id),
            )

            # Grant any new level roles if the user leveled up
            await grant_level_roles(member, new_level)
            await ctx.send(
                f"Successfully set {member.mention} to **Level {new_level}** ({base_xp} XP)."
            )
        finally:
            cursor.close()

    async def cog_command_error(
        self, ctx: commands.Context[Any], error: Exception
    ) -> None:
        """Handle errors for commands in this cog."""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You do not have permission to use this command.")
        else:
            print(f"Unhandled error in {ctx.command}: {error!r}")
            await ctx.send("Something went wrong running that command.")


async def setup(bot: commands.Bot) -> None:
    """Setup function to add the Admin cog to the bot."""
    await bot.add_cog(Admin(bot))
