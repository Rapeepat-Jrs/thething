import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import random
from datetime import datetime, timezone

PET_FILE = "pet_data.json"

# ============================================================
# ตั้งค่า
# ============================================================
PET_COST      = 100
LEVEL_UP_COST = 50
STAT_MAX      = 100
DECAY_INTERVAL = 3600
DECAY_AMOUNT   = 5

PETS = [
    {
        "name": "หมา", "emoji": "🐶", "type": "dog",
        "image": "https://i.imgur.com/replace_me_dog.png",
        # ↑ เปลี่ยนเป็น URL รูปหมาที่ต้องการ
    },
    {
        "name": "แมว", "emoji": "🐱", "type": "cat",
        "image": "https://i.imgur.com/replace_me_cat.png",
    },
    {
        "name": "กระต่าย", "emoji": "🐰", "type": "rabbit",
        "image": "https://i.imgur.com/replace_me_rabbit.png",
    },
    {
        "name": "มังกร", "emoji": "🐲", "type": "dragon",
        "image": "https://i.imgur.com/replace_me_dragon.png",
    },
    {
        "name": "แมวน้ำ", "emoji": "🦭", "type": "seal",
        "image": "https://i.imgur.com/replace_me_seal.png",
    },
    {
        "name": "หมีแพนด้า", "emoji": "🐼", "type": "panda",
        "image": "https://i.imgur.com/replace_me_panda.png",
    },
    {
        "name": "จิ้งจอก", "emoji": "🦊", "type": "fox",
        "image": "https://i.imgur.com/replace_me_fox.png",
    },
    {
        "name": "เพนกวิน", "emoji": "🐧", "type": "penguin",
        "image": "https://i.imgur.com/replace_me_penguin.png",
    },
]

