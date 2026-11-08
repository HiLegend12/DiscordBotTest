from typing import cast

import discord
from discord.ext import commands

from config import PICKAXES
from database import ensure_user_exists, get_pool


class PickaxeShopView(discord.ui.LayoutView):
    def __init__(
        self,
        user_id: int,
        emojis: dict[str, str],
        coins: int,
        owned: set[str],
        equipped: str,
    ) -> None:
        super().__init__(timeout=120)
        self.user_id = user_id
        self.emojis = emojis
        self.coins = coins
        self.owned = owned
        self.equipped = equipped
        self.build()

    def build(self) -> None:
        self.clear_items()

        container: discord.ui.Container[PickaxeShopView] = discord.ui.Container(
            accent_colour=discord.Colour.dark_gold()
        )
        container.add_item(discord.ui.TextDisplay("## Pickaxe Shop"))
        container.add_item(discord.ui.TextDisplay(f"Your balance: **${self.coins:,}**"))
        container.add_item(discord.ui.Separator())

        for key, pickaxe in PICKAXES.items():
            if pickaxe["tier"] == 0:
                continue  # skip bare hands

            emoji = self.emojis.get(f"{key}_pic", "")
            price = pickaxe["price"]

            if key == self.equipped:
                label, style, disabled = "Equipped", discord.ButtonStyle.success, True
            elif key in self.owned:
                label, style, disabled = "Select", discord.ButtonStyle.success, False
            else:
                label = f"${price:,}"
                style = discord.ButtonStyle.primary
                disabled = self.coins < price

            button: discord.ui.Button[PickaxeShopView] = discord.ui.Button(
                label=label,
                style=style,
                disabled=disabled,
                emoji=emoji or None,
            )
            button.callback = self.make_callback(key)  # type: ignore[assignment]

            container.add_item(
                discord.ui.Section(
                    discord.ui.TextDisplay(f"{emoji} **{pickaxe['name']}**"),
                    accessory=button,
                )
            )

        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only the person who ran /shop pickaxe may press its buttons."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This isn't your shop. Run `/shop pickaxe` yourself.", ephemeral=True
            )
            return False
        return True

    def make_callback(self, key: str):
        async def callback(interaction: discord.Interaction) -> None:
            error = await self.buy_or_equip(key)
            if error:
                await interaction.response.send_message(error, ephemeral=True)
                return
            self.build()
            await interaction.response.edit_message(view=self)

        return callback

    async def buy_or_equip(self, key: str) -> str | None:
        """Do the database work. Returns an error message, or None on success."""
        price = PICKAXES[key]["price"]

        async with get_pool().acquire() as conn:
            async with conn.cursor() as cursor:
                if key in self.owned:
                    await cursor.execute(
                        "UPDATE user_info SET pickaxe = %s WHERE user_id = %s",
                        (key, self.user_id),
                    )
                    self.equipped = key
                    return None

                await conn.begin()
                try:
                    # Claim ownership first. rowcount 0 means a double-click
                    # already bought it, so we must not charge again.
                    await cursor.execute(
                        "INSERT IGNORE INTO owned_pickaxes (user_id, pickaxe) "
                        "VALUES (%s, %s)",
                        (self.user_id, key),
                    )
                    if cursor.rowcount == 0:
                        await conn.rollback()
                        return "You already own that pickaxe."

                    await cursor.execute(
                        "UPDATE user_info SET coins = coins - %s, pickaxe = %s "
                        "WHERE user_id = %s AND coins >= %s",
                        (price, key, self.user_id, price),
                    )
                    if cursor.rowcount == 0:
                        await conn.rollback()
                        return "You can't afford that."

                    await conn.commit()
                except Exception:
                    await conn.rollback()
                    raise

        self.coins -= price
        self.owned.add(key)
        self.equipped = key
        return None


class Shop(commands.Cog):
    """Buy pickaxes with coins."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emojis: dict[str, str] = {}

    @commands.hybrid_group(name="shop", description="Browse the shops.")
    async def shop(self, ctx: commands.Context[commands.Bot]) -> None:
        """Parent command. Does nothing by itself when used with the ! prefix."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Try `/shop pickaxe`.")

    @shop.command(name="pickaxe", description="Browse and buy pickaxes.")
    async def shop_pickaxe(self, ctx: commands.Context[commands.Bot]) -> None:
        user_id = ctx.author.id
        async with get_pool().acquire() as conn:
            async with conn.cursor() as cursor:
                await ensure_user_exists(cursor, user_id)
                await cursor.execute(
                    "SELECT coins, pickaxe FROM user_info WHERE user_id = %s",
                    (user_id,),
                )
                coins, equipped = cast(tuple[int, str], await cursor.fetchone())
                await cursor.execute(
                    "SELECT pickaxe FROM owned_pickaxes WHERE user_id = %s",
                    (user_id,),
                )
                rows = cast(list[tuple[str]], await cursor.fetchall())

        owned = {row[0] for row in rows}
        await ctx.send(
            view=PickaxeShopView(user_id, self.emojis, coins, owned, equipped)
        )

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Fetch the bot's application emojis once it's logged in."""
        if self.emojis:
            return
        fetched = await self.bot.fetch_application_emojis()
        self.emojis = {e.name: str(e) for e in fetched}


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Shop(bot))