import os
import random
import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
import re
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import threading
import time
from decimal import Decimal, ROUND_HALF_UP  # ROUND_HALF_UP 추가

# 환경 변수 로드
load_dotenv()

# MongoDB 연결 설정
MONGODB_URI = os.getenv('MONGODB_URI')
client = MongoClient(MONGODB_URI, tls=True, tlsAllowInvalidCertificates=True)
db = client.creatures_db
inventory_collection = db['inventory']
prices_collection = db['prices']

# 고정된 아이템 목록
creatures = [
    "angelic warden", "aolenus", "ardor warden", "boreal warden", "caldonterrus", "corsarlett", 
    "eigion warden", "ghartokus", "golgaroth", "hellion warden", "jhiggo jangl", "jotunhel", 
    "luxces", "lus adarch", "magnacetus", "menace", "mijusuima", "nolumoth", "pacedegon", 
    "parahexilian", "sang toare", "takamorath", "umbraxi", "urzuk", "verdent warden", 
    "voletexius", "whispthera", "woodralone", "yohsog"
]
items = ["death gacha token", "revive token", "max growth token", "partial growth token", "strong glimmer token", "appearance change token"]

# 타임 슬립과 랜덤 유니폼 적용
def random_sleep(min_sleep=3, max_sleep=5):
    time.sleep(random.uniform(min_sleep, max_sleep))

# 유저 에이전트와 추가 헤더 설정
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9'
}

# 소수점 셋째 자리를 반올림하여 둘째 자리로 올리고, 0, 2, 또는 5로 설정하는 함수
def round_to_nearest(value):
    rounded_value = Decimal(value).quantize(Decimal('0.00'))
    second_digit = int(rounded_value * 100) % 10
    
    if second_digit <= 2:
        rounded_value = rounded_value - Decimal(second_digit) / 100
    elif second_digit <= 4:
        rounded_value = rounded_value - Decimal(second_digit) / 100 + Decimal('0.05')
    elif second_digit <= 7:
        rounded_value = rounded_value - Decimal(second_digit) / 100 + Decimal('0.05')
    else:
        rounded_value = rounded_value + Decimal('0.1') - Decimal(second_digit) / 100
    
    return float(rounded_value)

# 소수점 넷째 자리를 반올림하여 세 번째 자리로 만드는 함수
def round_to_three_decimal_places(value):
    return float(Decimal(value).quantize(Decimal('0.000'), rounding=ROUND_HALF_UP))

# 크리쳐 가격 정보를 웹 스크래핑하는 함수
def fetch_creature_prices():
    url = 'https://www.game.guide/creatures-of-sonaria-value-list'
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    creature_data = []

    table = soup.find('table')
    if not table:
        print("Table not found in the web page.")
        return creature_data

    rows = table.find_all('tr')[1:]

    for row in rows:
        random_sleep()  # 각 요청 사이에 랜덤한 대기 시간 추가
        cols = row.find_all('td')
        if len(cols) >= 2:
            name = cols[0].text.strip().lower()
            value = cols[1].text.strip().lower()
            
            if '~' in value:
                range_values = re.findall(r'\d+', value)
                if range_values:
                    median_value = (int(range_values[0]) + int(range_values[1])) / 2
                    value = f"{median_value}k"
            
            creature_data.append({"name": name, "value": value})

    return creature_data

# MongoDB 업데이트 함수
def update_database(creature_data):
    for creature in creature_data:
        db.creatures.update_one({'name': creature['name']}, {'$set': {'shoom_price': creature['value']}}, upsert=True)
    print("Database updated with the latest creature prices.")

# Discord 봇 설정
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

async def fetch_prices_from_api():
    url = 'http://localhost:5000/creature_prices'
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return []

@bot.event
async def on_ready():
    global inventory, prices
    try:
        inventory = load_inventory()
        prices = load_prices()
        print(f'Logged in as {bot.user.name} - Inventory and prices loaded.')
        await setup_slash_commands()
    except Exception as e:
        print(f'Error in on_ready: {e}')

@bot.command(name='price')
async def fetch_price(ctx, *, creature_name: str):
    prices = await fetch_prices_from_api()
    for creature in prices:
        if creature['name'] == creature_name.lower():
            value = creature['shoom_price']
            await ctx.send(f"{creature['name'].title()} - 중간값: {value}")
            return
    await ctx.send(f"Creature {creature_name} not found.")

# 자동 완성 기능 구현
async def autocomplete_items(interaction: discord.Interaction, current: str):
    all_items = creatures + items
    # 최대 25개의 자동완성 옵션으로 제한
    return [app_commands.Choice(name=item, value=item) for item in all_items if current.lower() in item.lower()][:25]

# 슬래시 커맨드: 아이템 추가
@bot.tree.command(name='add', description='Add items to the inventory.')
@app_commands.describe(item='The item to add', quantity='The quantity to add')
@app_commands.autocomplete(item=autocomplete_items)
async def add_item(interaction: discord.Interaction, item: str, quantity: int):
    if item in creatures + items:
        current_quantity = inventory.get(item, "N/A")
        if current_quantity == "N/A":
            inventory[item] = quantity
        else:
            inventory[item] = int(current_quantity) + quantity
        save_inventory(inventory)
        await interaction.response.send_message(f'Item "{item}" added: {quantity} units.')
    else:
        await interaction.response.send_message(f'Item "{item}" is not recognized.')

