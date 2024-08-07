import os
import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
import re
import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask, jsonify
from dotenv import load_dotenv
import schedule
import threading
import time

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

# 크리쳐 가격 정보를 웹 스크래핑하는 함수
def fetch_creature_prices():
    url = 'https://www.game.guide/creatures-of-sonaria-value-list'
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    creature_data = []

    table = soup.find('table')
    if not table:
        print("Table not found in the web page.")
        return creature_data

    rows = table.find_all('tr')[1:]

    for row in rows:
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

# 주기적으로 크롤링 및 데이터베이스 업데이트
def job():
    print("Fetching creature prices...")
    creature_data = fetch_creature_prices()
    if creature_data:
        update_database(creature_data)
    else:
        print("Failed to fetch creature prices.")

schedule.every().day.at("09:00").do(job)

# Flask API 서버 설정
app = Flask(__name__)

@app.route('/creature_prices', methods=['GET'])
def get_creature_prices():
    creatures = db.creatures.find({})
    result = []
    for creature in creatures:
        result.append({
            "name": creature['name'],
            "shoom_price": creature['shoom_price']
        })
    return jsonify(result)

# Flask 서버 스레드 시작
def run_flask():
    app.run(debug=True, use_reloader=False)

# Discord 봇 설정
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

FLASK_API_URL = 'http://localhost:5000/creature_prices'

async def fetch_prices_from_api():
    response = requests.get(FLASK_API_URL)
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
    creatures_message = "ㅡㅡ소나리아ㅡㅡ\n\n계좌로 팔아요!!\n\n<크리쳐>\n"
    items_message = "\n<아이템>\n"

    # Creatures 목록 추가
    for item in creatures:
        quantity = inventory.get(item, "N/A")
        prices_info = prices.get(item, {"현금 시세": "N/A"})
        cash_price = prices_info["현금 시세"]
        if cash_price != "N/A":
            display_price = round(float(cash_price) * 0.0001, 2)
        else:
            display_price = "N/A"
        creatures_message += f"• {item.title()} {display_price} (재고 {quantity})\n"

    # Items 목록 추가
    for item in items:
        quantity = inventory.get(item, "N/A")
        prices_info = prices.get(item, {"현금 시세": "N/A"})
        cash_price = prices_info["현금 시세"]
        if cash_price != "N/A":
            display_price = round(float(cash_price) * 0.0001, 2)
        else:
            display_price = "N/A"
        items_message += f"• {item.title()} {display_price} (재고 {quantity})\n"

    # 필수 메시지 추가
    final_message = creatures_message + items_message + "\n• 문상 X  계좌 O\n• 구매를 원하시면 갠으로! \n• 재고는 갠디로 와서 물어봐주세요!"
    
    await interaction.response.send_message(final_message)

# 슬래시 커맨드: 크리쳐 목록 불러오기
@bot.tree.command(name='load_list', description='Load the creature prices from the website.')
async def load_list(interaction: discord.Interaction):
    await interaction.response.defer()  # Interaction이 시작되었음을 Discord에 알림
    creature_data = fetch_creature_prices()
    if creature_data:
        update_database(creature_data)
        await interaction.followup.send("Creature prices have been loaded and updated successfully.")
    else:
        await interaction.followup.send("Failed to load creature prices from the website.")

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
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    bot_thread = threading.Thread(target=lambda: bot.run(os.getenv('DISCORD_BOT_TOKEN')))
    bot_thread.start()

    while True:
        schedule.run_pending()
        time.sleep(3)

