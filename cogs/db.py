import asyncpg
import discord
from discord.ext import commands

class DB(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def find_user(self, discordID):
        query = "SELECT username FROM discord WHERE id = $1;"
        async with self.bot.pool.acquire() as connection:
            row = await connection.fetchrow(query, discordID)
            if row:
                return row.get('username')
            return None
            
    @commands.command(name='set')
    async def register(self, ctx, lastfmusername: str):
        query = """INSERT INTO discord (id, username)
                    VALUES ($1, $2)
                    ON CONFLICT (id) DO UPDATE SET username = EXCLUDED.username"""
        async with self.bot.pool.acquire() as connection:
            try:
                async with connection.transaction():
                    await connection.execute(query, ctx.message.author.id, lastfmusername)
                    await ctx.send("{}'s Last.fm account has been set.".format(ctx.message.author.display_name))
            except:
                await ctx.send("There was an error adding the user.")

async def create_pool():
    pool = await asyncpg.create_pool(database='cosmo', user='postgres')
    return pool

def setup(bot):
    bot.add_cog(DB(bot))
