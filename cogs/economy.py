import asyncio
import time
from collections.abc import Coroutine
from typing import Any, cast

import discord
from discord import app_commands
from discord.ext import commands

from config import (
    FORGE_COUNT_COSTS,
    FORGE_SIZE_COSTS,
    MINING_XP_BASE,
    ORES,
    PICKAXES,
    SELL_PRICES,
    SMELT_SECONDS_PER_BAR,
    SMELTING,
)
from database import ensure_user_exists, get_pool


class Economy(commands.Cog):
    """Profile, selling, smelting and forges."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the Economy cog with the bot instance."""
        self.bot = bot
        self.emojis: dict[str, str] = {}
        self._tasks: set[asyncio.Task[None]] = set()

    def _spawn(self, coro: Coroutine[Any, Any, None]) -> None:
        """Run a coroutine in the background and keep a reference to it."""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _edit_when_ready(
        self, message: discord.Message, finish_time: float, new_content: str
    ) -> None:
        """Wait until the job finishes, then replace the message text."""
        await asyncio.sleep(max(0, finish_time - time.time()))
        try:
            await message.edit(content=new_content)
        except discord.HTTPException:
            pass

    async def _build_forge_embed(
        self, user_id: int, display_name: str
    ) -> tuple[discord.Embed, list[float]]:
        """Build the forge overview. Also returns finish times of jobs still running."""
        async with get_pool().acquire() as conn:
            async with conn.cursor() as cursor:
                await ensure_user_exists(cursor, user_id)
                await cursor.execute(
                    "SELECT forge_count, forge_size FROM user_info WHERE user_id = %s",
                    (user_id,),
                )
                count, size = cast(tuple[int, int], await cursor.fetchone())
                await cursor.execute(
                    "SELECT slot, bar, amount, finish_time FROM smelting "
                    "WHERE user_id = %s ORDER BY slot",
                    (user_id,),
                )
                jobs = cast(list[tuple[int, str, int, float]], await cursor.fetchall())

        max_size = len(FORGE_SIZE_COSTS) + 1
        count_cost = (
            f"${FORGE_COUNT_COSTS[count]:,}"
            if count < len(FORGE_COUNT_COSTS)
            else "MAX"
        )
        size_cost = f"${FORGE_SIZE_COSTS[size - 1]:,}" if size < max_size else "MAX"

        now = time.time()
        job_lines: list[str] = []
        pending: list[float] = []
        for slot, bar, amount, finish in jobs:
            name = bar.replace("_", " ").title()
            if finish <= now:
                status = "**Ready!** Use `/collect`"
            else:
                status = f"ready <t:{int(finish)}:R>"
                pending.append(finish)
            job_lines.append(f"Forge {slot}: {amount:,} {name} ({status})")

        description = (
            f"Forges: **{count}** / {len(FORGE_COUNT_COSTS)}  (next: {count_cost})\n"
            f"Size: **{size}** / {max_size}  (next: {size_cost})\n\n"
            + ("\n".join(job_lines) if job_lines else "No active jobs.")
            + "\n\nUse `/upgrade number` or `/upgrade size`."
        )
        embed = discord.Embed(
            title=f"{display_name}'s Forges",
            description=description,
            color=discord.Color.orange(),
        )
        return embed, pending

    async def _refresh_forge(
        self,
        message: discord.Message,
        finish_time: float,
        user_id: int,
        display_name: str,
    ) -> None:
        """Wait for one job to finish, then rebuild the embed from the database."""
        await asyncio.sleep(max(0, finish_time - time.time()) + 1)
        embed, _ = await self._build_forge_embed(user_id, display_name)
        try:
            await message.edit(embed=embed)
        except discord.HTTPException:
            pass

    @commands.hybrid_command(
        name="profile", description="View your profile.", aliases=["pf"]
    )
    async def profile(self, ctx: commands.Context[commands.Bot]) -> None:
        """Display the user's stats, equipped pickaxe, ores and bars."""
        user_id = ctx.author.id
        async with get_pool().acquire() as conn:
            async with conn.cursor() as cursor:
                await ensure_user_exists(cursor, user_id)
                await cursor.execute(
                    "SELECT coins, pickaxe, mining_xp, mining_level "
                    "FROM user_info WHERE user_id = %s",
                    (user_id,),
                )
                coins, pickaxe_key, mining_xp, mining_level = cast(
                    tuple[int, str, int, int], await cursor.fetchone()
                )
                await cursor.execute(
                    "SELECT item, quantity FROM inventory "
                    "WHERE user_id = %s AND quantity > 0",
                    (user_id,),
                )
                rows = cast(list[tuple[str, int]], await cursor.fetchall())

        owned: dict[str, int] = dict(rows)

        pickaxe_name: str = PICKAXES.get(pickaxe_key, PICKAXES["hand"])["name"]
        pickaxe_emoji: str = self.emojis.get(f"{pickaxe_key}_pic", "")
        xp_needed: int = MINING_XP_BASE * (mining_level**2)

        ore_lines: list[str] = []
        total_value: int = 0
        for name, data in ORES.items():
            qty = owned.get(name, 0)
            total_value += qty * data[0]
            ore_lines.append(f"{qty:,} {self.emojis.get(name, '')} {name.title()}")

        bar_lines: list[str] = []
        for bar, _, _, price in SMELTING.values():
            qty = owned.get(bar, 0)
            total_value += qty * price
            bar_lines.append(
                f"{qty:,} {self.emojis.get(bar, '')} {bar.replace('_', ' ').title()}"
            )

        description = (
            f"Balance: **${coins:,}**\n"
            f"**Level {mining_level}**, {mining_xp:,} / {xp_needed:,} XP to next level\n"
            f"Currently using: {pickaxe_emoji} **{pickaxe_name}**\n\n"
            f"**Ores**\n"
            + "\n".join(ore_lines)
            + "\n\n**Bars**\n"
            + "\n".join(bar_lines)
            + f"\n\nTotal value: **${total_value:,}**"
        )

        embed = discord.Embed(
            title=f"Profile of {ctx.author.display_name}",
            description=description,
            color=discord.Color.dark_gold(),
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="sell", description="Sell ore and bars for coins.")
    async def sell(
        self, ctx: commands.Context[commands.Bot], item: str = "all"
    ) -> None:
        """Sell ore or bars for coins. If "all" is specified, sell everything sellable."""
        user_id = ctx.author.id
        key = item.lower()

        total = 0
        lines: list[str] = []

        async with get_pool().acquire() as conn:
            async with conn.cursor() as cursor:
                await ensure_user_exists(cursor, user_id)
                await cursor.execute(
                    "SELECT item, quantity FROM inventory "
                    "WHERE user_id = %s AND quantity > 0",
                    (user_id,),
                )
                rows = cast(list[tuple[str, int]], await cursor.fetchall())

                to_sell = [
                    (name, qty)
                    for name, qty in rows
                    if name in SELL_PRICES and (key == "all" or name == key)
                ]
                if not to_sell:
                    await ctx.send("You have nothing to sell.")
                    return

                await conn.begin()
                try:
                    for name, qty in to_sell:
                        await cursor.execute(
                            "UPDATE inventory SET quantity = quantity - %s "
                            "WHERE user_id = %s AND item = %s AND quantity >= %s",
                            (qty, user_id, name, qty),
                        )
                        if cursor.rowcount == 0:
                            continue
                        earned = qty * SELL_PRICES[name]
                        total += earned
                        lines.append(
                            f"{qty:,} {self.emojis.get(name, '')} "
                            f"{name.replace('_', ' ').title()}: {earned:,}"
                        )

                    await cursor.execute(
                        "UPDATE user_info SET coins = coins + %s WHERE user_id = %s",
                        (total, user_id),
                    )
                    await conn.commit()
                except Exception:
                    await conn.rollback()
                    raise

        if not lines:
            await ctx.send("You have nothing to sell.")
            return

        embed = discord.Embed(
            title=f"{ctx.author.display_name} sold:",
            description="\n".join(lines) + f"\n\n**+{total:,} coins**",
            color=discord.Color.green(),
        )
        await ctx.send(embed=embed)

    @sell.autocomplete("item")
    async def sell_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Suggest 'all' plus the sellable items this user actually has."""
        async with get_pool().acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT item, quantity FROM inventory "
                    "WHERE user_id = %s AND quantity > 0",
                    (interaction.user.id,),
                )
                rows = cast(list[tuple[str, int]], await cursor.fetchall())

        current = current.lower()
        choices = [app_commands.Choice(name="All", value="all")]
        choices += [
            app_commands.Choice(
                name=f"{name.replace('_', ' ').title()} ({qty:,})", value=name
            )
            for name, qty in rows
            if name in SELL_PRICES
        ]
        return [c for c in choices if current in c.value][:25]

    @commands.hybrid_command(name="smelt", description="Smelt ore into bars.")
    async def smelt(
        self, ctx: commands.Context[commands.Bot], ore: str, amount: int = 1
    ) -> None:
        """Start a smelting job in a free forge."""
        key = ore.lower()
        recipe = SMELTING.get(key)
        if recipe is None:
            options = ", ".join(f"`{k}`" for k in SMELTING)
            await ctx.send(f"You can't smelt that. Smeltable ores: {options}.")
            return
        if amount <= 0:
            await ctx.send("Amount must be at least 1.")
            return

        # Unpack the recipe and calculate the total ore and coal needed
        bar, ore_each, coal_each, _ = recipe
        ore_needed = ore_each * amount
        coal_needed = coal_each * amount

        user_id = ctx.author.id
        # Check if the user has a forge, enough free slots, and enough ore and coal
        async with get_pool().acquire() as conn:
            async with conn.cursor() as cursor:
                await ensure_user_exists(cursor, user_id)
                await cursor.execute(
                    "SELECT forge_count, forge_size FROM user_info WHERE user_id = %s",
                    (user_id,),
                )
                forge_count, forge_size = cast(tuple[int, int], await cursor.fetchone())

                if forge_count == 0:
                    await ctx.send(
                        "You don't have a forge yet. Use `/forge` to see how to get one."
                    )
                    return
                # Check if the user has enough ore and coal
                if amount > forge_size:
                    await ctx.send(
                        f"Your forges can only smelt {forge_size} bar(s) at a time."
                    )
                    return

                await cursor.execute(
                    "SELECT slot, finish_time FROM smelting WHERE user_id = %s",
                    (user_id,),
                )
                busy = dict(cast(list[tuple[int, float]], await cursor.fetchall()))
                free_slot = next(
                    (s for s in range(1, forge_count + 1) if s not in busy), None
                )
                # If all slots are busy, check if any have finished
                if free_slot is None:
                    soonest = min(busy.values())
                    if soonest <= time.time():
                        await ctx.send(
                            "Your forges are full, but one has finished! Use `/collect`."
                        )
                    else:
                        await ctx.send(
                            f"All your forges are busy! One finishes "
                            f"<t:{int(soonest)}:R>. Use `/collect` when it's done."
                        )
                    return

                finish_time = time.time() + SMELT_SECONDS_PER_BAR * amount

                await conn.begin()
                try:
                    # Deduct the required ore from the user's inventory
                    await cursor.execute(
                        "UPDATE inventory SET quantity = quantity - %s "
                        "WHERE user_id = %s AND item = %s AND quantity >= %s",
                        (ore_needed, user_id, key, ore_needed),
                    )
                    ok = cursor.rowcount == 1

                    if ok:
                        # Check for coal availability
                        await cursor.execute(
                            "UPDATE inventory SET quantity = quantity - %s "
                            "WHERE user_id = %s AND item = %s AND quantity >= %s",
                            (coal_needed, user_id, "coal", coal_needed),
                        )
                        ok = cursor.rowcount == 1

                    if not ok:
                        # Rollback if either the ore or coal update failed (not enough quantity)
                        await ctx.send(
                            f"You need {ore_needed:,} {key} and {coal_needed:,} coal "
                            f"to smelt {amount:,} bar(s)."
                        )
                        return

                    await cursor.execute(
                        "INSERT INTO smelting (user_id, slot, bar, amount, finish_time) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (user_id, free_slot, bar, amount, finish_time),
                    )
                    await conn.commit()
                except Exception:
                    await conn.rollback()
                    raise

        name = bar.replace("_", " ").title()
        msg = await ctx.send(
            f"Forge {free_slot} is smelting {ore_needed:,} {key} and "
            f"{coal_needed:,} coal into {amount:,} {name}. "
            f"Ready <t:{int(finish_time)}:R>."
        )
        # Background task to edit the message when the job is finished
        self._spawn(
            self._edit_when_ready(
                msg,
                finish_time,
                f"Forge {free_slot} finished {amount:,} {name}! Use `/collect`.",
            )
        )

    @smelt.autocomplete("ore")
    async def smelt_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        current = current.lower()
        return [
            app_commands.Choice(name=ore.title(), value=ore)
            for ore in SMELTING
            if current in ore
        ]

    @commands.hybrid_command(name="collect", description="Collect finished bars.")
    async def collect(self, ctx: commands.Context[commands.Bot]) -> None:
        """Pick up the bars from every finished forge."""
        user_id = ctx.author.id
        now = time.time()

        collected: dict[str, int] = {}

        async with get_pool().acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT slot, bar, amount FROM smelting "
                    "WHERE user_id = %s AND finish_time <= %s",
                    (user_id, now),
                )
                done = cast(list[tuple[int, str, int]], await cursor.fetchall())
                if not done:
                    await ctx.send("Nothing is ready to collect.")
                    return

                await conn.begin()
                try:
                    for slot, bar, amount in done:
                        await cursor.execute(
                            "DELETE FROM smelting WHERE user_id = %s AND slot = %s",
                            (user_id, slot),
                        )
                        if cursor.rowcount == 0:
                            continue
                        await cursor.execute(
                            "INSERT INTO inventory (user_id, item, quantity) "
                            "VALUES (%s, %s, %s) "
                            "ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)",
                            (user_id, bar, amount),
                        )
                        collected[bar] = collected.get(bar, 0) + amount
                    await conn.commit()
                except Exception:
                    await conn.rollback()
                    raise

        if not collected:
            await ctx.send("Nothing is ready to collect.")
            return
        lines = [
            f"{qty:,} {self.emojis.get(bar, '')} {bar.replace('_', ' ').title()}"
            for bar, qty in collected.items()
        ]
        await ctx.send("You collected:\n" + "\n".join(lines))

    @commands.hybrid_command(name="forge", description="View your forges.")
    async def forge(self, ctx: commands.Context[commands.Bot]) -> None:
        """Show forge count, size, active jobs and upgrade costs."""
        embed, pending = await self._build_forge_embed(
            ctx.author.id, ctx.author.display_name
        )
        msg = await ctx.send(embed=embed)

        for finish in pending:
            self._spawn(
                self._refresh_forge(msg, finish, ctx.author.id, ctx.author.display_name)
            )

    @commands.hybrid_command(name="upgrade", description="Upgrade your forges.")
    async def upgrade(self, ctx: commands.Context[commands.Bot], kind: str) -> None:
        """Buy another forge ('number') or bigger forges ('size')."""
        kind = kind.lower()
        if kind not in ("number", "size"):
            await ctx.send("Choose `number` or `size`.")
            return

        # Safe to put in an f-string: only ever one of our own two literals
        column = "forge_count" if kind == "number" else "forge_size"

        user_id = ctx.author.id
        async with get_pool().acquire() as conn:
            async with conn.cursor() as cursor:
                await ensure_user_exists(cursor, user_id)
                await cursor.execute(
                    f"SELECT coins, {column} FROM user_info WHERE user_id = %s",
                    (user_id,),
                )
                coins, current = cast(tuple[int, int], await cursor.fetchone())

                costs = FORGE_COUNT_COSTS if kind == "number" else FORGE_SIZE_COSTS
                index = current if kind == "number" else current - 1
                if index >= len(costs):
                    await ctx.send("That's already at the maximum level.")
                    return

                cost = costs[index]
                if coins < cost:
                    await ctx.send(f"You need ${cost:,} but only have ${coins:,}.")
                    return

                await cursor.execute(
                    f"UPDATE user_info SET coins = coins - %s, {column} = {column} + 1 "
                    f"WHERE user_id = %s AND coins >= %s AND {column} = %s",
                    (cost, user_id, cost, current),
                )
                if cursor.rowcount == 0:
                    await ctx.send("Upgrade failed, try again.")
                    return

        await ctx.send(f"Upgraded forge {kind} to **{current + 1}** for ${cost:,}!")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Fetch the bot's application emojis once it's logged in."""
        if self.emojis:
            return
        fetched = await self.bot.fetch_application_emojis()
        self.emojis = {emoji.name: str(emoji) for emoji in fetched}


async def setup(bot: commands.Bot) -> None:
    """Setup function to add the Economy cog to the bot."""
    await bot.add_cog(Economy(bot))
