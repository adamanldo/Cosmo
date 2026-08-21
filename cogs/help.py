import discord
from discord.ext import commands


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="help", description="Show available commands")
    async def help(self, ctx):
        embed = discord.Embed()
        embed.description = "Commands also work as slash commands, e.g. `/fmi`."
        embed.add_field(name=".cd", value="Countdown for listening parties.")
        embed.add_field(
            name=".fmi",
            value="Outputs formatted image of currently playing last.fm song",
        )
        embed.add_field(
            name=".set",
            value='Adds last.fm username to database. Format: ".set username"',
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Help(bot))
