import discord
from discord.ext import commands
import os
import random
import sqlite3
from dotenv import load_dotenv

# 1. โหลด Token และเช็กความถูกต้อง
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

if TOKEN is None:
    print("❌ Error: ไม่พบ DISCORD_TOKEN ในไฟล์ .env (เช็กชื่อไฟล์หรือตัวแปรให้ดีนะครับ)")
    exit()

# 2. ระบบฐานข้อมูล SQLite (เก็บคะแนนถาวร)
conn = sqlite3.connect('game_data.db')
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS scores (user_id INTEGER PRIMARY KEY, points INTEGER)')
conn.commit()

def update_score(user_id, pts):
    c.execute("INSERT OR IGNORE INTO scores (user_id, points) VALUES (?, 0)", (user_id,))
    c.execute("UPDATE scores SET points = points + ? WHERE user_id = ?", (pts, user_id))
    conn.commit()

# 3. ตั้งค่าบอท
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# คลังคำศัพท์เกม (เพิ่มคำศัพท์กวนๆ ได้ที่นี่)
words_dict = {
    "python": "งูที่สาย Dev รักและใช้เขียนบอทตัวนี้",
    "macbook": "คอมพิวเตอร์ที่ราคาแรงแต่สเปกโดนใจชาวเรา",
    "database": "ที่เก็บข้อมูลขนาดใหญ่ คล้ายๆ ตู้เอกสารดิจิทัล",
    "github": "ที่ฝากโค้ดระดับโลก มีรูปแมวปลาหมึกเป็นโลโก้",
    "terminal": "หน้าจอดำๆ ที่คุณกำลังใช้รันบอทตัวนี้อยู่",
    "vscode": "Editor ยอดนิยมที่มี Extension ให้เลือกเพียบ"
}

@bot.event
async def on_ready():
    print(f'✅ บอทเกมออนไลน์แล้วในชื่อ: {bot.user.name}')
    print('--- พร้อมเล่นบน macOS แล้ว ---')

# --- คำสั่งเล่นเกม ---
@bot.command()
async def play(ctx):
    word, hint = random.choice(list(words_dict.items()))
    
    embed = discord.Embed(
        title="🎮 เกมทายคำศัพท์มาแล้ว!",
        description=f"**คำใบ้:** `{hint}`\n\n(คุณมีเวลา 30 วินาที พิมพ์ตอบมาได้เลย!)",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)

    def check(m):
        return m.channel == ctx.channel and not m.author.bot

    try:
        msg = await bot.wait_for('message', check=check, timeout=30.0)
        
        if msg.content.lower() == word:
            pts_won = 10
            update_score(msg.author.id, pts_won)
            await msg.reply(f"🎉 ถูกต้องนะคร้าบ! **{word}** รับไป {pts_won} คะแนน!")
        else:
            await msg.reply(f"❌ เสียใจด้วยนะ คำตอบที่ถูกคือ **{word}**")
            
    except:
        await ctx.send(f"⏰ หมดเวลาแล้ว! คำตอบที่ถูกคือ **{word}**")

# --- คำสั่งเช็กคะแนนตัวเอง ---
@bot.command()
async def score(ctx):
    c.execute("SELECT points FROM scores WHERE user_id = ?", (ctx.author.id,))
    res = c.fetchone()
    pts = res[0] if res else 0
    
    embed = discord.Embed(
        title="🏆 สถิติคะแนน",
        description=f"คุณ **{ctx.author.name}** สะสมไปแล้วทั้งหมด **{pts}** คะแนน",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

# --- คำสั่งดูอันดับ (Top 5) ---
@bot.command()
async def rank(ctx):
    c.execute("SELECT user_id, points FROM scores ORDER BY points DESC LIMIT 5")
    top_users = c.fetchall()
    
    text = ""
    for i, (uid, pts) in enumerate(top_users, 1):
        try:
            user = await bot.fetch_user(uid)
            text += f"{i}. {user.name} : {pts} คะแนน\n"
        except:
            text += f"{i}. UserID {uid} : {pts} คะแนน\n"

    embed = discord.Embed(
        title="📊 5 อันดับสูงสุดในเซิร์ฟเวอร์",
        description=text if text else "ยังไม่มีข้อมูลคะแนน",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

# รันบอทด้วย Token จาก .env
bot.run(TOKEN)