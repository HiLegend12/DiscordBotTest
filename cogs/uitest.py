from collections.abc import Callable, Coroutine
from typing import Any

import discord
from discord.ext import commands

from config import PICKAXES

START_COINS = 600


class TestView(discord.ui.LayoutView):
    def __init__(self, emojis: dict[str, str]) -> None:
        super().__init__(timeout=120)
        self.emojis = emojis
        self.reset_state()
        self.build()

    def reset_state(self) -> None:
        self.coins = START_COINS
        self.owned: set[str] = {"wooden"}
        self.equipped = "wooden"

    def build(self) -> None:
        self.clear_items()

        container: discord.ui.Container[TestView] = discord.ui.Container(
            accent_colour=discord.Colour.green()
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

            button: discord.ui.Button[TestView] = discord.ui.Button(
                label=label,
                style=style,
                disabled=disabled,
                emoji=emoji or None,
            )
            button.callback = self.make_callback(key)  # type: ignore[assignment]

            container.add_item(
                discord.ui.Section(
                    discord.ui.TextDisplay(
                        f"{emoji} **{pickaxe['name']}**\n{pickaxe['description']}"
                    ),
                    accessory=button,
                )
            )

        container.add_item(discord.ui.Separator())

        reset: discord.ui.Button[TestView] = discord.ui.Button(
            label="Reset", style=discord.ButtonStyle.secondary
        )
        reset.callback = self.on_reset
        container.add_item(discord.ui.ActionRow(reset))

        self.add_item(container)

    def make_callback(
        self, key: str
    ) -> Callable[[discord.Interaction], Coroutine[Any, Any, None]]:
        """Create a callback that remembers which pickaxe it belongs to."""

        async def callback(interaction: discord.Interaction) -> None:
            if key not in self.owned:
                price = PICKAXES[key]["price"]
                if self.coins < price:  # safety net, button should be disabled
                    await interaction.response.send_message(
                        "You can't afford that.", ephemeral=True
                    )
                    return
                self.coins -= price
                self.owned.add(key)
            self.equipped = key
            self.build()
            await interaction.response.edit_message(view=self)

        return callback

    async def on_reset(self, interaction: discord.Interaction) -> None:
        self.reset_state()
        self.build()
        await interaction.response.edit_message(view=self)


class UITest(commands.Cog):
    """Temporary cog for testing Components V2."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emojis: dict[str, str] = {}

    @commands.hybrid_command(name="uitest", description="Test Components V2.")
    async def uitest(self, ctx: commands.Context[commands.Bot]) -> None:
        await ctx.send(view=TestView(self.emojis))

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Fetch the bot's application emojis once it's logged in."""
        if self.emojis:
            return
        fetched = await self.bot.fetch_application_emojis()
        self.emojis = {e.name: str(e) for e in fetched}


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UITest(bot))
