import asyncio
from typing import Optional

import discord
import httpx
from discord import app_commands
from discord.ext import commands
from TikTokLive import TikTokLiveClient

from config import (
    DISCORD_BOT_TOKEN,
    DISCORD_GUILD_ID,
    SIDE_ANNOUNCEMENTS_CHANNEL_ID,
    LIVE_NOTIFICATION_ROLE_ID,
    TIKTOK_USERNAME,
    TIKTOK_THUMBNAIL_URL,
    TWITCH_USERNAME,
    TWITCH_CLIENT_ID,
    TWITCH_CLIENT_SECRET,
    YOUTUBE_CHANNEL_ID,
    YOUTUBE_API_KEY,
)


class LiveSocialsBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=discord.Intents.default())

    async def setup_hook(self) -> None:
        guild = discord.Object(id=DISCORD_GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        print("Slash commands synced.")


bot = LiveSocialsBot()

live_group = app_commands.Group(
    name="live",
    description="Check whether your social accounts are live",
)

has_checked_on_startup = False


class StreamButtons(discord.ui.View):
    def __init__(self, active_streams: list[dict]) -> None:
        super().__init__(timeout=None)

        for stream in active_streams:
            platform = stream["platform"].upper()

            self.add_item(
                discord.ui.Button(
                    label=f"CLICK HERE TO WATCH ON {platform}",
                    url=stream["url"],
                    style=discord.ButtonStyle.link,
                    emoji=stream.get("emoji", "▶️"),
                )
            )


async def check_tiktok() -> Optional[dict]:
    username = TIKTOK_USERNAME.strip().lstrip("@")

    if not username:
        return None

    try:
        client = TikTokLiveClient(unique_id=f"@{username}")

        if await client.is_live():
            return {
                "platform": "TikTok",
                "emoji": "🎵",
                "url": f"https://www.tiktok.com/@{username}/live",
                "title": "",
                "thumbnail": TIKTOK_THUMBNAIL_URL.strip(),
            }

    except Exception as error:
        print(f"TikTok check failed: {error}")

    return None


async def get_twitch_access_token(
    http: httpx.AsyncClient,
) -> Optional[str]:
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        return None

    try:
        response = await http.post(
            "https://id.twitch.tv/oauth2/token",
            params={
                "client_id": TWITCH_CLIENT_ID,
                "client_secret": TWITCH_CLIENT_SECRET,
                "grant_type": "client_credentials",
            },
        )

        response.raise_for_status()

        return response.json().get("access_token")

    except Exception as error:
        print(f"Twitch authentication failed: {error}")

    return None


async def check_twitch(
    http: httpx.AsyncClient,
) -> Optional[dict]:
    username = TWITCH_USERNAME.strip().lstrip("@")

    if not username:
        return None

    try:
        access_token = await get_twitch_access_token(http)

        if not access_token:
            return None

        response = await http.get(
            "https://api.twitch.tv/helix/streams",
            params={
                "user_login": username,
            },
            headers={
                "Client-ID": TWITCH_CLIENT_ID,
                "Authorization": f"Bearer {access_token}",
            },
        )

        response.raise_for_status()

        streams = response.json().get("data", [])

        if not streams:
            return None

        stream = streams[0]
        thumbnail = stream.get("thumbnail_url", "")

        if thumbnail:
            thumbnail = thumbnail.replace(
                "{width}",
                "1280",
            ).replace(
                "{height}",
                "720",
            )

        return {
            "platform": "Twitch",
            "emoji": "🟣",
            "url": f"https://www.twitch.tv/{username}",
            "title": stream.get("title", ""),
            "thumbnail": thumbnail,
        }

    except Exception as error:
        print(f"Twitch check failed: {error}")

    return None


async def check_youtube(
    http: httpx.AsyncClient,
) -> Optional[dict]:
    if not YOUTUBE_CHANNEL_ID or not YOUTUBE_API_KEY:
        return None

    try:
        response = await http.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "channelId": YOUTUBE_CHANNEL_ID,
                "eventType": "live",
                "type": "video",
                "maxResults": 1,
                "key": YOUTUBE_API_KEY,
            },
        )

        response.raise_for_status()

        items = response.json().get("items", [])

        if not items:
            return None

        item = items[0]
        video_id = item["id"]["videoId"]
        snippet = item.get("snippet", {})
        thumbnails = snippet.get("thumbnails", {})

        thumbnail = (
            thumbnails.get("high", {}).get("url")
            or thumbnails.get("medium", {}).get("url")
            or thumbnails.get("default", {}).get("url", "")
        )

        return {
            "platform": "YouTube",
            "emoji": "🔴",
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "title": snippet.get("title", ""),
            "thumbnail": thumbnail,
        }

    except Exception as error:
        print(f"YouTube check failed: {error}")

    return None


