from discord.ext import commands
import asyncio

class Countdown(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.command(name='countdown')
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def count(self, ctx):
        msg = await ctx.send('10')
        await asyncio.sleep(1)
        for num in range(9, 0, -1):
            try:
                await msg.edit(content=num)
                await asyncio.sleep(1)
            except:
                return
        await msg.edit(content="Go!")

    @count.error
    async def count_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send("This command can only be used once every 10 seconds per server.")

def setup(bot):
    bot.add_cog(Countdown(bot))
