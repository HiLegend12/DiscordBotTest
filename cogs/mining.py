import math
import random
import time
from typing import cast

import discord
from discord.ext import commands

from config import MINE_COOLDOWN, ORES, PICKAXES
from database import ensure_user_exists, get_cursor, get_db


class Mining(commands.Cog):
    """Mining game: dig for ore, sell it for coins."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emojis: dict[str, str] = {}

    @commands.hybrid_command(name="mine", description="Mine for ore.")
    async def mine(self, ctx: commands.Context[commands.Bot]) -> None:
        user_id = ctx.author.id
        now = time.time()

        conn = get_db()
        cursor = get_cursor()
        try:
            # Make sure the user exists in the database
            ensure_user_exists(cursor, user_id)
            cursor.execute(
                "SELECT last_mine, pickaxe FROM user_info WHERE user_id = %s",
                (user_id,),
            )
            last_mine, pickaxe_key = cast(tuple[float, str], cursor.fetchone())

            # Cooldown check
            remaining = MINE_COOLDOWN - (now - last_mine)
            if remaining > 0:
                await ctx.send(
                    f"Your pickaxe needs a rest! Try again in {remaining:.1f}s."
                )
                return

            # Determine which ores can be mined based on the user's pickaxe tier
            pickaxe = PICKAXES.get(pickaxe_key, PICKAXES["hand"])
            names = [name for name, data in ORES.items() if data[1] <= pickaxe["tier"]]
            weights = [
                math.exp(
                    -((ORES[name][2] - pickaxe["center"]) ** 2)
                    / (2 * pickaxe["spread"] ** 2)
                )
                for name in names
            ]

            # Randomly select one ore based on the bell-curve weights
            ore: str = random.choices(names, weights=weights, k=1)[0]
            amount: int = random.randint(1, 3)

            conn.start_transaction()
            try:
                # Save the cooldown timestamp
                cursor.execute(
                    "UPDATE user_info SET last_mine = %s WHERE user_id = %s",
                    (now, user_id),
                )

                # Add the ore to the inventory
                cursor.execute(
                    "INSERT INTO inventory (user_id, item, quantity) "
                    "VALUES (%s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)",
                    (user_id, ore, amount),
                )

                # One commit: both writes save together or not at all
                conn.commit()
            except Exception:
                conn.rollback()
                raise

            # Build the embed
            embed = discord.Embed(
                title=ctx.author.display_name,
                color=discord.Color.dark_gold(),
            )
            embed.description = (
                f"**You mined:**\n{amount} {self.emojis.get(ore, '')} {ore.title()}"
            )
            await ctx.send(embed=embed)
        finally:
            cursor.close()

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