# 슬래시 커맨드: 아이템 제거
@bot.tree.command(name='remove', description='Remove items from the inventory.')
@app_commands.describe(item='The item to remove', quantity='The quantity to remove')
@app_commands.autocomplete(item=autocomplete_items)
async def remove_item(interaction: discord.Interaction, item: str, quantity: int):
    if item in creatures + items:
        current_quantity = inventory.get(item, "N/A")
        if current_quantity != "N/A" and int(current_quantity) >= quantity:
            inventory[item] = int(current_quantity) - quantity
            save_inventory(inventory)
            await interaction.response.send_message(f'Item "{item}" removed: {quantity} units.')
        else:
            await interaction.response.send_message(f'Not enough "{item}" in inventory.')
    else:
        await interaction.response.send_message(f'Item "{item}" is not recognized.')

# 슬래시 커맨드: 시세 업데이트
@bot.tree.command(name='price', description='Update the price of an item.')
@app_commands.describe(item='The item to update the price for', shoom_price='The new shoom price of the item')
@app_commands.autocomplete(item=autocomplete_items)
async def update_price(interaction: discord.Interaction, item: str, shoom_price: int):
    if item in creatures + items:
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

# 슬래시 커맨드: 판매 메시지 생성
@bot.tree.command(name='sell_message', description='Generate the sell message.')
async def sell_message(interaction: discord.Interaction):
    """판매 메시지를 생성합니다."""
    rate_message = "슘 1K당 0.07\n"  # 새로운 환율 정보
    creatures_message = "ㅡㅡ소나리아ㅡㅡ\n\n계좌로 팔아요!!\n\n" + rate_message + "<크리쳐>\n"

    # 크리처 목록을 순회하면서 메시지 구성
    for item in creatures:
        quantity = inventory.get(item, "N/A")
        prices_info = prices.get(item, {"현금 시세": "N/A"})
        cash_price = prices_info["현금 시세"]
        if cash_price != "N/A":
            display_price = round_to_nearest(float(cash_price) * 0.0001)  # 수정된 반올림 함수 적용
        else:
            display_price = "N/A"
        creatures_message += f"• {item.title()} {display_price} (재고 {quantity})\n"

    # 아이템 목록 메시지 구성
    items_message = "\n<아이템>\n"
    for item in items:
        quantity = inventory.get(item, "N/A")
        prices_info = prices.get(item, {"현금 시세": "N/A"})
        cash_price = prices_info["현금 시세"]
        if cash_price != "N/A":
            display_price = round_and_adjust(float(cash_price) * 0.0001)  # 소수점 네 번째 자리 반올림 및 조정 적용
        else:
            display_price = "N/A"
        items_message += f"• {item.title()} {display_price} (재고 {quantity})\n"

    # 필수 메시지 추가
    final_message = creatures_message + items_message + "\n• 문상 X  계좌 O\n• 구매를 원하시면 갠으로! \n• 재고는 갠디로 와서 물어봐주세요!"

    await interaction.response.send_message(final_message)

# 슬래시 명령어를 추가하기 위해 bot에 명령어를 등록
async def setup_slash_commands():
    guild = discord.Object(id=os.getenv('GUILD_ID'))
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)
    print(f'Slash commands synced for guild ID: {guild.id}')

# 데이터 로드 함수
def load_inventory():
    try:
        inventory_data = inventory_collection.find({})
        inventory = {item['item']: item['quantity'] for item in inventory_data}
        for item in creatures + items:
            if item not in inventory:
                inventory[item] = "N/A"
        return inventory
    except Exception as e:
        print(f'Error loading inventory: {e}')
        return {item: "N/A" for item in creatures + items}

def save_inventory(inventory):
    try:
        for item, quantity in inventory.items():
            inventory_collection.update_one({'item': item}, {'$set': {'quantity': quantity}}, upsert=True)
        print("Inventory saved successfully")
    except Exception as e:
        print(f'Error saving inventory: {e}')

def load_prices():
    try:
        prices_data = prices_collection.find({})
        prices = {item['item']: {'슘 시세': item['shoom_price'], '현금 시세': item['cash_price']} for item in prices_data}
        for item in creatures + items:
            if item not in prices:
                prices[item] = {'슘 시세': "N/A", '현금 시세': "N/A"}
        return prices
    except Exception as e:
        print(f'Error loading prices: {e}')
        return {item: {'슘 시세': "N/A", '현금 시세': "N/A"} for item in creatures + items}

def save_prices(prices):
    try:
        for item, price in prices.items():
            prices_collection.update_one({'item': item}, {'$set': {'shoom_price': price['슘 시세'], 'cash_price': price['현금 시세']}}, upsert=True)
        print("Prices saved successfully")
    except Exception as e:
        print(f'Error saving prices: {e}')

# 모든 기능 실행
if __name__ == '__main__':
    bot.run(os.getenv('DISCORD_BOT_TOKEN'))
