from discord.ext import commands


def is_in_guilds(*guild_ids):
    def predicate(ctx):
        guild = ctx.guild
        if guild is None:
            return False
        return guild.id in guild_ids

    return commands.check(predicate)
