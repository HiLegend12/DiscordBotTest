from typing import cast

import discord
from discord.ext import commands

from config import PICKAXES
from database import ensure_user_exists, get_cursor, get_db


class Shop(commands.Cog):
    """Buy pickaxes with coins."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the Shop cog with the bot instance."""
        self.bot = bot

    @commands.hybrid_command(name="shop", description="View pickaxes for sale.")
    async def shop(self, ctx: commands.Context[commands.Bot]) -> None:
        """Display the list of pickaxes available for purchase."""
        cursor = get_cursor()
        try:
            # Ensure the user exists in the database and fetch their coins and current pickaxe
            ensure_user_exists(cursor, ctx.author.id)
            cursor.execute(
                "SELECT coins, pickaxe FROM user_info WHERE user_id = %s",
                (ctx.author.id,),
            )
            coins, current = cast(tuple[int, str], cursor.fetchone())
        finally:
            cursor.close()
        current_tier = PICKAXES.get(current, PICKAXES["hand"])["tier"]

        # Build the shop display
        lines: list[str] = []
        for key, p in PICKAXES.items():
            if p["tier"] == 0:
                continue
            if key == current:
                status = "Equipped"
            elif p["tier"] < current_tier:
                status = "Owned"
            else:
                status = f"{p['price']:,} coins"
            lines.append(f"**{p['name']}** (`{key}`) - {status}")

        # Create and send the embed message
        embed = discord.Embed(
            title="Pickaxe Shop",
            description="\n".join(lines),
            color=discord.Color.dark_gold(),
        )
        embed.set_footer(text=f"Your coins: {coins:,}  |  Use /buy <name>")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="buy", description="Buy a pickaxe.")
    async def buy(self, ctx: commands.Context[commands.Bot], pickaxe: str) -> None:
        """Purchase a pickaxe if the user has enough coins and doesn't already own it."""
        # Validate the pickaxe key and fetch the corresponding item
        key = pickaxe.lower()
        item = PICKAXES.get(key)
        if item is None or item["tier"] == 0:
            await ctx.send("That pickaxe doesn't exist. Use `/shop` to see the list.")
            return

        cursor = get_cursor()
        try:
            # Ensure the user exists in the database and fetch their coins and current pickaxe
            ensure_user_exists(cursor, ctx.author.id)
            cursor.execute(
                "SELECT coins, pickaxe FROM user_info WHERE user_id = %s",
                (ctx.author.id,),
            )
            coins, current = cast(tuple[int, str], cursor.fetchone())
            current_tier = PICKAXES.get(current, PICKAXES["hand"])["tier"]

            # Check if the user already owns the pickaxe or has enough coins
            if item["tier"] <= current_tier:
                await ctx.send("You already have that pickaxe or a better one.")
                return
            if coins < item["price"]:
                await ctx.send(
                    f"You need {item['price']:,} coins but only have {coins:,}."
                )
                return

            # Charge the coins and equip the pickaxe in one statement
            cursor.execute(
                "UPDATE user_info SET coins = coins - %s, pickaxe = %s "
                "WHERE user_id = %s AND coins >= %s",
                (item["price"], key, ctx.author.id, item["price"]),
            )
            if cursor.rowcount == 0:
                await ctx.send("Purchase failed: not enough coins.")
                return
            get_db().commit()

            await ctx.send(f"You bought the **{item['name']}**!")
        finally:
            cursor.close()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Shop(bot))