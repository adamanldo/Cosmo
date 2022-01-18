import discord
from discord.ext import commands

class Help(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='help')
    async def help(self, ctx):
        embed = discord.Embed()
        embed.add_field(name='.countdown', value="Countdown for listening parties.")
        embed.add_field(name='.fmi', value="Outputs formatted image of currently playing last.fm song")
        embed.add_field(name='.set', value="Adds last.fm username to database. Format: \".set [last.fm username]\"")
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Help(bot))