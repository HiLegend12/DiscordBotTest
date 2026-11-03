from typing import cast

import discord
from discord.ext import commands

from config import ORES
from database import ensure_user_exists, get_cursor, get_db


class Economy(commands.Cog):
    """Inventory and selling."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the Economy cog with the bot instance."""
        self.bot = bot
        self.emojis: dict[str, str] = {}

    @commands.hybrid_command(name="inventory", description="View your ore and coins.")
    async def inventory(self, ctx: commands.Context[commands.Bot]) -> None:
        """Display the user's inventory of ores and their coin balance."""
        # Validate the user and fetch their inventory and coin balance
        user_id = ctx.author.id
        cursor = get_cursor()
        try:
            # Ensure the user exists in the database and fetch their inventory and coin balance
            ensure_user_exists(cursor, user_id)
            cursor.execute(
                "SELECT item, quantity FROM inventory "
                "WHERE user_id = %s AND quantity > 0 ORDER BY item",
                (user_id,),
            )
            rows = cast(list[tuple[str, int]], cursor.fetchall())
            cursor.execute("SELECT coins FROM user_info WHERE user_id = %s", (user_id,))
            (coins,) = cast(tuple[int], cursor.fetchone())
        finally:
            cursor.close()

        # Build the inventory display based on the fetched data
        if rows:
            body = "\n".join(
                f"{qty:,} {self.emojis.get(item, '')} {item.title()}"
                for item, qty in rows
            )
        else:
            body = "Nothing yet. Try `/mine`!"

        # Create and send the embed message with the inventory details
        embed = discord.Embed(
            title=f"{ctx.author.display_name}'s Inventory",
            description=body,
            color=discord.Color.dark_gold(),
        )
        embed.set_footer(text=f"Coins: {coins:,}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="sell", description="Sell ore for coins.")
    async def sell(
        self, ctx: commands.Context[commands.Bot], item: str = "all"
    ) -> None:
        """Sell ore for coins. If "all" is specified, sell all ores in the inventory."""
        # Validate the item key and fetch the corresponding ore
        user_id = ctx.author.id
        key = item.lower()

        conn = get_db()
        cursor = get_cursor()
        try:
            # Ensure the user exists in the database and fetch their inventory
            ensure_user_exists(cursor, user_id)
            cursor.execute(
                "SELECT item, quantity FROM inventory "
                "WHERE user_id = %s AND quantity > 0",
                (user_id,),
            )
            rows = cast(list[tuple[str, int]], cursor.fetchall())

            # Filter the inventory to only include ores that match the specified item or all ores if "all" is specified
            to_sell = [
                (name, qty)
                for name, qty in rows
                if name in ORES and (key == "all" or name == key)
            ]
            if not to_sell:
                await ctx.send("You have nothing to sell.")
                return

            # Calculate the total earnings and update the database
            total = 0
            lines: list[str] = []
            conn.start_transaction()
            try:
                for name, qty in to_sell:
                    # Only removes the ore if you still have that much
                    cursor.execute(
                        "UPDATE inventory SET quantity = quantity - %s "
                        "WHERE user_id = %s AND item = %s AND quantity >= %s",
                        (qty, user_id, name, qty),
                    )
                    if cursor.rowcount == 0:
                        continue
                    earned = qty * ORES[name][0]
                    total += earned
                    lines.append(
                        f"{qty:,} {self.emojis.get(name, '')} {name.title()}: {earned:,}"
                    )

                cursor.execute(
                    "UPDATE user_info SET coins = coins + %s WHERE user_id = %s",
                    (total, user_id),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        finally:
            cursor.close()

        if not lines:
            await ctx.send("You have nothing to sell.")
            return

        # Create and send the embed message with the sale details
        embed = discord.Embed(
            title=f"{ctx.author.display_name} sold:",
            description="\n".join(lines) + f"\n\n**+{total:,} coins**",
            color=discord.Color.green(),
        )
        await ctx.send(embed=embed)

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
