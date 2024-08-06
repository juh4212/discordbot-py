import discord
from discord.ext import commands
import sqlite3
import os

# 데이터베이스 경로 설정
db_path = os.path.join(os.path.dirname(__file__), 'bot_data.db')

# 데이터베이스 초기화 함수
def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS inventory (
                        item TEXT PRIMARY KEY,
                        quantity INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS prices (
                        item TEXT PRIMARY KEY,
                        shoom_price INTEGER,
                        cash_price INTEGER)''')
    conn.commit()
    conn.close()

# 인텐트 설정
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

# 봇 객체 생성
bot = commands.Bot(command_prefix='!', intents=intents)

# 고정된 아이템 목록
creatures = [
    "angelic warden", "aolenus", "ardor warden", "boreal warden", "caldonterrus", "corsarlett", 
    "eigion warden", "ghartokus", "golgaroth", "hellion warden", "jhiggo jangl", "jotunhel", 
    "luxces", "lus adarch", "magnacetus", "menace", "mijusuima", "nolumoth", "pacedegon", 
    "parahexilian", "sang toare", "takamorath", "umbraxi", "urzuk", "verdent warden", 
    "voletexius", "whispthera", "woodralone", "yohsog"
]
items = ["death gacha token", "revive token", "max growth token", "partial growth token", "strong glimmer token", "appearance change token"]

# 데이터 로드 함수
def load_inventory():
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM inventory")
        rows = cursor.fetchall()
        inventory = {row[0]: row[1] for row in rows}
        for item in creatures + items:
            if item not in inventory:
                inventory[item] = "N/A"
        conn.close()
        return inventory
    except Exception as e:
        print(f'Error loading inventory: {e}')
        return {item: "N/A" for item in creatures + items}

def save_inventory(inventory):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for item, quantity in inventory.items():
            cursor.execute("REPLACE INTO inventory (item, quantity) VALUES (?, ?)", (item, quantity))
        conn.commit()
        conn.close()
        print("Inventory saved successfully.")
    except Exception as e:
        print(f'Error saving inventory: {e}')

def load_prices():
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM prices")
        rows = cursor.fetchall()
        prices = {row[0]: {"슘 시세": row[1], "현금 시세": row[2]} for row in rows}
        for item in creatures + items:
            if item not in prices:
                prices[item] = {"슘 시세": "N/A", "현금 시세": "N/A"}
        conn.close()
        return prices
    except Exception as e:
        print(f'Error loading prices: {e}')
        return {item: {"슘 시세": "N/A", "현금 시세": "N/A"} for item in creatures + items}

def save_prices(prices):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for item, price in prices.items():
            cursor.execute("REPLACE INTO prices (item, shoom_price, cash_price) VALUES (?, ?, ?)", (item, price["슘 시세"], price["현금 시세"]))
        conn.commit()
        conn.close()
        print("Prices saved successfully.")
    except Exception as e:
        print(f'Error saving prices: {e}')

@bot.event
async def on_ready():
    global inventory, prices
    try:
        init_db()
        inventory = load_inventory()
        prices = load_prices()
        print(f'Logged in as {bot.user.name} - Inventory and prices loaded.')
        await bot.tree.sync()  # 슬래시 커맨드를 디스코드와 동기화합니다.
    except Exception as e:
        print(f'Error in on_ready: {e}')

# 이하 슬래시 커맨드와 추가적인 기능들은 기존 코드와 동일하게 이어갑니다.

# 환경 변수에서 토큰을 가져옵니다.
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
if TOKEN is None:
    raise ValueError("DISCORD_BOT_TOKEN 환경 변수가 설정되지 않았습니다.")
bot.run(TOKEN)



