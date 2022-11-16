#Based on gist from EvieePy https://gist.github.com/EvieePy/d78c061a4798ae81be9825468fe146be#file-owner-py

import discord
from discord.ext import commands

class OwnerCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='servers', hidden=True)
    @commands.is_owner()
    async def servers(self, ctx):
        """Command which shows the total amount of server and users"""
        guilds = len(self.bot.guilds)
        users = sum([len([m for m in g.members if not m.bot]) for g in self.bot.guilds])

        embed = discord.Embed()
        embed.description = f'**Total servers:** {guilds}\n**Total users:** {users}'

        await ctx.send(embed=embed, delete_after=30)
    
    @commands.command(name='load', hidden=True)
    @commands.is_owner()
    async def load_cog(self, ctx, *, cog: str):
        """Command which Loads a Module.
        Remember to use dot path. e.g: cogs.owner"""

        try:
            await self.bot.load_extension(cog)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
        else:
            await ctx.send('**`SUCCESS`**')

    @commands.command(name='unload', hidden=True)
    @commands.is_owner()
    async def unload_cog(self, ctx, *, cog: str):
        """Command which Unloads a Module.
        Remember to use dot path. e.g: cogs.owner"""

        try:
            await self.bot.unload_extension(cog)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
        else:
            await ctx.send('**`SUCCESS`**')

    @commands.command(name='reload', hidden=True)
    @commands.is_owner()
    async def reload_cog(self, ctx, *, cog: str):
        """Command which Reloads a Module.
        Remember to use dot path. e.g: cogs.owner"""

        try:
            await self.bot.unload_extension(cog)
            await self.bot.load_extension(cog)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
        else:
            await ctx.send('**`SUCCESS`**')


async def setup(bot):
    await bot.add_cog(OwnerCog(bot))
