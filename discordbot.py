import discord
from discord.ext import commands
import pymongo
import os
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
MONGODB_URI = os.getenv('MONGODB_URI')

# MongoDB 클라이언트 초기화
client = pymongo.MongoClient(MONGODB_URI, tls=True, tlsAllowInvalidCertificates=True)
db = client['discordbot']
inventory_collection = db['inventory']
prices_collection = db['prices']

# 인텐트 설정
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

# 봇 객체 생성
bot = commands.Bot(command_prefix='!', intents=intents)

# 데이터베이스 초기화 함수
def init_db():
    if 'inventory' not in db.list_collection_names():
        db.create_collection('inventory')
    if 'prices' not in db.list_collection_names():
        db.create_collection('prices')

# 데이터 로드 함수
def load_inventory():
    inventory = {item['item']: item['quantity'] for item in inventory_collection.find()}
    for item in creatures + items:
        if item not in inventory:
            inventory[item] = 'N/A'
    return inventory

def save_inventory(inventory):
    for item, quantity in inventory.items():
        inventory_collection.update_one({'item': item}, {'$set': {'quantity': quantity}}, upsert=True)

def load_prices():
    prices = {item['item']: {'슘 시세': item['shoom_price'], '현금 시세': item['cash_price']} for item in prices_collection.find()}
    for item in creatures + items:
        if item not in prices:
            prices[item] = {'슘 시세': 'N/A', '현금 시세': 'N/A'}
    return prices

def save_prices(prices):
    for item, price in prices.items():
        prices_collection.update_one({'item': item}, {'$set': {'shoom_price': price['슘 시세'], 'cash_price': price['현금 시세']}}, upsert=True)

@bot.event
async def on_ready():
    global inventory, prices
    try:
        init_db()
        inventory = load_inventory()
        prices = load_prices()
        print(f'Logged in as {bot.user.name} - Inventory and prices loaded.')
        await bot.tree.sync()
    except Exception as e:
        print(f'Error in on_ready: {e}')

# 슬래시 커맨드: 현재 재고 확인
@bot.tree.command(name='inventory', description='Show the current inventory with prices.')
async def show_inventory(interaction: discord.Interaction):
    embed1 = discord.Embed(title="현재 재고 목록 (Creatures Part 1)", color=discord.Color.blue())
    embed2 = discord.Embed(title="현재 재고 목록 (Creatures Part 2)", color=discord.Color.blue())
    embed3 = discord.Embed(title="현재 재고 목록 (Items)", color=discord.Color.green())

    # Creatures 목록 추가 (첫 번째 임베드)
    for item in creatures[:len(creatures)//2]:
        quantity = inventory.get(item, "N/A")
        prices_info = prices.get(item, {"슘 시세": "N/A", "현금 시세": "N/A"})
        shoom_price = prices_info["슘 시세"]
        cash_price = prices_info["현금 시세"]
        embed1.add_field(name=item, value=f"재고: {quantity}개\n슘 시세: {shoom_price}슘\n현금 시세: {cash_price}원", inline=True)

    # Creatures 목록 추가 (두 번째 임베드)
    for item in creatures[len(creatures)//2:]:
        quantity = inventory.get(item, "N/A")
        prices_info = prices.get(item, {"슘 시세": "N/A", "현금 시세": "N/A"})
        shoom_price = prices_info["슘 시세"]
        cash_price = prices_info["현금 시세"]
        embed2.add_field(name=item, value=f"재고: {quantity}개\n슘 시세: {shoom_price}슘\n현금 시세: {cash_price}원", inline=True)

    # Items 목록 추가 (세 번째 임베드)
    for item in items:
        quantity = inventory.get(item, "N/A")
        prices_info = prices.get(item, {"슘 시세": "N/A", "현금 시세": "N/A"})
        shoom_price = prices_info["슘 시세"]
        cash_price = prices_info["현금 시세"]
        embed3.add_field(name=item, value=f"재고: {quantity}개\n슘 시세: {shoom_price}슘\n현금 시세: {cash_price}원", inline=True)

    # 임베드 메시지를 디스코드에 전송
    await interaction.response.send_message(embeds=[embed1, embed2, embed3])

bot.run(DISCORD_BOT_TOKEN)
