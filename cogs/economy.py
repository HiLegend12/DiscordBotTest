from typing import cast

import discord
from discord.ext import commands

from config import ORES, PICKAXES, MINING_XP_BASE
from database import ensure_user_exists, get_cursor, get_db


class Economy(commands.Cog):
    """Inventory and selling."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the Economy cog with the bot instance."""
        self.bot = bot
        self.emojis: dict[str, str] = {}

    @commands.hybrid_command(name="inventory", description="View your inventory.", aliases=["inv"])
    async def inventory(self, ctx: commands.Context[commands.Bot]) -> None:
        """Display the user's stats, equipped pickaxe, and ores."""
        user_id = ctx.author.id
        cursor = get_cursor()
        try:
            ensure_user_exists(cursor, user_id)
            cursor.execute(
                "SELECT coins, pickaxe, mining_xp, mining_level "
                "FROM user_info WHERE user_id = %s",
                (user_id,),
            )
            coins, pickaxe_key, mining_xp, mining_level = cast(
                tuple[int, str, int, int], cursor.fetchone()
            )
            cursor.execute(
                "SELECT item, quantity FROM inventory "
                "WHERE user_id = %s AND quantity > 0",
                (user_id,),
            )
            rows = cast(list[tuple[str, int]], cursor.fetchall())
        finally:
            cursor.close()

        owned: dict[str, int] = dict(rows)
        pickaxe_name: str = PICKAXES.get(pickaxe_key, PICKAXES["hand"])["name"]
        pickaxe_emoji: str = self.emojis.get(f"{pickaxe_key}_pic", "")
        xp_needed: int = MINING_XP_BASE * (mining_level**2)

        # One line per ore, in the order defined in config (dirt -> diamond)
        ore_lines: list[str] = []
        total_value: int = 0
        for name, data in ORES.items():
            qty = owned.get(name, 0)
            total_value += qty * data[0]
            ore_lines.append(f"{qty:,} {self.emojis.get(name, '')} {name.title()}")

        description = (
            f"Balance: **${coins:,}**\n"
            f"**Level {mining_level}**, {mining_xp:,} / {xp_needed:,} XP to next level\n"
            f"Currently using: {pickaxe_emoji} **{pickaxe_name}**\n\n"
            f"**Ores**\n" + "\n".join(ore_lines) + f"\nOre value: **${total_value:,}**"
        )

        embed = discord.Embed(
            title=f"Inventory of {ctx.author.display_name}",
            description=description,
            color=discord.Color.dark_gold(),
        )
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
