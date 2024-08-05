import discord
from discord.ext import commands
from discord import app_commands
import json
import os

# 인텐트 설정
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

# 봇과의 상호작용을 위한 객체 생성
bot = commands.Bot(command_prefix='!', intents=intents)

# 고정된 아이템 목록
creatures = ["angelic warden", "aolenus", "ardor warden", "boreal warden", "corsarlett", "caldonterrus", "eigion warden", "ghartokus", "golgaroth", "hellion warden", "jhiggo jangl", "jotunhel", "luxces", "lus adarch", "menace", "magnacetus", "mijusuima", "nolumoth", "pacedegon", "parahexilian", "sang toare", "takamorath", "urzuk", "umbraxi", "verdent warden", "whispthera", "woodralone"]
items = ["death gacha token", "revive token", "max growth token", "partial growth token", "strong glimmer token", "appearance change token"]

# 시세 정보 초기화
prices = {item: {"슘 시세": "N/A", "현금 시세": "N/A"} for item in creatures + items}

# 재고 저장소 초기화
inventory = {item: 0 for item in creatures + items}

# 재고 파일 경로
data_folder = os.path.join(os.getcwd(), 'data')
inventory_file = os.path.join(data_folder, 'inventory.json')
prices_file = os.path.join(data_folder, 'prices.json')

def load_inventory():
    """재고를 JSON 파일에서 불러옵니다."""
    if os.path.exists(inventory_file):
        with open(inventory_file, "r") as f:
            return json.load(f)
    else:
        return {item: 0 for item in creatures + items}

def save_inventory():
    """재고를 JSON 파일에 저장합니다."""
    os.makedirs(data_folder, exist_ok=True)
    with open(inventory_file, "w") as f:
        json.dump(inventory, f)

def load_prices():
    """시세를 JSON 파일에서 불러옵니다."""
    if os.path.exists(prices_file):
        with open(prices_file, "r") as f:
            return json.load(f)
    else:
        return {item: {"슘 시세": "N/A", "현금 시세": "N/A"} for item in creatures + items}

def save_prices():
    """시세를 JSON 파일에 저장합니다."""
    os.makedirs(data_folder, exist_ok=True)
    with open(prices_file, "w") as f:
        json.dump(prices, f)

@bot.event
async def on_ready():
    global inventory, prices
    inventory = load_inventory()
    prices = load_prices()
    print(f'Logged in as {bot.user.name}')
    await bot.tree.sync()  # 슬래시 커맨드를 디스코드와 동기화합니다.

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
    inventory[item] += quantity
    save_inventory()
    await interaction.response.send_message(f'{item}(이)가 {quantity}개 추가되었습니다.')

# 슬래시 커맨드: 아이템 제거
@bot.tree.command(name='remove', description='Remove items from the inventory.')
@app_commands.describe(item='The item to remove', quantity='The quantity to remove')
@app_commands.autocomplete(item=autocomplete_item)
async def remove_item(interaction: discord.Interaction, item: str, quantity: int):
    if inventory[item] >= quantity:
        inventory[item] -= quantity
        save_inventory()
        await interaction.response.send_message(f'{item}(이)가 {quantity}개 제거되었습니다.')
    else:
        await interaction.response.send_message(f'{item}(이)의 재고가 부족합니다.')

# 슬래시 커맨드: 시세 업데이트
@bot.tree.command(name='price', description='Update the prices of items.')
@app_commands.describe(item='The item to update', shoem_price='The 슘 price', cash_price='The 현금 price')
@app_commands.autocomplete(item=autocomplete_item)
async def update_price(interaction: discord.Interaction, item: str, shoem_price: str, cash_price: str):
    prices[item]['슘 시세'] = shoem_price
    prices[item]['현금 시세'] = cash_price
    save_prices()
    await interaction.response.send_message(f'{item}(이)의 시세가 업데이트되었습니다.')

# 슬래시 커맨드: 재고 확인
@bot.tree.command(name='inventory', description='Show the current inventory.')
async def show_inventory(interaction: discord.Interaction):
    embed = discord.Embed(title="현재 재고 목록")
    for item, quantity in inventory.items():
        embed.add_field(name=item, value=f'재고: {quantity}', inline=False)
    await interaction.response.send_message(embed=embed)

bot.run('YOUR_BOT_TOKEN')


