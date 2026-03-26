import discord
from discord import app_commands
from discord.ext import commands
import random
import asyncio

# ============================================================
# ตั้งค่า
# ============================================================
CORRECT_REWARD = 10   # เหรียญที่ได้เมื่อตอบถูก
WRONG_PENALTY  = 5    # เหรียญที่หายเมื่อตอบผิด

class GameCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.words_dict = {
            "python":  "งูที่สาย Dev รักและใช้เขียนบอทตัวนี้",
            "macbook": "คอมพิวเตอร์ที่ราคาแรงแต่สเปกโดนใจชาวเรา",
            "java":    "ภาษาโปรแกรมมิ่งที่มีโลโก้เป็นถ้วยกาแฟร้อนๆ",
            "wolfcut": "ทรงผมยอดฮิตที่คุณชอบลองใช้ AI แต่งรูปเปลี่ยนลุค",
            "wifi":    "สิ่งที่หายไปแล้วจะทำให้โลกดับสลายสำหรับสายทำงาน",
        }

    # ── UI ────────────────────────────────────────────────────
    class GameMenu(discord.ui.View):
        def __init__(self, cog, interaction):
            super().__init__(timeout=60)
            self.cog = cog
            self.orig_interaction = interaction

        @discord.ui.button(label="NEXT MISSION", style=discord.ButtonStyle.success, emoji="🎮")
        async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer()
            await self.cog.play_logic(interaction)

    # ── Logic หลัก ────────────────────────────────────────────
    async def play_logic(self, interaction: discord.Interaction):
        from cogs.economy import get_coins, add_coins

        word, hint = random.choice(list(self.words_dict.items()))
        current_coins = get_coins(interaction.guild_id, interaction.user.id)

        frame = discord.Embed(
            title="🎮 --- MISSION CONTROL --- 🎮",
            description=(
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"**[ HINT ]**\n> `{hint}`\n\n"
                f"💰 เหรียญปัจจุบัน: **{current_coins:,}**\n"
                f"✅ ตอบถูก: `+{CORRECT_REWARD}` เหรียญ  "
                f"❌ ตอบผิด: `-{WRONG_PENALTY}` เหรียญ\n\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            ),
            color=0x2f3136,
        )

        if interaction.response.is_done():
            await interaction.followup.send(embed=frame, ephemeral=True)
        else:
            await interaction.response.send_message(embed=frame, ephemeral=True)

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            msg = await self.bot.wait_for("message", check=check, timeout=30.0)
            is_correct = msg.content.lower() == word.lower()

            # อัพเดทเหรียญผ่าน economy.py
            if is_correct:
                new_coins = add_coins(interaction.guild_id, interaction.user.id, CORRECT_REWARD)
                pts_text = f"+{CORRECT_REWARD}"
            else:
                new_coins = add_coins(interaction.guild_id, interaction.user.id, -WRONG_PENALTY)
                pts_text = f"-{WRONG_PENALTY}"

            try:
                await msg.delete()
            except Exception:
                pass

            res_frame = discord.Embed(
                title="✅ SUCCESS" if is_correct else "❌ FAILED",
                description=(
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"**ANSWER:** `{word}`\n"
                    f"**เหรียญ:** `{pts_text}` → รวม **{new_coins:,}** เหรียญ\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━"
                ),
                color=discord.Color.green() if is_correct else discord.Color.red(),
            )
            await interaction.edit_original_response(
                embed=res_frame, view=self.GameMenu(self, interaction)
            )

        except asyncio.TimeoutError:
            await interaction.edit_original_response(
                content="⏰ หมดเวลา!", embed=None, view=self.GameMenu(self, interaction)
            )

    # ── /play ─────────────────────────────────────────────────
    @app_commands.command(name="play", description="เริ่มเกมทายคำศัพท์ (ชนะได้เหรียญ!)")
    async def play(self, interaction: discord.Interaction):
        await self.play_logic(interaction)

async def setup(bot):
    await bot.add_cog(GameCog(bot))