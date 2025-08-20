import discord
from discord.ext import commands

# ---------- Config ----------
# Optional: limit to specific channel IDs. Leave empty to apply in all channels the bot can see.
CHANNEL_WHITELIST = set()  # e.g., {123456789012345678, 987654321098765432}

# Prevent @everyone/@here from firing again when reposted
ALLOWED_MENTIONS = discord.AllowedMentions(everyone=False, users=True, roles=False)
# ----------------------------

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Cache webhooks per parent text channel (threads use parent)
channel_webhooks = {}

async def get_or_create_webhook(target_channel: discord.TextChannel):
    """
    Get/create one webhook per *text channel* (parent for threads).
    """
    if target_channel.id in channel_webhooks:
        return channel_webhooks[target_channel.id]

    try:
        hooks = await target_channel.webhooks()
        webhook = hooks[0] if hooks else await target_channel.create_webhook(name="MessageReposter")
        channel_webhooks[target_channel.id] = webhook
        return webhook
    except discord.Forbidden:
        print(f"[WARN] Missing Manage Webhooks in #{target_channel} ({target_channel.id})")
    except discord.HTTPException as e:
        print(f"[ERROR] Could not get/create webhook in #{target_channel}: {e}")
    return None

@bot.event
async def on_ready():
    print(f"✅ Bot online as {bot.user} (id={bot.user.id})")

@bot.event
async def on_message(message: discord.Message):
    # 1) Avoid loops / skip bots & webhooks
    if message.author.bot:
        return
    if message.webhook_id is not None:
        return

    # 2) Optional: restrict to whitelist
    if CHANNEL_WHITELIST and message.channel.id not in CHANNEL_WHITELIST:
        return

    # 3) Determine the text channel where the webhook belongs
    channel = message.channel
    thread = None

    # Webhooks belong to parent text channels; we can still send into threads
    if isinstance(channel, discord.Thread):
        thread = channel
        channel = channel.parent  # type: ignore

    # 4) Get/create webhook
    if not isinstance(channel, discord.TextChannel):
        return  # ignore DMs / categories / voice
    webhook = await get_or_create_webhook(channel)
    if webhook is None:
        return

    # 5) Collect attachments (all media/files)
    files = []
    try:
        for att in message.attachments:
            # Preserve spoiler flag if present
            f = await att.to_file(spoiler=att.is_spoiler())
            files.append(f)
    except Exception as e:
        print(f"[WARN] Failed to fetch attachments: {e}")

    # 6) Build display name & avatar
    display_name = message.author.display_name
    avatar_url = message.author.display_avatar.url if message.author.display_avatar else None

    # 7) Preserve reply context (if message is a reply)
    reference_note = ""
    if message.reference and isinstance(message.reference.resolved, discord.Message):
        ref = message.reference.resolved
        reference_note = f"(reply to {ref.author.display_name}) "

    # 8) Send via webhook into same place (thread if applicable)
    try:
        await webhook.send(
            content=(reference_note + message.content) if message.content else reference_note or None,
            username=display_name,
            avatar_url=avatar_url,
            files=files if files else None,
            allowed_mentions=ALLOWED_MENTIONS,
            thread=thread  # will post inside the thread if original was in a thread
        )
    except discord.Forbidden:
        print("[WARN] Webhook send forbidden — missing perms?")
        return
    except discord.HTTPException as e:
        print(f"[ERROR] Webhook send failed: {e}")
        return

    # 9) Delete original message
    try:
        await message.delete()
    except discord.Forbidden:
        print("[WARN] Missing Manage Messages permission to delete.")
    except discord.HTTPException as e:
        print(f"[WARN] Failed to delete original message: {e}")

# Optional: simple health command
@bot.command()
async def ping(ctx):
    await ctx.reply("pong")

# Entry point: token comes from environment in hosting (Railway)
import os
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("❌ Set the DISCORD_TOKEN environment variable.")
else:
    bot.run(TOKEN)
