import discord
from discord.ext import commands
from discord import app_commands
import json
import os

# 데이터 폴더 경로 설정
data_folder = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(data_folder, exist_ok=True)

inventory_file = os.path.join(data_folder, "inventory.json")
prices_file = os.path.join(data_folder, "prices.json")

# 초기 데이터 생성
if not os.path.exists(inventory_file):
    with open(inventory_file, 'w') as f:
        json.dump({item: 0 for item in creatures + items}, f)

if not os.path.exists(prices_file):
    with open(prices_file, 'w') as f:
        json.dump({item: {"슘 시세": 0, "현금 시세": 0} for item in creatures + items}, f)

def load_inventory():
    with open(inventory_file, "r") as f:
        return json.load(f)

def save_inventory():
    with open(inventory_file, "w") as f:
        json.dump(inventory, f)

def load_prices():
    with open(prices_file, "r") as f:
        return json.load(f)

def save_prices():
    with open(prices_file, "w") as f:
        json.dump(prices, f)

# 인텐트 설정
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

creatures = ["angelic warden", "aolenus", "ardor warden", "boreal warden", "corsarlett", "caldonterrus", "eigion warden", "ghartokus", "golgaroth", "hellion warden", "jhiggo jangl", "jotunhel", "luxces", "lus adarch", "menace", "magnacetus", "mijusuima", "nolumoth", "pacedegon", "parahexilian", "sang toare", "takamorath", "urzuk", "umbraxi", "verdent warden", "whispthera", "woodralone"]
items = ["death gacha token", "revive token", "max growth token", "partial growth token", "strong glimmer token", "appearance change token"]

inventory = load_inventory()
prices = load_prices()

@bot.event
async def on_ready():
    global inventory, prices
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
        inventory[item] += quantity
        save_inventory()
        await interaction.response.send_message(f'아이템 "{item}"이(가) {quantity}개 추가되었습니다.')
    else:
        await interaction.response.send_message(f'아이템 "{item}"은(는) 사용할 수 없는 아이템입니다.')

# 슬래시 커맨드: 아이템 제거
@bot.tree.command(name='remove', description='Remove items from the inventory.')
@app_commands.describe(item='The item to remove', quantity='The quantity to remove')
@app_commands.autocomplete(item=autocomplete_item)
async def remove_item(interaction: discord.Interaction, item: str, quantity: int):
    if item in inventory:
        if inventory[item] >= quantity:
            inventory[item] -= quantity
            save_inventory()
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
        save_prices()
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
        embed1.add_field(name=item, value=f"재고: {quantity}개\n슘 시세: {shoom_price}슘\n현금 시세: {cash_price}원", inline=True)

    for item in creatures[len(creatures)//2:]:
        quantity = inventory.get(item, "N/A")
        prices_info = prices.get(item, {"슘 시세": "N/A", "현금 시세": "N/A"})
        shoom_price = prices_info["슘 시세"]
        cash_price = prices_info["현금 시세"]
        embed2.add_field(name=item, value=f"재고: {quantity}개\n슘 시세: {shoom_price}슘\n현금 시세: {cash_price}원", inline=True)

    for item in items:
        quantity = inventory.get(item, "N/A")
        prices_info = prices.get(item, {"슘 시세": "N/A", "현금 시세": "N/A"})
        shoom_price = prices_info["슘 시세"]
        cash_price = prices_info["현금 시세"]
        embed3.add_field(name=item, value=f"재고: {quantity}개\n슘 시세: {shoom_price}슘\n현금 시세: {cash_price}원", inline=True)

    await interaction.response.send_message(embeds=[embed1, embed2, embed3])

TOKEN = os.getenv('DISCORD_BOT_TOKEN')
bot.run(TOKEN)

