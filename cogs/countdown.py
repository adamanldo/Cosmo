from discord.ext import commands
import asyncio


class Countdown(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="cd")
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def count(self, ctx):
        msg = await ctx.send("10")
        await asyncio.sleep(1)
        for num in range(9, 0, -1):
            try:
                await msg.edit(content=num)
                await asyncio.sleep(1)
            except:
                return
        await msg.edit(content="Go!")

    @commands.command(name="scd")
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def short_count(self, ctx):
        msg = await ctx.send("5")
        await asyncio.sleep(1)
        for num in range(4, 0, -1):
            try:
                await msg.edit(content=num)
                await asyncio.sleep(1)
            except:
                return
        await msg.edit(content="Go!")

    @count.error
    async def count_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                "This command can only be used once every 10 seconds per server."
            )

    @short_count.error
    async def short_count_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                "This command can only be used once every 5 seconds per server."
            )


async def setup(bot):
    await bot.add_cog(Countdown(bot))
