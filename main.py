from dotenv import load_dotenv
from discord.ext import commands
import discord
import os


cogs = ['bandori']

load_dotenv()
token = os.getenv('TOKEN')
bot = commands.Bot(command_prefix=';')

for cog in [ 'cogs.' + _ for _ in cogs]:
    try:
        bot.load_extension(cog)
    except Exception as e:
        print(e)

@bot.event
async def on_ready():
    print('Connected\nLogged in as', bot.user.name,
        bot.user.id)
    await bot.change_presence(activity = discord.Game('prefix ;'))

@bot.command(pass_context=True)
@commands.has_permissions(administrator=True)
async def clean(ctx, limit: int):
    await ctx.channel.purge(limit=limit)


@bot.command(name='quit')
@commands.is_owner()
async def quit(ctx):
    await ctx.message.delete()
    await bot.close()

@bot.command(name='load')
@commands.is_owner()
async def load(ctx, msg):
    try:
        bot.load_extension('cogs.' + msg)
        await ctx.message.delete()
    except Exception as e:
        print(e)

@bot.command(name='unload')
@commands.is_owner()
async def unload(ctx, msg):
    try:
        bot.unload_extension('cogs.' + msg)
        await ctx.message.delete()
    except Exception as e:
        print(e)

bot.run(token)
