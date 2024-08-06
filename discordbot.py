import discord
from discord.ext import commands
from pymongo import MongoClient
import os

# 환경 변수에서 MongoDB URI를 가져옵니다.
MONGO_URI = os.getenv('MONGO_URI')
if MONGO_URI is None:
    raise ValueError("MONGO_URI 환경 변수가 설정되지 않았습니다.")

# MongoDB 클라이언트 설정
client = MongoClient(MONGO_URI)
db = client['discordbot']  # 데이터베이스 선택
inventory_collection = db['inventory']
prices_collection = db['prices']

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

def load_inventory():
    inventory = {}
    for item in creatures + items:
        data = inventory_collection.find_one({"item": item})
        if data:
            inventory[item] = data['quantity']
        else:
            inventory[item] = "N/A"
            print(f"No inventory data for {item}. Defaulting to 'N/A'.")
    return inventory

def save_inventory(inventory):
    for item, quantity in inventory.items():
        inventory_collection.update_one(
            {"item": item}, 
            {"$set": {"quantity": quantity}}, 
            upsert=True
        )

def load_prices():
    prices = {}
    for item in creatures + items:
        data = prices_collection.find_one({"item": item})
        if data:
            prices[item] = {"슘 시세": data['shoom_price'], "현금 시세": data['cash_price']}
        else:
            prices[item] = {"슘 시세": "N/A", "현금 시세": "N/A"}
            print(f"No pricing data for {item}. Defaulting to 'N/A'.")
    return prices

def save_prices(prices):
    for item, price in prices.items():
        prices_collection.update_one(
            {"item": item}, 
            {"$set": {"shoom_price": price['슘 시세'], "cash_price": price['현금 시세']}}, 
            upsert=True
        )

@bot.event
async def on_ready():
    global inventory, prices
    try:
        inventory = load_inventory()
        prices = load_prices()
        print(f'Logged in as {bot.user.name} - Inventory and prices loaded.')
        await bot.tree.sync()
    except Exception as e:
        print(f'Error in on_ready: {e}')

# 자동 완성 기능 구현
async def autocomplete_items(interaction: discord.Interaction, current: str):
    all_items = creatures + items
    return [discord.app_commands.Choice(name=item, value=item) for item in all_items if current.lower() in item.lower()]

# 슬래시 커맨드: 아이템 추가
@bot.tree.command(name='add', description='Add items to the inventory.')
@discord.app_commands.describe(item='The item to add', quantity='The quantity to add')
@discord.app_commands.autocomplete(item=autocomplete_items)
async def add_item(interaction: discord.Interaction, item: str, quantity: int):
    if item in creatures + items:
        current_quantity = inventory.get(item, "N/A")
        if current_quantity == "N/A":
            inventory[item] = quantity
        else:
            inventory[item] += quantity
        save_inventory(inventory)
        await interaction.response.send_message(f'Item "{item}" added: {quantity} units.')
    else:
        await interaction.response.send_message(f'Item "{item}" is not recognized.')

# 슬래시 커맨드: 아이템 제거
@bot.tree.command(name='remove', description='Remove items from the inventory.')
@discord.app_commands.describe(item='The item to remove', quantity='The quantity to remove')
@discord.app_commands.autocomplete(item=autocomplete_items)
async def remove_item(interaction: discord.Interaction, item: str, quantity: int):
    if item in creatures + items:
        current_quantity = inventory.get(item, "N/A")
        if current_quantity == "N/A":
            await interaction.response.send_message(f'No "{item}" in inventory.')
        elif current_quantity < quantity:
            await interaction.response.send_message(f'Not enough "{item}" in inventory.')
        else:
            inventory[item] -= quantity
            save_inventory(inventory)
            await interaction.response.send_message(f'Item "{item}" removed: {quantity} units.')
    else:
        await interaction.response.send_message(f'Item "{item}" is not recognized.')

# 슬래시 커맨드: 시세 업데이트
@bot.tree.command(name='price', description='Update the price of an item.')
@discord.app_commands.describe(item='The item to update the price for', shoom_price='The new shoom price of the item')
@discord.app_commands.autocomplete(item=autocomplete_items)
async def update_price(interaction: discord.Interaction, item: str, shoom_price: int):
    if item in creatures + items:
        prices[item] = {"슘 시세": shoom_price, "현금 시세": shoom_price * 0.7}
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

    # Creatures 목록 추가 (첫 번째 임베드)
    for item in creatures[:len(creatures)//2]:
        quantity = inventory.get(item, "N/A")
        prices_info = prices.get(item, {"슘 시세": "N/A", "현금 시세": "N/A"})
        shoom_price = prices_info["슘 시세"]
        cash_price = prices_info["현금 시세"]
        embed1.add_field(name=item, value=f"재고: {quantity}\n슘 시세: {shoom_price}슘\n현금 시세: {cash_price}원", inline=True)

    # Creatures 목록 추가 (두 번째 임베드)
    for item in creatures[len(creatures)//2:]:
        quantity = inventory.get(item, "N/A")
        prices_info = prices.get(item, {"슘 시세": "N/A", "현금 시세": "N/A"})
        shoom_price = prices_info["슘 시세"]
        cash_price = prices_info["현금 시세"]
        embed2.add_field(name=item, value=f"재고: {quantity}\n슘 시세: {shoom_price}슘\n현금 시세: {cash_price}원", inline=True)

    # Items 목록 추가 (세 번째 임베드)
    for item in items:
        quantity = inventory.get(item, "N/A")
        prices_info = prices.get(item, {"슘 시세": "N/A", "현금 시세": "N/A"})
        shoom_price = prices_info["슘 시세"]
        cash_price = prices_info["현금 시세"]
        embed3.add_field(name=item, value=f"재고: {quantity}\n슘 시세: {shoom_price}슘\n현금 시세: {cash_price}원", inline=True)

    # 임베드 메시지를 디스코드에 전송
    await interaction.response.send_message(embeds=[embed1, embed2, embed3])

# 슬래시 커맨드: 판매 메시지 생성
@bot.tree.command(name='sell_message', description='Generate the sell message.')
async def sell_message(interaction: discord.Interaction):
    """판매 메시지를 생성합니다."""
    creatures_message = "ㅡㅡ소나리아ㅡㅡ\n\n계좌로 팔아요!!\n\n<크리쳐>\n"
    items_message = "\n<아이템>\n"

    # Creatures 목록 추가
    for item in creatures:
        prices_info = prices.get(item, {"현금 시세": "N/A"})
        cash_price = prices_info["현금 시세"]
        if cash_price != "N/A":
            display_price = round(float(cash_price) * 0.0001, 2)
        else:
            display_price = "N/A"
        creatures_message += f"• {item.title()} {display_price}\n"

    # Items 목록 추가
    for item in items:
        prices_info = prices.get(item, {"현금 시세": "N/A"})
        cash_price = prices_info["현금 시세"]
        if cash_price != "N/A":
            display_price = round(float(cash_price) * 0.0001, 2)
        else:
            display_price = "N/A"
        items_message += f"• {item.title()} {display_price}\n"

    # 필수 메시지 추가
    final_message = creatures_message + items_message + "\n• 문상 X  계좌 O\n• 구매를 원하시면 갠으로! \n• 재고는 갠디로 와서 물어봐주세요!"
    
    await interaction.response.send_message(final_message)

# 환경 변수에서 토큰을 가져옵니다.
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
if TOKEN is None:
    raise ValueError("DISCORD_BOT_TOKEN 환경 변수가 설정되지 않았습니다.")
bot.run(TOKEN)

