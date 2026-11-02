import random
import time
from typing import cast

import discord
from discord.ext import commands

from config import MINE_COOLDOWN, ORES
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

        cursor = get_cursor()
        try:
            # Make sure the user exists in the database
            ensure_user_exists(cursor, user_id)
            cursor.execute(
                "SELECT last_mine FROM user_info WHERE user_id = %s", (user_id,)
            )
            (last_mine,) = cast(tuple[float], cursor.fetchone())

            # Cooldown check
            remaining = MINE_COOLDOWN - (now - last_mine)
            if remaining > 0:
                await ctx.send(
                    f"Your pickaxe needs a rest! Try again in {remaining:.1f}s."
                )
                return

            # Randomly select ores to drop based on their weights
            names = list(ORES.keys())
            weights = [ORES[name][0] for name in names]

            # Randomly select ores to drop based on their weights
            drops: dict[str, int] = {}
            ore = random.choices(names, weights=weights, k=1)[0]
            drops[ore] = drops.get(ore, 0) + random.randint(1, 3)

            # Save the cooldown timestamp
            cursor.execute(
                "UPDATE user_info SET last_mine = %s WHERE user_id = %s",
                (now, user_id),
            )

            # Upsert every ore that dropped into the inventory
            for ore, amount in drops.items():
                cursor.execute(
                    "INSERT INTO inventory (user_id, item, quantity) "
                    "VALUES (%s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)",
                    (user_id, ore, amount),
                )

            get_db().commit()

            # Build the embed
            lines = "\n".join(
                f"{amount} {self.emojis.get(ore, '')} {ore.title()}"
                for ore, amount in drops.items()
            )
            embed = discord.Embed(
                title=ctx.author.display_name,
                color=discord.Color.dark_gold(),
            )
            embed.description = f"**You mined:**\n{lines}"
            await ctx.send(embed=embed)
        finally:
            cursor.close()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Fetch the bot's application emojis once it's logged in."""
        fetched = await self.bot.fetch_application_emojis()
        self.emojis = {emoji.name: str(emoji) for emoji in fetched}


async def setup(bot: commands.Bot) -> None:
    """Setup function to add the Mining cog to the bot."""
    await bot.add_cog(Mining(bot))
