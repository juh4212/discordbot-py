import os
import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
from dotenv import load_dotenv
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict

# 환경 변수 로드
load_dotenv()

# MongoDB 연결 설정
MONGODB_URI = os.getenv('MONGODB_URI')
client = MongoClient(MONGODB_URI, tls=True, tlsAllowInvalidCertificates=True)
db = client.creatures_db
inventory_collection = db['inventory']
prices_collection = db['prices']
sales_collection = db['sales']  # 판매 기록을 저장할 컬렉션

# 고정된 아이템 목록 (영어 순으로 정렬, 새로운 항목 추가)
creatures = [
    "aidoneiscus", "angelic warden", "aolenus", "ardor warden", "boreal warden", "caldonterrus", 
    "corsarlett", "cuxena", "eigion warden", "garra warden", "ghartokus", "golgaroth", 
    "hellion warden", "jhiggo jangl", "jotunhel", "luxces", "lus adarch", "magnacetus", 
    "menace", "mijusuima", "nolumoth", "pacedegon", "parahexilian", "sang toare", "takamorath", 
    "umbraxi", "urzuk", "verdent warden", "voletexius", "whispthera", "woodralone", "yohsog"
]
items = ["death gacha token", "revive token", "max growth token", "partial growth token", "strong glimmer token", "appearance change token"]

# 할인된 가격을 저장할 변수
discounted_prices = {}

# 소수점 셋째 자리를 반올림하여 둘째 자리로 올리고, 0, 2, 또는 5로 설정하는 함수
def round_to_nearest(value):
    rounded_value = Decimal(value).quantize(Decimal('0.00'))
    second_digit = int(rounded_value * 100) % 10
    
    if (second_digit <= 2):
        rounded_value = rounded_value - Decimal(second_digit) / 100
    elif (second_digit <= 4):
        rounded_value = rounded_value - Decimal(second_digit) / 100 + Decimal('0.05')
    elif (second_digit <= 7):
        rounded_value = rounded_value - Decimal(second_digit) / 100 + Decimal('0.05')
    else:
        rounded_value = rounded_value + Decimal('0.1') - Decimal(second_digit) / 100
    
    return float(rounded_value)

# 소수점 네 번째 자리를 반올림하고 세 번째 자리를 0, 2, 5로 조정하는 함수
def round_and_adjust(value):
    rounded_value = Decimal(value).quantize(Decimal('0.000'), rounding=ROUND_HALF_UP)
    third_digit = int(rounded_value * 1000) % 10
    
    if (third_digit <= 2):
        adjusted_value = rounded_value - Decimal(third_digit) / 1000
    elif (third_digit <= 4):
        adjusted_value = rounded_value - Decimal(third_digit) / 1000 + Decimal('0.002')
    elif (third_digit <= 7):
        adjusted_value = rounded_value - Decimal(third_digit) / 1000 + Decimal('0.005')
    else:
        adjusted_value = rounded_value + Decimal('0.01') - Decimal(third_digit) / 1000

    return float(adjusted_value)

# Discord 봇 설정
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

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
    global prices  # 전역 변수로 접근하여 업데이트
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

# 슬래시 커맨드: 판매
@bot.tree.command(name='판매', description='여러 종류의 아이템을 판매합니다.')
@app_commands.describe(
    amount='총 판매 금액', buyer_name='구매자 이름',
    item_name1='판매할 아이템 이름 1', quantity1='아이템 1의 갯수',
    item_name2='판매할 아이템 이름 2 (선택사항)', quantity2='아이템 2의 갯수 (선택사항)',
    item_name3='판매할 아이템 이름 3 (선택사항)', quantity3='아이템 3의 갯수 (선택사항)',
    item_name4='판매할 아이템 이름 4 (선택사항)', quantity4='아이템 4의 갯수 (선택사항)',
    item_name5='판매할 아이템 이름 5 (선택사항)', quantity5='아이템 5의 갯수 (선택사항)'
)
@app_commands.autocomplete(
    item_name1=autocomplete_items, item_name2=autocomplete_items, item_name3=autocomplete_items,
    item_name4=autocomplete_items, item_name5=autocomplete_items
)
async def record_sales(
    interaction: discord.Interaction,
    amount: float,
    buyer_name: str,
    item_name1: str, quantity1: int,
    item_name2: str = None, quantity2: int = None,
    item_name3: str = None, quantity3: int = None,
    item_name4: str = None, quantity4: int = None,
    item_name5: str = None, quantity5: int = None,
):
    nickname = interaction.user.display_name
    item_details = []
    item_summary = defaultdict(list)  # 구매자별 아이템 요약
    
    # 모든 아이템과 수량을 확인하여 판매 기록에 추가
    for i in range(1, 6):
        item_name = eval(f'item_name{i}')
        quantity = eval(f'quantity{i}')
        if item_name and quantity:
            current_quantity = inventory_collection.find_one({'item': item_name})['quantity']
            if current_quantity < quantity:
                await interaction.response.send_message(f"재고가 부족합니다. 현재 {item_name}의 재고는 {current_quantity}개입니다.")
                return
            inventory_collection.update_one({'item': item_name}, {'$inc': {'quantity': -quantity}})
            item_summary[buyer_name].append((item_name, quantity))
    
    # 판매 기록 저장
    for buyer, items in item_summary.items():
        item_list = ', '.join([f"{name} - {qty}개" for name, qty in items])
        sale_entry = {
            "nickname": nickname,
            "item_summary": item_list,
            "amount": round(amount / len(item_summary)),  # 총액을 정수로 나누어 저장
            "buyer_name": buyer,
            "timestamp": interaction.created_at
        }
        sales_collection.insert_one(sale_entry)

    # 메시지 출력
    response_message = ""
    for buyer, items in item_summary.items():
        item_list = ', '.join([f"{name} - {qty}개" for name, qty in items])
        response_message += f"{item_list} - {round(amount)}원 - 구매자: {buyer}\n"

    await interaction.response.send_message(response_message)

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
