import discord
from discord.ext import commands
import os

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("❌ No DISCORD_TOKEN found in environment!")
    exit(1)

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

@bot.event
async def on_ready():
    print(f"✅ Bot online as {bot.user} (id={bot.user.id})")

@bot.command()
async def ping(ctx):
    await ctx.reply("pong")

bot.run(TOKEN)





