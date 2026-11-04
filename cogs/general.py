import time
from discord.ext import commands


class General(commands.Cog):
    """Small utility commands."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the General cog with the bot instance."""
        self.bot = bot

    @commands.hybrid_command(name="delay", description="Check the bot's latency.")
    async def delay(self, ctx: commands.Context[commands.Bot]) -> None:
        """Show websocket latency and round-trip latency."""
        websocket_ms: float = self.bot.latency * 1000

        # Time how long Discord takes to accept and confirm a message
        start = time.perf_counter()
        message = await ctx.send("Pinging...")
        round_trip_ms = (time.perf_counter() - start) * 1000

        await message.edit(
            content=(
                f"Websocket latency: {websocket_ms:.2f} ms\n"
                f"Round-trip latency: {round_trip_ms:.2f} ms"
            )
        )


async def setup(bot: commands.Bot) -> None:
    """Setup function to add the General cog to the bot."""
    await bot.add_cog(General(bot))
