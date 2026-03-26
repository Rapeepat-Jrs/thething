import discord
from discord import app_commands
from discord.ext import commands
import asyncio

# ============================================================
# ตั้งค่า
# ============================================================
CATEGORY_NAME = "🎙️ ห้องชั่วคราว"  # ชื่อ Category ที่จะสร้างห้องใน
EMPTY_TIMEOUT = 30                   # วินาทีที่รอก่อนลบถ้าไม่มีคนเข้า
VACANT_TIMEOUT = 30                  # วินาทีที่รอก่อนลบเมื่อทุกคนออกไปแล้ว

# เก็บห้องที่สร้างโดยคำสั่งนี้ { channel_id: True }
temp_channels: set[int] = set()

# ============================================================
# Cog
# ============================================================
class VoiceRoom(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /createroom — สร้างห้องเสียงชั่วคราว ─────────────────
    @app_commands.command(name="createroom", description="สร้างห้องเสียงชั่วคราว (ลบอัตโนมัติเมื่อไม่มีคนใช้)")
    @app_commands.describe(
        name="ชื่อห้องที่ต้องการ",
        limit="จำกัดจำนวนคน (0 = ไม่จำกัด)",
    )
    async def createroom(
        self,
        interaction: discord.Interaction,
        name: str,
        limit: int = 0,
    ):
        guild = interaction.guild
        limit = max(0, min(limit, 99))

        # หา Category หรือสร้างใหม่ถ้ายังไม่มี
        category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
        if category is None:
            category = await guild.create_category(CATEGORY_NAME)

        # สร้างห้องเสียง
        channel = await guild.create_voice_channel(
            name=name,
            category=category,
            user_limit=limit,
            reason=f"สร้างโดย {interaction.user.display_name}",
        )
        temp_channels.add(channel.id)

        await interaction.response.send_message(
            f"✅ สร้างห้อง **{name}** เรียบร้อยแล้ว!\n"
            f"📌 {channel.mention}\n"
            f"👥 จำกัด: {'ไม่จำกัด' if limit == 0 else f'{limit} คน'}\n"
            f"⚠️ ห้องจะถูกลบอัตโนมัติถ้าไม่มีคนเข้าใน **{EMPTY_TIMEOUT} วินาที**",
            ephemeral=True,
        )

        # รอดูว่ามีคนเข้าไหมภายใน EMPTY_TIMEOUT วินาที
        await asyncio.sleep(EMPTY_TIMEOUT)

        # โหลดห้องใหม่จาก Discord
        channel = guild.get_channel(channel.id)
        if channel is None:
            return  # ถูกลบไปแล้ว

        if len(channel.members) == 0:
            await self._delete_channel(channel, "ไม่มีคนเข้าใช้งาน")

    # ── Listener — ตรวจจับเมื่อคนออกจากห้อง ──────────────────
    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        # ออกจากห้อง
        if before.channel and before.channel.id in temp_channels:
            channel = before.channel
            if len(channel.members) == 0:
                # รอก่อนลบ เผื่อมีคนเข้าใหม่เดี๋ยวนั้น
                await asyncio.sleep(VACANT_TIMEOUT)
                channel = member.guild.get_channel(channel.id)
                if channel and len(channel.members) == 0:
                    await self._delete_channel(channel, "ไม่มีคนใช้งานแล้ว")

    # ── Helper — ลบห้อง ───────────────────────────────────────
    async def _delete_channel(self, channel: discord.VoiceChannel, reason: str):
        if channel.id not in temp_channels:
            return
        temp_channels.discard(channel.id)
        try:
            await channel.delete(reason=reason)
            print(f"🗑️ ลบห้อง '{channel.name}' — {reason}")
        except discord.NotFound:
            pass  # ถูกลบไปแล้ว
        except discord.Forbidden:
            print(f"❌ ไม่มีสิทธิ์ลบห้อง '{channel.name}'")

async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceRoom(bot))