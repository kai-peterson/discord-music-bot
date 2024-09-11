import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
import os
import tempfile

def get_token_from_env():
    with open('.env', 'r') as env_file:
        for line in env_file:
            if line.startswith('DISCORD_TOKEN='):
                return line.split('=')[1].strip()
    raise ValueError("DISCORD_TOKEN not found in .env file")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

ytdl_format_options = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'outtmpl': os.path.join(tempfile.gettempdir(), '%(extractor)s-%(id)s-%(title)s.%(ext)s'),
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = ""

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
            if 'entries' in data:
                data = data['entries'][0]
            filename = data['url'] if stream else ytdl.prepare_filename(data)
            print(f"Attempting to access file: {filename}")
            return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
        except Exception as e:
            print(f"Error in YTDLSource.from_url: {str(e)}")
            print(f"Current working directory: {os.getcwd()}")
            print(f"Temp directory: {tempfile.gettempdir()}")
            raise

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                try:
                    await ctx.author.voice.channel.connect()
                except discord.errors.ClientException:
                    await ctx.send("I'm already in a voice channel.")
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")
        elif ctx.voice_client.is_playing():
            ctx.voice_client.stop()

    @commands.command()
    async def play(self, ctx, *, url):
        """Plays a song from a given url."""
        try:
            await self.ensure_voice(ctx)
            async with ctx.typing():
                player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
                ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)
            await ctx.send(f'Now playing: {player.title}')
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")
            print(f"Error in play command: {str(e)}")

    @commands.command()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
        else:
            await ctx.send("I'm not connected to a voice channel.")

async def setup(bot):
    await bot.add_cog(Music(bot))

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await setup(bot)

bot.run(get_token_from_env())