import random
import time
from typing import cast
from discord.ext import commands
from config import MINE_COOLDOWN, ORES
from database import ensure_user_exists, get_cursor, get_db

class Mining(commands.Cog):
    """Mining game: dig for ore, sell it for coins."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the Mining cog with the bot instance."""
        self.bot = bot

    @commands.hybrid_command(name="mine", description="Mine for ore.")
    async def mine(self, ctx: commands.Context[commands.Bot]) -> None:
        """Mine for ore."""
        user_id: int = ctx.author.id
        current_time: float = time.time()

        cursor = get_cursor()
        try:
            # Ensure the user exists in the database and fetch their last mine timestamp
            ensure_user_exists(cursor, user_id)
            cursor.execute(
                "SELECT last_mine FROM user_info WHERE user_id = %s", (user_id,)
            )
            (last_mine,) = cast(tuple[float], cursor.fetchone())

            # Check if the user is still on cooldown for mining
            remaining: float = MINE_COOLDOWN - (current_time - last_mine)
            if remaining > 0:
                await ctx.send(f"Your pickaxe needs a rest! Try again in {remaining:.1f}s.")
                return

            # Randomly select an ore based on the defined weights and determine the amount mined
            names = list(ORES.keys())
            weights = [ORES[name][0] for name in names]
            ore = random.choices(names, weights=weights, k=1)[0]
            amount = random.randint(1, 3)

            # Update the last_mine timestamp and upsert the mined ore into the inventory
            cursor.execute(
                "UPDATE user_info SET last_mine = %s WHERE user_id = %s",
                (current_time, user_id),
            )
            # Upsert the ore into the inventory
            cursor.execute(
                "INSERT INTO inventory (user_id, item, quantity) VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)",
                (user_id, ore, amount),
            )
            get_db().commit()

            await ctx.send(f"⛏️ {ctx.author.mention} mined **{amount}x {ore}**!")
        finally:
            cursor.close()


async def setup(bot: commands.Bot) -> None:
    """Add the Mining cog to the bot."""
    await bot.add_cog(Mining(bot))
