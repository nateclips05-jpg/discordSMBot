
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN was not found in the .env file")

DISCORD_GUILD_ID = 788483111960051712
SIDE_ANNOUNCEMENTS_CHANNEL_ID = 1525650752096178399
LIVE_NOTIFICATION_ROLE_ID  = 1372288152777261099
# TikTok
TIKTOK_USERNAME = "hiiinate_"
TIKTOK_THUMBNAIL_URL = "https://i.ytimg.com/vi/JtlTOyTZUJc/maxresdefault.jpg"

# Twitchhow 
TWITCH_USERNAME = ""
TWITCH_CLIENT_ID = ""
TWITCH_CLIENT_SECRET = ""

# YouTube
YOUTUBE_CHANNEL_ID = ""
YOUTUBE_API_KEY = ""