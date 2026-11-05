import math
import random
import time
from typing import cast

import discord
from discord.ext import commands

from config import MINE_COOLDOWN, MINING_XP_BASE, ORE_XP, ORES, PICKAXES
from database import ensure_user_exists, get_pool
from levels import calculate_new_level


class Mining(commands.Cog):
    """Mining game: dig for ore, sell it for coins."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emojis: dict[str, str] = {}

    @commands.hybrid_command(name="mine", description="Mine for ore.")
    async def mine(self, ctx: commands.Context[commands.Bot]) -> None:
        user_id = ctx.author.id
        now = time.time()

        async with get_pool().acquire() as conn:
            async with conn.cursor() as cursor:
                await ensure_user_exists(cursor, user_id)
                await cursor.execute(
                    "SELECT last_mine, pickaxe, mining_xp, mining_level "
                    "FROM user_info WHERE user_id = %s",
                    (user_id,),
                )
                last_mine, pickaxe_key, mining_xp, mining_level = cast(
                    tuple[float, str, int, int], await cursor.fetchone()
                )

                # Cooldown check
                remaining = MINE_COOLDOWN - (now - last_mine)
                if remaining > 0:
                    await ctx.send(
                        f"Your pickaxe needs a rest! Try again in {remaining:.1f}s."
                    )
                    return

                # Ores allowed by pickaxe tier, weighted by a bell curve
                pickaxe = PICKAXES.get(pickaxe_key, PICKAXES["hand"])
                names = [
                    name for name, data in ORES.items() if data[1] <= pickaxe["tier"]
                ]
                weights = [
                    math.exp(
                        -((ORES[name][2] - pickaxe["center"]) ** 2)
                        / (2 * pickaxe["spread"] ** 2)
                    )
                    for name in names
                ]

                ore: str = random.choices(names, weights=weights, k=1)[0]
                amount: int = random.randint(1, 3)

                # Mining XP is separate from chat XP and has its own level
                xp_gained: int = ORE_XP[ore] * amount
                new_mining_xp: int = mining_xp + xp_gained
                new_mining_level, leveled_up = calculate_new_level(
                    new_mining_xp, mining_level, MINING_XP_BASE
                )

                # This connection belongs only to this command, so no other
                # command can interleave statements into the transaction.
                await conn.begin()
                try:
                    await cursor.execute(
                        "UPDATE user_info "
                        "SET last_mine = %s, mining_xp = %s, mining_level = %s "
                        "WHERE user_id = %s",
                        (now, new_mining_xp, new_mining_level, user_id),
                    )
                    await cursor.execute(
                        "INSERT INTO inventory (user_id, item, quantity) "
                        "VALUES (%s, %s, %s) "
                        "ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)",
                        (user_id, ore, amount),
                    )
                    await conn.commit()
                except Exception:
                    await conn.rollback()
                    raise

        # Build the embed outside the DB block
        embed = discord.Embed(
            title=ctx.author.display_name,
            color=discord.Color.dark_gold(),
        )
        description = (
            f"**You mined:**\n{amount} {self.emojis.get(ore, '')} {ore.title()}"
            f"\n\n+{xp_gained} Mining XP"
        )
        if leveled_up:
            description += (
                f"\n**Mining level up! You're now Mining Level {new_mining_level}.**"
            )
        embed.description = description
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Fetch the bot's application emojis once it's logged in."""
        if self.emojis:
            return
        fetched = await self.bot.fetch_application_emojis()
        self.emojis = {emoji.name: str(emoji) for emoji in fetched}


async def setup(bot: commands.Bot) -> None:
    """Setup function to add the Mining cog to the bot."""
    await bot.add_cog(Mining(bot))
