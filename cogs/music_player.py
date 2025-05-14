import discord
from discord.ext import commands
import wavelink
import logging
from wavelink.payloads import TrackEventPayload
from wavelink.enums import TrackEventType

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
        was_empty = len(queue) == 0  
        queue.append({"track": track, "ctx": ctx})
        await ctx.send(f"🎶 Añadido a la cola: **{track.title}**")

        if was_empty and not player.is_playing() and not player.is_paused():
            await self.play_next(ctx)

    async def play_next(self, ctx=None, player=None):
        if player is None and ctx is not None:
            player = ctx.voice_client
        if player is None:
            return  

        guild_id = player.guild.id if player else (ctx.guild.id if ctx else None)
        queue = self.queues.get(guild_id, [])
        if queue:
            next_item = queue.pop(0)
            track = next_item["track"]
            track_ctx = next_item["ctx"]
            player.ctx = track_ctx
            await player.play(track)
            await track_ctx.send(f"▶️ Reproduciendo: **{track.title}** (pedido por {track_ctx.author.mention})")
        else:
            if ctx:
                await ctx.send("✅ Cola vacía. Usa el comando `play` para añadir más canciones.")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: TrackEventPayload):
        # Solo nos interesa cuando el evento es END
        if payload.event is not TrackEventType.END:
            return

        player = payload.player
        guild_id = player.guild.id
        queue = self.queues.get(guild_id, [])

        if queue:
            item = queue.pop(0)
            track, ctx = item["track"], item["ctx"]
            player.ctx = ctx
            await player.play(track)
            await ctx.send(f"▶️ Reproduciendo: **{track.title}** (pedido por {ctx.author.mention})")
        else:
            # Opción: notificar al usuario de que la cola está vacía
            await player.ctx.send("✅ Cola vacía. Usa `!play <título>` para añadir más canciones.")

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
            self.queues.pop(ctx.guild.id, None)  
            await ctx.send("👋 Desconectado y cola limpiada.")

    @commands.command(name="queue")
    async def queue_cmd(self, ctx):
        guild_id = ctx.guild.id
        queue = self.queues.get(guild_id, [])
        if not queue:
            await ctx.send("La cola está vacía.")
        else:
            msg = "\n".join(f"{idx+1}. {item['track'].title} (por {item['ctx'].author.display_name})"
                            for idx, item in enumerate(queue))
            await ctx.send(f"🎶 **Cola actual:**\n{msg}")

async def setup(bot):
    await bot.add_cog(MusicPlayerLavalink(bot))