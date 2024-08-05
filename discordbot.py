import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import os

# 인텐트 설정
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

# 봇 객체 생성
bot = commands.Bot(command_prefix='!', intents=intents)

# 고정된 아이템 목록
creatures = [
    "angelic warden", "aolenus", "ardor warden", "boreal warden", "corsarlett", 
    "caldonterrus", "eigion warden", "ghartokus", "golgaroth", "hellion warden", 
    "jhiggo jangl", "jotunhel", "luxces", "lus adarch", "menace", "magnacetus", 
    "mijusuima", "nolumoth", "pacedegon", "parahexilian", "sang toare", 
    "takamorath", "urzuk", "umbraxi", "verdent warden", "whispthera", "woodralone"
]
items = [
    "death gacha token", "revive token", "max growth token", "partial growth token", 
    "strong glimmer token", "appearance change token"
]

# 현재 파일 경로
current_path = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(current_path, "data", "inventory_prices.db")

# 데이터베이스 초기화
def init_db():
    if not os.path.exists(os.path.dirname(db_path)):
        os.makedirs(os.path.dirname(db_path))
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            item TEXT PRIMARY KEY,
            quantity INTEGER
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS prices (
            item TEXT PRIMARY KEY,
            shoom_price INTEGER,
            cash_price REAL
        )
    ''')
    conn.commit()
    conn.close()

def load_inventory():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT * FROM inventory')
    inventory = {row[0]: row[1] for row in c.fetchall()}
    for item in creatures + items:
        if item not in inventory:
            inventory[item] = "N/A"
    conn.close()
    return inventory

def save_inventory(inventory):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    for item, quantity in inventory.items():
        c.execute('INSERT OR REPLACE INTO inventory (item, quantity) VALUES (?, ?)', (item, quantity))
    conn.commit()
    conn.close()

def load_prices():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT * FROM prices')
    prices = {row[0]: {"슘 시세": row[1], "현금 시세": row[2]} for row in c.fetchall()}
    for item in creatures + items:
        if item not in prices:
            prices[item] = {"슘 시세": "N/A", "현금 시세": "N/A"}
    conn.close()
    return prices

def save_prices(prices):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    for item, price in prices.items():
        c.execute('INSERT OR REPLACE INTO prices (item, shoom_price, cash_price) VALUES (?, ?, ?)',
                  (item, price["슘 시세"], price["현금 시세"]))
    conn.commit()
    conn.close()

@bot.event
async def on_ready():
    global inventory, prices
    init_db()
    inventory = load_inventory()
    prices = load_prices()
    print(f'Logged in as {bot.user.name}')
    await bot.tree.sync()

# 자동 완성 함수
async def autocomplete_item(interaction: discord.Interaction, current: str):
    items_list = creatures + items
    return [
        app_commands.Choice(name=item, value=item)
        for item in items_list if current.lower() in item.lower()
    ]

# 슬래시 커맨드: 아이템 추가
@bot.tree.command(name='add', description='Add items to the inventory.')
@app_commands.describe(item='The item to add', quantity='The quantity to add')
@app_commands.autocomplete(item=autocomplete_item)
async def add_item(interaction: discord.Interaction, item: str, quantity: int):
    if item in inventory:
        if inventory[item] == "N/A":
            inventory[item] = 0
        inventory[item] += quantity
        save_inventory(inventory)
        await interaction.response.send_message(f'아이템 "{item}"이(가) {quantity}개 추가되었습니다.')
    else:
        await interaction.response.send_message(f'아이템 "{item}"은(는) 사용할 수 없는 아이템입니다.')

# 슬래시 커맨드: 아이템 제거
@bot.tree.command(name='remove', description='Remove items from the inventory.')
@app_commands.describe(item='The item to remove', quantity='The quantity to remove')
@app_commands.autocomplete(item=autocomplete_item)
async def remove_item(interaction: discord.Interaction, item: str, quantity: int):
    if item in inventory and inventory[item] != "N/A":
        if inventory[item] >= quantity:
            inventory[item] -= quantity
            save_inventory(inventory)
            await interaction.response.send_message(f'아이템 "{item}"이(가) {quantity}개 제거되었습니다.')
        else:
            await interaction.response.send_message(f'아이템 "{item}"의 재고가 부족합니다.')
    else:
        await interaction.response.send_message(f'아이템 "{item}"은(는) 사용할 수 없는 아이템입니다.')

# 슬래시 커맨드: 시세 업데이트
@bot.tree.command(name='price', description='Update the price of an item.')
@app_commands.describe(item='The item to update the price for', shoom_price='The new shoom price of the item')
@app_commands.autocomplete(item=autocomplete_item)
async def update_price(interaction: discord.Interaction, item: str, shoom_price: int):
    if item in prices:
        prices[item]["슘 시세"] = shoom_price
        prices[item]["현금 시세"] = shoom_price * 0.7
        save_prices(prices)
        await interaction.response.send_message(f'아이템 "{item}"의 시세가 슘 시세: {shoom_price}슘, 현금 시세: {shoom_price * 0.7}원으로 업데이트되었습니다.')
    else:
        await interaction.response.send_message(f'아이템 "{item}"은(는) 사용할 수 없는 아이템입니다.')

# 슬래시 커맨드: 현재 재고 확인
@bot.tree.command(name='inventory', description='Show the current inventory with prices.')
async def show_inventory(interaction: discord.Interaction):
    embed1 = discord.Embed(title="현재 재고 목록 (Creatures Part 1)", color=discord.Color.blue())
    embed2 = discord.Embed(title="현재 재고 목록 (Creatures Part 2)", color=discord.Color.blue())
    embed3 = discord.Embed(title="현재 재고 목록 (Items)", color=discord.Color.green())

    for item in creatures[:len(creatures)//2]:
        quantity = inventory.get(item, "N/A")
        prices_info = prices.get(item, {"슘 시세": "N/A", "현금 시세": "N/A"})
        shoom_price = prices_info["슘 시세"]
        cash_price = prices_info["현금 시세"]
        embed1.add_field(name=item, value=f"재고: {quantity}\n슘 시세: {shoom_price}슘\n현금 시세: {cash_price}원", inline=True)

    for item in creatures[len(creatures)//2:]:
        quantity = inventory.get(item, "N/A")
        prices_info = prices.get(item, {"슘 시세": "N/A", "현금 시세": "N/A"})
        shoom_price = prices_info["슘 시세"]
        cash_price = prices_info["현금 시세"]
        embed2.add_field(name=item, value=f"재고: {quantity}\n슘 시세: {shoom_price}슘\n현금 시세: {cash_price}원", inline=True)

    for item in items:
        quantity = inventory.get(item, "N/A")
        prices_info = prices.get(item, {"슘 시세": "N/A", "현금 시세": "N/A"})
        shoom_price = prices_info["슘 시세"]
        cash_price = prices_info["현금 시세"]
        embed3.add_field(name=item, value=f"재고: {quantity}\n슘 시세: {shoom_price}슘\n현금 시세: {cash_price}원", inline=True)

    await interaction.response.send_message(embeds=[embed1, embed2, embed3])

# 봇 실행
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
bot.run(TOKEN)




