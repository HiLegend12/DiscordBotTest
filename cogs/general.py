from discord.ext import commands


class General(commands.Cog):
    """Small utility commands."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the General cog with the bot instance."""
        self.bot = bot

    @commands.hybrid_command(name="delay", description="Check the bot's latency.")
    async def delay(self, ctx: commands.Context[commands.Bot]) -> None:
        """Check the bot's latency."""
        latency_ms: float = self.bot.latency * 1000
        await ctx.send(f"Latency is {latency_ms:.2f} ms.")


async def setup(bot: commands.Bot) -> None:
    """Setup function to add the General cog to the bot."""
    await bot.add_cog(General(bot))