async def check_all_socials() -> list[dict]:
    async with httpx.AsyncClient(timeout=15) as http:
        results = await asyncio.gather(
            check_tiktok(),
            check_twitch(http),
            check_youtube(http),
            return_exceptions=True,
        )

    active_streams = []

    for result in results:
        if isinstance(result, Exception):
            print(f"Social check failed: {result}")
        elif result:
            active_streams.append(result)

    return active_streams


async def get_announcement_channel():
    channel = bot.get_channel(
        SIDE_ANNOUNCEMENTS_CHANNEL_ID
    )

    if channel is not None:
        return channel

    try:
        return await bot.fetch_channel(
            SIDE_ANNOUNCEMENTS_CHANNEL_ID
        )

    except discord.DiscordException as error:
        print(
            f"Could not access #side-announcements: {error}"
        )

    return None


def create_live_embed(
    active_streams: list[dict],
) -> discord.Embed:
    platforms = []

    for stream in active_streams:
        platforms.append(
            f"{stream.get('emoji', '▶️')} "
            f"**LIVE ON {stream['platform'].upper()}**"
        )

    description = (
        "Come join the stream!\n\n"
        + "\n".join(platforms)
        + "\n\nUse the button below to watch."
    )

    embed = discord.Embed(
        title=f"🔴We are live!",
        description=description,
        color=discord.Color.red(),
        timestamp=discord.utils.utcnow(),
    )

    for stream in active_streams:
        thumbnail = stream.get("thumbnail", "").strip()

        if thumbnail:
            embed.set_image(url=thumbnail)
            break

    embed.set_footer(
        text="Live Socials"
    )

    return embed


async def post_offline_status() -> bool:
    channel = await get_announcement_channel()

    if channel is None:
        return False

    embed = discord.Embed(
        title=f"⚫ @{TIKTOK_USERNAME} is not live",
        description="No configured social accounts are currently live.",
        color=discord.Color.dark_grey(),
        timestamp=discord.utils.utcnow(),
    )

    embed.set_footer(text="Live Socials")

    await channel.send(embed=embed)

    return True


async def post_live_announcement(
    active_streams: list[dict],
) -> bool:
    if not active_streams:
        print("No configured social accounts are live.")
        return False

    channel = await get_announcement_channel()

    if channel is None:
        return False

    embed = create_live_embed(active_streams)

    await channel.send(
        content=f"<@&{LIVE_NOTIFICATION_ROLE_ID}>",
        embed=embed,
        view=StreamButtons(active_streams),
        allowed_mentions=discord.AllowedMentions(
            roles=True,
            everyone=False,
            users=False,
        ),
    )

    return True


@live_group.command(
    name="socials",
    description="Check all socials and announce active streams",
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def live_socials(
    interaction: discord.Interaction,
) -> None:
    await interaction.response.defer(
        ephemeral=True
    )

    active_streams = await check_all_socials()

    if not active_streams:
        print("No configured social accounts are live.")

        await interaction.followup.send(
            "None of your configured social accounts are live.",
            ephemeral=True,
        )

        return

    posted = await post_live_announcement(
        active_streams
    )

    if posted:
        await interaction.followup.send(
            "Live announcement posted in #side-announcements.",
            ephemeral=True,
        )
    else:
        await interaction.followup.send(
            "I could not post in #side-announcements.",
            ephemeral=True,
        )


@live_socials.error
async def live_socials_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    if isinstance(
        error,
        app_commands.MissingPermissions,
    ):
        message = (
            "Only moderators with Manage Server "
            "permission can use this command."
        )
    else:
        message = "The live command failed."
        print(f"Slash command failed: {error}")

    if interaction.response.is_done():
        await interaction.followup.send(
            message,
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            message,
            ephemeral=True,
        )


bot.tree.add_command(live_group)


@bot.event
async def on_ready() -> None:
    global has_checked_on_startup

    print(f"Logged in as {bot.user}")
    print("Use /live socials in Discord.")

    if has_checked_on_startup:
        return

    has_checked_on_startup = True

    print("Checking socials on startup...")

    active_streams = await check_all_socials()

    if not active_streams:
        #print("No configured social accounts are live.")
        active_streams.append(
        {
            "platform": "TikTok",
            "emoji": "🎵",
            "url": f"https://www.tiktok.com/@{TIKTOK_USERNAME}/live",
            "title": "",
            "thumbnail": TIKTOK_THUMBNAIL_URL.strip(),
        }
    )
        
        #return

    posted = await post_live_announcement(
        active_streams
    )

    if posted:
        print(
            "Live announcement posted in "
            "#side-announcements."
        )
    else:
        print(
            "Could not post in #side-announcements."
        )


bot.run(DISCORD_BOT_TOKEN)