# ============================================================
# Helper
# ============================================================
def load_pets() -> dict:
    if os.path.exists(PET_FILE):
        with open(PET_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_pets(data: dict):
    with open(PET_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def pet_key(guild_id, user_id):
    return str(guild_id), str(user_id)

def clamp(val):
    return max(0, min(STAT_MAX, val))

def new_pet(pet_info, name):
    return {
        "name": name, "type": pet_info["type"],
        "emoji": pet_info["emoji"], "species": pet_info["name"],
        "image": pet_info.get("image", ""),   # ← เก็บ URL รูปไว้
        "level": 1, "exp": 0,
        "hp": 100, "hunger": 100, "clean": 100, "happy": 100,
        "last_decay": datetime.now(timezone.utc).isoformat(),
        "last_feed": None, "last_play": None, "last_bath": None,
    }

def apply_decay(pet):
    now = datetime.now(timezone.utc)
    last = datetime.fromisoformat(pet["last_decay"])
    hours = int((now - last).total_seconds() // DECAY_INTERVAL)
    if hours > 0:
        pet["hunger"] = clamp(pet["hunger"] - DECAY_AMOUNT * hours)
        pet["clean"]  = clamp(pet["clean"]  - DECAY_AMOUNT * hours)
        pet["happy"]  = clamp(pet["happy"]  - DECAY_AMOUNT * hours)
        pet["last_decay"] = now.isoformat()
    return pet

def check_cooldown(pet, action, cooldown_sec):
    last = pet.get(f"last_{action}")
    if not last:
        return 0
    elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds()
    return max(0, cooldown_sec - int(elapsed))

def stat_bar(value):
    filled = round(value / 10)
    return "🟩" * filled + "⬛" * (10 - filled) + f" {value}/100"

def mood_emoji(pet):
    avg = (pet["hp"] + pet["hunger"] + pet["clean"] + pet["happy"]) // 4
    if avg >= 80: return "😄"
    if avg >= 60: return "🙂"
    if avg >= 40: return "😐"
    if avg >= 20: return "😢"
    return "😭"

def build_embed(pet, coins=None):
    embed = discord.Embed(
        title=f"{pet['emoji']} {pet['name']} {mood_emoji(pet)}",
        description=f"สายพันธุ์: **{pet['species']}** | Lv.**{pet['level']}** | EXP: **{pet['exp']}**",
        color=discord.Color.blurple(),
    )
    # แสดงรูปสัตว์เลี้ยง
    image_url = pet.get("image", "")
    if image_url and not image_url.endswith("replace_me_dog.png") and "replace_me" not in image_url:
        embed.set_image(url=image_url)
    embed.add_field(name="❤️ HP",         value=stat_bar(pet["hp"]),     inline=False)
    embed.add_field(name="🍖 ความอิ่ม",   value=stat_bar(pet["hunger"]), inline=False)
    embed.add_field(name="🛁 ความสะอาด",  value=stat_bar(pet["clean"]),  inline=False)
    embed.add_field(name="😊 ความสุข",    value=stat_bar(pet["happy"]),  inline=False)
    if coins is not None:
        embed.set_footer(text=f"💰 เหรียญของคุณ: {coins:,}")
    return embed

# ============================================================
# View — ปุ่มทั้งหมด
# ============================================================
class PetView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.user_id  = user_id

    async def _refresh(self, interaction: discord.Interaction):
        """อัพเดท embed หลังทำ action"""
        from cogs.economy import get_coins
        data = load_pets()
        gid, uid = pet_key(self.guild_id, self.user_id)
        pet = data.get(gid, {}).get(uid)
        if not pet:
            await interaction.response.edit_message(content="❌ ไม่พบสัตว์เลี้ยง", embed=None, view=None)
            return
        pet = apply_decay(pet)
        data[gid][uid] = pet
        save_pets(data)
        coins = get_coins(self.guild_id, self.user_id)
        await interaction.response.edit_message(embed=build_embed(pet, coins), view=self)

    # ── ให้อาหาร ──────────────────────────────────────────────
    @discord.ui.button(label="ให้อาหาร", emoji="🍖", style=discord.ButtonStyle.primary, row=0)
    async def feed(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ นี่ไม่ใช่สัตว์เลี้ยงของคุณ", ephemeral=True)
            return
        data = load_pets()
        gid, uid = pet_key(self.guild_id, self.user_id)
        pet = data[gid][uid]
        remaining = check_cooldown(pet, "feed", 1800)
        if remaining > 0:
            m, s = remaining // 60, remaining % 60
            await interaction.response.send_message(f"⏳ รออีก **{m} นาที {s} วินาที**", ephemeral=True)
            return
        pet = apply_decay(pet)
        pet["hunger"] = clamp(pet["hunger"] + 30)
        pet["hp"]     = clamp(pet["hp"] + 10)
        pet["exp"]   += 5
        pet["last_feed"] = datetime.now(timezone.utc).isoformat()
        data[gid][uid] = pet
        save_pets(data)
        await self._refresh(interaction)

    # ── เล่นด้วย ──────────────────────────────────────────────
    @discord.ui.button(label="เล่นด้วย", emoji="🎾", style=discord.ButtonStyle.primary, row=0)
    async def play(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ นี่ไม่ใช่สัตว์เลี้ยงของคุณ", ephemeral=True)
            return
        data = load_pets()
        gid, uid = pet_key(self.guild_id, self.user_id)
        pet = data[gid][uid]
        remaining = check_cooldown(pet, "play", 3600)
        if remaining > 0:
            m, s = remaining // 60, remaining % 60
            await interaction.response.send_message(f"⏳ รออีก **{m} นาที {s} วินาที**", ephemeral=True)
            return
        pet = apply_decay(pet)
        pet["happy"]  = clamp(pet["happy"] + 25)
        pet["hunger"] = clamp(pet["hunger"] - 10)
        pet["exp"]   += 8
        pet["last_play"] = datetime.now(timezone.utc).isoformat()
        data[gid][uid] = pet
        save_pets(data)
        await self._refresh(interaction)

    # ── อาบน้ำ ────────────────────────────────────────────────
    @discord.ui.button(label="อาบน้ำ", emoji="🛁", style=discord.ButtonStyle.primary, row=0)
    async def bath(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ นี่ไม่ใช่สัตว์เลี้ยงของคุณ", ephemeral=True)
            return
        data = load_pets()
        gid, uid = pet_key(self.guild_id, self.user_id)
        pet = data[gid][uid]
        remaining = check_cooldown(pet, "bath", 7200)
        if remaining > 0:
            h, m = remaining // 3600, (remaining % 3600) // 60
            await interaction.response.send_message(f"⏳ รออีก **{h} ชั่วโมง {m} นาที**", ephemeral=True)
            return
        pet = apply_decay(pet)
        pet["clean"] = clamp(pet["clean"] + 40)
        pet["happy"] = clamp(pet["happy"] + 10)
        pet["exp"]  += 5
        pet["last_bath"] = datetime.now(timezone.utc).isoformat()
        data[gid][uid] = pet
        save_pets(data)
        await self._refresh(interaction)

    # ── เลเวลอัพ ──────────────────────────────────────────────
    @discord.ui.button(label="เลเวลอัพ", emoji="⬆️", style=discord.ButtonStyle.success, row=1)
    async def levelup(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ นี่ไม่ใช่สัตว์เลี้ยงของคุณ", ephemeral=True)
            return
        from cogs.economy import get_coins, spend_coins
        data = load_pets()
        gid, uid = pet_key(self.guild_id, self.user_id)
        pet = data[gid][uid]
        required_exp = pet["level"] * 20
        if pet["exp"] < required_exp:
            await interaction.response.send_message(
                f"❌ EXP ไม่พอ! มี **{pet['exp']}** / ต้องการ **{required_exp}**", ephemeral=True
            )
            return
        coins = get_coins(self.guild_id, self.user_id)
        if coins < LEVEL_UP_COST:
            await interaction.response.send_message(
                f"❌ เหรียญไม่พอ! มี **{coins}** / ต้องการ **{LEVEL_UP_COST}**", ephemeral=True
            )
            return
        spend_coins(self.guild_id, self.user_id, LEVEL_UP_COST)
        pet["level"] += 1
        pet["exp"]   -= required_exp
        pet["hp"]     = clamp(pet["hp"] + 20)
        pet["hunger"] = clamp(pet["hunger"] + 20)
        pet["clean"]  = clamp(pet["clean"] + 20)
        pet["happy"]  = clamp(pet["happy"] + 20)
        data[gid][uid] = pet
        save_pets(data)
        await self._refresh(interaction)

    # ── รีเฟรช ────────────────────────────────────────────────
    @discord.ui.button(label="รีเฟรช", emoji="🔄", style=discord.ButtonStyle.secondary, row=1)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ นี่ไม่ใช่สัตว์เลี้ยงของคุณ", ephemeral=True)
            return
        await self._refresh(interaction)

    # ── ปล่อยสัตว์เลี้ยง ─────────────────────────────────────
    @discord.ui.button(label="ปล่อยสัตว์เลี้ยง", emoji="🚪", style=discord.ButtonStyle.danger, row=2)
    async def release(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ นี่ไม่ใช่สัตว์เลี้ยงของคุณ", ephemeral=True)
            return
        data = load_pets()
        gid, uid = pet_key(self.guild_id, self.user_id)
        pet = data.get(gid, {}).get(uid)
        if not pet:
            await interaction.response.send_message("❌ ไม่พบสัตว์เลี้ยง", ephemeral=True)
            return
        # แสดง confirm ก่อนลบ
        embed = discord.Embed(
            title="⚠️ ยืนยันการปล่อยสัตว์เลี้ยง",
            description=f"คุณแน่ใจไหมที่จะปล่อย **{pet['emoji']} {pet['name']}** ?\n\n❗ ข้อมูลจะหายถาวร และไม่สามารถกู้คืนได้",
            color=discord.Color.red(),
        )
        await interaction.response.edit_message(embed=embed, view=ConfirmReleaseView(self.guild_id, self.user_id))

# ============================================================
# View — ยืนยันการปล่อยสัตว์เลี้ยง
# ============================================================
class ConfirmReleaseView(discord.ui.View):
    def __init__(self, guild_id, user_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.user_id  = user_id

    @discord.ui.button(label="ยืนยัน ปล่อยเลย", emoji="✅", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ ไม่ใช่ของคุณ", ephemeral=True)
            return
        data = load_pets()
        gid, uid = pet_key(self.guild_id, self.user_id)
        pet = data.get(gid, {}).get(uid)
        name = f"{pet['emoji']} {pet['name']}" if pet else "สัตว์เลี้ยง"
        data.get(gid, {}).pop(uid, None)
        save_pets(data)
        embed = discord.Embed(
            title="🚪 ปล่อยสัตว์เลี้ยงแล้ว",
            description=f"{name} ได้รับอิสระแล้ว...\n\nใช้ `/pet` เพื่อรับสัตว์เลี้ยงตัวใหม่ได้เลยครับ 🐾",
            color=discord.Color.grayed_out(),
        )
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="ยกเลิก", emoji="↩️", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ ไม่ใช่ของคุณ", ephemeral=True)
            return
        from cogs.economy import get_coins
        data = load_pets()
        gid, uid = pet_key(self.guild_id, self.user_id)
        pet = data.get(gid, {}).get(uid)
        coins = get_coins(self.guild_id, self.user_id)
        await interaction.response.edit_message(embed=build_embed(pet, coins), view=PetView(self.guild_id, self.user_id))


# ============================================================
# Cog
# ============================================================
class PetSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._decay_task = None

    async def cog_load(self):
        self._decay_task = self.bot.loop.create_task(self._decay_loop())

    async def cog_unload(self):
        if self._decay_task:
            self._decay_task.cancel()

    async def _decay_loop(self):
        import asyncio
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            await asyncio.sleep(DECAY_INTERVAL)
            data = load_pets()
            for gid in data:
                for uid in data[gid]:
                    data[gid][uid] = apply_decay(data[gid][uid])
            save_pets(data)

    @app_commands.command(name="pet", description="ดูและดูแลสัตว์เลี้ยงของคุณ")
    async def pet(self, interaction: discord.Interaction):
        print(f"[pet] {interaction.user} เรียกคำสั่ง")
        from cogs.economy import get_coins
        data = load_pets()
        print(f"[pet] โหลดข้อมูลสำเร็จ: {data}")
        gid, uid = pet_key(interaction.guild_id, interaction.user.id)
        pet = data.get(gid, {}).get(uid)
        print(f"[pet] pet = {pet}")

        if not pet:
            coins = get_coins(interaction.guild_id, interaction.user.id)
            print(f"[pet] ไม่มีสัตว์ เหรียญ = {coins}")
            embed = discord.Embed(
                title="🐾 คุณยังไม่มีสัตว์เลี้ยง",
                description=f"ราคา: **{PET_COST} เหรียญ** | เหรียญของคุณ: **{coins:,}**\n\nกดปุ่มด้านล่างเพื่อซื้อสัตว์เลี้ยงสุ่ม!",
                color=discord.Color.grayed_out(),
            )
            await interaction.response.send_message(embed=embed, view=BuyView(interaction.guild_id, interaction.user.id), ephemeral=True)
            print("[pet] ส่ง BuyView สำเร็จ")
            return

        pet = apply_decay(pet)
        data[gid][uid] = pet
        save_pets(data)
        coins = get_coins(interaction.guild_id, interaction.user.id)
        print(f"[pet] มีสัตว์แล้ว กำลังส่ง PetView")
        await interaction.response.send_message(
            embed=build_embed(pet, coins),
            view=PetView(interaction.guild_id, interaction.user.id),
            ephemeral=True,
        )
        print("[pet] ส่ง PetView สำเร็จ")

# ============================================================
# View — ซื้อสัตว์
# ============================================================
class BuyView(discord.ui.View):
    def __init__(self, guild_id, user_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.user_id  = user_id
        self.petname  = None

    @discord.ui.button(label="ซื้อสัตว์เลี้ยง", emoji="🛒", style=discord.ButtonStyle.success)
    async def buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ ไม่ใช่ของคุณ", ephemeral=True)
            return
        await interaction.response.send_modal(BuyModal(self.guild_id, self.user_id))

class BuyModal(discord.ui.Modal, title="ตั้งชื่อสัตว์เลี้ยง"):
    petname = discord.ui.TextInput(label="ชื่อสัตว์เลี้ยง", placeholder="ใส่ชื่อที่ต้องการ", max_length=20)

    def __init__(self, guild_id, user_id):
        super().__init__()
        self.guild_id = guild_id
        self.user_id  = user_id

    async def on_submit(self, interaction: discord.Interaction):
        from cogs.economy import get_coins, spend_coins
        coins = get_coins(self.guild_id, self.user_id)
        if coins < PET_COST:
            await interaction.response.send_message(
                f"❌ เหรียญไม่พอ! มี **{coins}** / ต้องการ **{PET_COST}**", ephemeral=True
            )
            return
        pet_info = random.choice(PETS)
        spend_coins(self.guild_id, self.user_id, PET_COST)
        data = load_pets()
        gid, uid = pet_key(self.guild_id, self.user_id)
        data.setdefault(gid, {})[uid] = new_pet(pet_info, self.petname.value)
        save_pets(data)
        embed = discord.Embed(
            title="🎉 ได้สัตว์เลี้ยงใหม่!",
            description=f"ชื่อ: **{self.petname.value}**\nสายพันธุ์: {pet_info['emoji']} **{pet_info['name']}**\n\nใช้ `/pet` เพื่อดูแลสัตว์เลี้ยงของคุณ!",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(PetSystem(bot))