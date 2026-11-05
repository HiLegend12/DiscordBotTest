import asyncio
import random
import time
from typing import cast

import discord
from discord.ext import commands

from config import DAILY_COOLDOWN, DEBUG, STREAK_WINDOW
from database import ensure_user_exists, get_pool
from levels import add_xp, announce_level_up, calculate_new_level
from rankcard import generate_rank_card


class XP(commands.Cog):
    """XP gain, ranks, the leaderboard and daily rewards."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the XP cog with the bot instance."""
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Award XP for regular messages."""
        if DEBUG:
            print(f"on_message fired: {message.author} said {message.content!r}")
        if message.author.bot or not message.guild:
            return

        # Commands and bot pings don't earn XP
        ctx = await self.bot.get_context(message)
        is_command = ctx.valid or message.content.startswith("!")
        is_bot_ping = self.bot.user is not None and self.bot.user in message.mentions
        if is_command or is_bot_ping:
            return

        # Award XP and check for level up
        new_level = await add_xp(message.author.id)
        if new_level is None:
            return

        await announce_level_up(message.channel, message.author, new_level)

    @commands.hybrid_command(
        name="rank", description="Display the rank (level and XP) of a user."
    )
    @commands.guild_only()
    async def rank(
        self,
        ctx: commands.Context[commands.Bot],
        member: discord.Member | None = None,
    ) -> None:
        """Display the rank (level and XP) of a user."""
        target: discord.Member | discord.User = member or ctx.author

        await ctx.defer()

        async with get_pool().acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT xp, level, last_daily, daily_streak, mining_xp, mining_level "
                    "FROM user_info WHERE user_id = %s",
                    (target.id,),
                )
                result = cast(
                    tuple[int, int, float, int, int, int] | None,
                    await cursor.fetchone(),
                )

        if result is None:
            xp, level, streak, mining_xp, mining_level = 0, 0, 0, 0, 0
        else:
            xp, level, last_daily, streak, mining_xp, mining_level = result
            if time.time() - last_daily >= STREAK_WINDOW:
                streak = 0

        user_colour: tuple[int, int, int] = (
            target.color.to_rgb() if target.color.value != 0 else (255, 255, 255)
        )
        avatar_bytes = (
            await target.display_avatar.with_size(256).with_format("png").read()
        )

        # Generate the image in a separate thread to avoid blocking the event loop
        image_buffer = await asyncio.to_thread(
            generate_rank_card,
            target.display_name,
            avatar_bytes,
            xp,
            level,
            user_colour,
            streak,
            mining_xp,
            mining_level,
        )

        file = discord.File(fp=image_buffer, filename="rank_card.png")
        await ctx.send(file=file)

    @commands.hybrid_command(
        name="leaderboard",
        description="Display the top 10 users on the leaderboard.",
        aliases=["lb", "top"],
    )
    async def leaderboard(self, ctx: commands.Context[commands.Bot]) -> None:
        """Display the top 10 users on the leaderboard."""
        async with get_pool().acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT user_id, xp, level FROM user_info "
                    "ORDER BY level DESC, xp DESC LIMIT 10"
                )
                results = cast(
                    list[tuple[int, int, int]] | None, await cursor.fetchall()
                )

        if not results:
            await ctx.send("No data recorded yet.")
            return

        embed = discord.Embed(title="Leaderboard", color=discord.Color.gold())

        description = ""
        for rank_num, (user_id, xp, level) in enumerate(results, start=1):
            description += f"{rank_num}. <@{user_id}> - **Level: {level}**, XP: {xp}\n"

        embed.description = description
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="daily", description="Claim your daily XP reward.")
    async def daily(self, ctx: commands.Context[commands.Bot]) -> None:
        """Claim your daily XP reward."""
        user_id: int = ctx.author.id
        now: float = time.time()

        async with get_pool().acquire() as conn:
            async with conn.cursor() as cursor:
                await ensure_user_exists(cursor, user_id)
                await cursor.execute(
                    "SELECT xp, level, last_daily, daily_streak "
                    "FROM user_info WHERE user_id = %s",
                    (user_id,),
                )
                xp, level, last_daily, streak = cast(
                    tuple[int, int, float, int], await cursor.fetchone()
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

                # Claimed within 48h keeps the streak; otherwise restart at 1
                is_first_claim = last_daily == 0
                streak = streak + 1 if elapsed < STREAK_WINDOW else 1

                # Streak bonus (max +50 XP for a 10-day streak)
                streak_bonus = min(streak, 10) * 5
                daily_reward = random.randint(100, 175) + streak_bonus

                new_xp = xp + daily_reward
                new_level, leveled_up = calculate_new_level(new_xp, level)

                await cursor.execute(
                    "UPDATE user_info SET xp = %s, level = %s, last_daily = %s, "
                    "daily_streak = %s WHERE user_id = %s",
                    (new_xp, new_level, now, streak, user_id),
                )

        # Discord messages go outside the DB block
        if is_first_claim:
            await ctx.send(
                f"Welcome {ctx.author.mention}! You claimed your first daily reward of **{daily_reward} XP**!"
            )
        else:
            await ctx.send(
                f"Daily reward claimed! You received **{daily_reward} XP** "
                f"(streak: **{streak}**, bonus: +{streak_bonus} XP)."
            )

        if leveled_up:
            await announce_level_up(ctx, ctx.author, new_level)


async def setup(bot: commands.Bot) -> None:
    """Setup function to add the XP cog to the bot."""
    await bot.add_cog(XP(bot))
