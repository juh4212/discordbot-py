import discord
from discord.ext import commands
from discord import app_commands
import json
import os

# 환경 변수에서 BASE_DIR 가져오기
BASE_DIR = os.getenv('BASE_DIR', '/app/data')

# 인벤토리와 가격 파일의 절대 경로 설정
inventory_file = os.path.join(BASE_DIR, 'inventory.json')
prices_file = os.path.join(BASE_DIR, 'prices.json')

# 인텐트 설정
intents = discord.Intents.default()
intents.messages = True

# 봇과의 상호작용을 위한 객체 생성
bot = commands.Bot(command_prefix='!', intents=intents)

# 고정된 아이템 목록
creatures = ["angelic warden", "aolenus", "ardor warden", "boreal warden", "corsarlett", "caldonterrus", "eigion warden", "ghartokus", "golgaroth", "hellion warden", "jhiggo jangl", "jotunhel", "luxces", "lus adarch", "menace", "magnacetus", "mijusuima", "nolumoth", "pacedegon", "parahexilian", "sang toare", "takamorath", "urzuk", "umbraxi", "verdent warden", "whispthera", "woodralone"]
items = ["death gacha token", "revive token", "max growth token", "partial growth token", "strong glimmer token", "appearance change token"]

# 시세 정보 초기화
prices = {item: {"슘 시세": 0, "현금 시세": 0} for item in creatures + items}

# 재고 저장소 초기화
inventory = {item: 0 for item in creatures + items}

def load_inventory():
    """재고를 JSON 파일에서 불러옵니다."""
    if os.path.exists(inventory_file):
        with open(inventory_file, "r") as f:
            loaded_inventory = json.load(f)
            for item in creatures + items:
                if item not in loaded_inventory:
                    loaded_inventory[item] = 0
            return loaded_inventory
    else:
        return {item: 0 for item in creatures + items}

def save_inventory():
    """재고를 JSON 파일에 저장합니다."""
    with open(inventory_file, "w") as f:
        json.dump(inventory, f)

def load_prices():
    """시세를 JSON 파일에서 불러옵니다."""
    if os.path.exists(prices_file):
        with open(prices_file, "r") as f:
            return json.load(f)
    else:
        return {item: {"슘 시세": 0, "현금 시세": 0} for item in creatures + items}

def save_prices():
    """시세를 JSON 파일에 저장합니다."""
    with open(prices_file, "w") as f:
        json.dump(prices, f)

@bot.event
async def on_ready():
    global inventory, prices
    inventory = load_inventory()
    prices = load_prices()
    print(f'Logged in as {bot.user.name}')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} commands.')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

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
    """고정된 아이템 목록에 아이템을 추가합니다."""
    global inventory
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
    """고정된 아이템 목록에서 아이템을 제거합니다."""
    global inventory
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
@bot.tree.command(name='update_price', description='Update the price of an item.')
@app_commands.describe(item='The item to update the price for', shoom_price='The new shoom price of the item')
@app_commands.autocomplete(item=autocomplete_item)
async def update_price(interaction: discord.Interaction, item: str, shoom_price: int):
    """아이템의 시세를 업데이트합니다."""
    global prices
    if item in prices:
        prices[item]["슘 시세"] = shoom_price
        prices[item]["현금 시세"] = shoom_price * 0.7
        save_prices()
        await interaction.response.send_message(f'아이템 "{item}"의 시세가 슘 시세: {shoom_price}슘, 현금 시세: {shoom_price * 0.7}원으로 업데이트되었습니다.')
    else:
        await interaction.response.send_message(f'아이템 "{item}"은(는) 사용할 수 없는 아이템입니다.')

# 슬래시 커맨드: 시세 확인
@bot.tree.command(name='price', description='Check the price of an item.')
@app_commands.describe(item='The item to check the price for')
@app_commands.autocomplete(item=autocomplete_item)
async def check_price(interaction: discord.Interaction, item: str):
    """아이템의 시세를 확인합니다."""
    global prices
    if item in prices:
        shoom_price = prices[item]["슘 시세"]
        cash_price = prices[item]["현금 시세"]
        await interaction.response.send_message(f'아이템 "{item}"의 시세는 다음과 같습니다:\n슘 시세: {shoom_price}슘\n현금 시세: {cash_price}원')
    else:
        await interaction.response.send_message(f'아이템 "{item}"은(는) 사용할 수 없는 아이템입니다.')

# 슬래시 커맨드: 현재 재고 확인
@bot.tree.command(name='inventory', description='Show the current inventory with prices.')
async def show_inventory(interaction: discord.Interaction):
    """현재 재고를 카테고리별로 임베드 형태로 표시합니다."""
    global inventory, prices
    embed1 = discord.Embed(title="현재 재고 목록 (Creatures Part 1)", color=discord.Color.blue())
    embed2 = discord.Embed(title="현재 재고 목록 (Creatures Part 2)", color=discord.Color.blue())
    embed3 = discord.Embed(title="현재 재고 목록 (Items)", color=discord.Color.green())

    # Creatures 목록 추가 (첫 번째 임베드)
    for item in creatures[:len(creatures)//2]:
        quantity = inventory[item]
        prices_info = prices.get(item, {"슘 시세": "N/A", "현금 시세": "N/A"})
        shoom_price = prices_info["슘 시세"]
        cash_price = prices_info["현금 시세"]
        embed1.add_field(name=item, value=f"재고: {quantity}개\n슘 시세: {shoom_price}슘\n현금 시세: {cash_price}원", inline=True)

    # Creatures 목록 추가 (두 번째 임베드)
    for item in creatures[len(creatures)//2:]:
        quantity = inventory[item]
        prices_info = prices.get(item, {"슘 시세": "N/A", "현금 시세": "N/A"})
        shoom_price = prices_info["슘 시세"]
        cash_price = prices_info["현금 시세"]
        embed2.add_field(name=item, value=f"재고: {quantity}개\n슘 시세: {shoom_price}슘\n현금 시세: {cash_price}원", inline=True)

    # Items 목록 추가 (세 번째 임베드)
    for item in items:
        quantity = inventory[item]
        prices_info = prices.get(item, {"슘 시세": "N/A", "현금 시세": "N/A"})
        shoom_price = prices_info["슘 시세"]
        cash_price = prices_info["현금 시세"]
        embed3.add_field(name=item, value=f"재고: {quantity}개\n슘 시세: {shoom_price}슘\n현금 시세: {cash_price}원", inline=True)

    # 임베드 메시지를 디스코드에 전송
    await interaction.response.send_message(embeds=[embed1, embed2, embed3])

# 봇 실행
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
if TOKEN:
    bot.run(TOKEN)
else:
    print("DISCORD_BOT_TOKEN 환경 변수를 설정하세요.")



