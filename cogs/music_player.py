import discord
from discord.ext import commands
import wavelink
import logging

logger = logging.getLogger('discord_bot.music_lavalink')

class MusicPlayerLavalink(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.bot.loop.create_task(self.connect_lavalink())

    async def connect_lavalink(self):
        print("Intentando conectar a Lavalink...")  
        try:
            node: wavelink.Node = wavelink.Node(
            uri="lava-v3.ajieblogs.eu.org:443",
            password="https://dsc.gg/ajidevserver",
            secure=True,
            )
            await wavelink.NodePool.connect(client=self.bot, nodes=[node])
            self.bot.lavalink_ready = True
            print("¡Conectado a Lavalink!")  # <-- Depuración
            logger.info("Conectado a Lavalink público")
        except Exception as e:
            print(f"Error conectando a Lavalink: {e}")  # <-- Depuración
            logger.error(f"Error conectando a Lavalink: {e}")

    @commands.command(name="join")
    async def join(self, ctx):
        if not wavelink.NodePool.nodes:
            await ctx.send("⏳ Esperando conexión con el servidor de música. Intenta de nuevo en unos segundos.")
            return
        if not ctx.author.voice:
            await ctx.send("❌ Debes estar en un canal de voz.")
            return
        channel = ctx.author.voice.channel
        player = await channel.connect(cls=wavelink.Player)
        player.ctx = ctx  
        
        if not hasattr(player, "_track_end_connected"):
            player.on('track_end', self._on_track_end)
            player._track_end_connected = True
        await ctx.send(f"Me he unido a {channel.mention}")

    @commands.command(name="play")
    async def play(self, ctx, *, search: str):
        guild_id = ctx.guild.id
        if not ctx.voice_client:
            await ctx.invoke(self.join)
        player: wavelink.Player = ctx.voice_client

        tracks = await wavelink.YouTubeTrack.search(search)
        if not tracks:
            await ctx.send("❌ No se encontraron resultados.")
            return
        track = tracks[0]

        queue = self.queues.setdefault(guild_id, [])
        queue.append(track)
        await ctx.send(f"🎶 Añadido a la cola: **{track.title}**")

        if not player.is_playing() and not player.is_paused():
            await self.play_next(ctx)

    async def play_next(self, ctx):
        guild_id = ctx.guild.id
        player: wavelink.Player = ctx.voice_client
        queue = self.queues.get(guild_id, [])
        if queue:
            next_track = queue.pop(0)
            player.ctx = ctx  
            await player.play(next_track)
            await ctx.send(f"▶️ Reproduciendo: **{next_track.title}**")
        else:
            await ctx.send("✅ Cola vacía. Usa el comando `play` para añadir más canciones.")

    async def _on_track_end(self, player: wavelink.Player, track, reason):
        ctx = getattr(player, "ctx", None)
        if ctx:
            await self.play_next(ctx)

    @commands.command(name="pause")
    async def pause(self, ctx):
        player: wavelink.Player = ctx.voice_client
        if player and player.is_playing():
            await player.pause()
            await ctx.send("⏸️ Pausado.")

    @commands.command(name="resume")
    async def resume(self, ctx):
        player: wavelink.Player = ctx.voice_client
        if player and player.is_paused():
            await player.resume()
            await ctx.send("▶️ Reanudado.")

    @commands.command(name="skip")
    async def skip(self, ctx):
        player: wavelink.Player = ctx.voice_client
        if player and player.is_playing():
            await player.stop()
            await ctx.send("⏭️ Saltado.")
            await self.play_next(ctx)

    @commands.command(name="leave")
    async def leave(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("👋 Desconectado.")

    @commands.command(name="queue")
    async def queue_cmd(self, ctx):
        guild_id = ctx.guild.id
        queue = self.queues.get(guild_id, [])
        if not queue:
            await ctx.send("La cola está vacía.")
        else:
            msg = "\n".join(f"{idx+1}. {track.title}" for idx, track in enumerate(queue))
            await ctx.send(f"🎶 **Cola actual:**\n{msg}")

async def setup(bot):
    await bot.add_cog(MusicPlayerLavalink(bot))