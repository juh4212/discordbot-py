import os
import random
import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
import re
import discord
from discord.ext import commands
from discord import app_commands
import threading
import time
from decimal import Decimal, ROUND_HALF_UP
from bson.objectid import ObjectId

# MongoDB 연결 설정
MONGODB_URI = os.getenv('MONGODB_URI')
client = MongoClient(MONGODB_URI, tls=True, tlsAllowInvalidCertificates=True)
db = client.creatures_db
inventory_collection = db['inventory']
prices_collection = db['prices']
sales_collection = db['sales']

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
    
    if (second_digit <= 2) or (second_digit > 7):
        rounded_value = rounded_value - Decimal(second_digit) / 100
    elif (second_digit <= 4) or (second_digit <= 7):
        rounded_value = rounded_value - Decimal(second_digit) / 100 + Decimal('0.05')

    return float(rounded_value)

# 소수점 네 번째 자리를 반올림하고 세 번째 자리를 0, 2, 5로 조정하는 함수
def round_and_adjust(value):
    rounded_value = Decimal(value).quantize(Decimal('0.000'), rounding=ROUND_HALF_UP)
    third_digit = int(rounded_value * 1000) % 10
    
    if third_digit <= 2:
        adjusted_value = rounded_value - Decimal(third_digit) / 1000
    elif third_digit <= 4:
        adjusted_value = rounded_value - Decimal(third_digit) / 1000 + Decimal('0.002')
    elif third_digit <= 7:
        adjusted_value = rounded_value - Decimal(third_digit) / 1000 + Decimal('0.005')
    else:
        adjusted_value = rounded_value + Decimal('0.01') - Decimal(third_digit) / 1000

    return float(adjusted_value)

# 크리쳐 가격 정보를 웹 스크래핑하는 함수
def fetch_creature_prices():
    url = 'https://www.game.guide/creatures-of-sonaria-value-list'
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
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
    else:
        return []

# MongoDB 업데이트 함수
def update_database(creature_data):
    for creature in creature_data:
        db.creatures.update_one({'name': creature['name']}, {'$set': {'shoom_price': creature['value']}}, upsert=True)
    print("Database updated with the latest creature prices.")

# Discord 봇 설정
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 안전한 응답 함수: 상호작용이 이미 응답되었는지 확인
async def safe_send(interaction, content=None, embeds=None):
    try:
        if embeds is None:
            embeds = []
        if not interaction.response.is_done():
            await interaction.response.send_message(content, embeds=embeds)
        else:
            await interaction.followup.send(content, embeds=embeds)
    except discord.errors.NotFound:
        print("Interaction not found or already responded to.")

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
        await safe_send(interaction, f'Item "{item}" added: {quantity} units.')
    else:
        await safe_send(interaction, f'Item "{item}" is not recognized.')

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
            await safe_send(interaction, f'Item "{item}" removed: {quantity} units.')
        else:
            await safe_send(interaction, f'Not enough "{item}" in inventory.')
    else:
        await safe_send(interaction, f'Item "{item}" is not recognized.')

# 슬래시 커맨드: 시세 업데이트
@bot.tree.command(name='price', description='Update the price of an item.')
@app_commands.describe(item='The item to update the price for', shoom_price='The new shoom price of the item')
@app_commands.autocomplete(item=autocomplete_items)
async def update_price(interaction: discord.Interaction, item: str, shoom_price: int):
    global prices  # 전역 변수로 접근하여 업데이트
    if item in creatures + items:
        prices[item]["슘 시세"] = shoom_price
        prices[item]["현금 시세"] = shoom_price * 0.5
        save_prices(prices)
        await safe_send(interaction, f'아이템 "{item}"의 시세가 슘 시세: {shoom_price}슘, 현금 시세: {shoom_price * 0.5}원으로 업데이트되었습니다.')
    else:
        await safe_send(interaction, f'아이템 "{item}"은(는) 사용할 수 없는 아이템입니다.')

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
    await safe_send(interaction, embeds=[embed1, embed2, embed3])

# 슬래시 커맨드: 할인 적용
@bot.tree.command(name='discount', description='Apply a discount to all creatures.')
@app_commands.describe(discount_percentage='The discount percentage to apply (0-100)')
async def discount_creatures(interaction: discord.Interaction, discount_percentage: int):
    global discounted_prices  # 전역 변수로 접근
    if 0 <= discount_percentage <= 100:
        discount_factor = 1 - (discount_percentage / 100)
        discounted_prices = {}
        for creature in creatures:
            if creature in prices:
                original_price = float(prices[creature]["현금 시세"])
                discounted_price = round_to_nearest(original_price * discount_factor)
                discounted_prices[creature] = discounted_price

        # 결과 메시지 구성
        discount_message = "할인이 적용된 시세:\n"
        for creature, price in discounted_prices.items():
            discount_message += f"• {creature.title()} - 할인된 시세: {price}원\n"

        await safe_send(interaction, discount_message)
    else:
        await safe_send(interaction, "할인율은 0과 100 사이의 값이어야 합니다.")

# 슬래시 커맨드: 판매 메시지 생성
@bot.tree.command(name='sell_message', description='Generate the sell message.')
async def sell_message(interaction: discord.Interaction):
    """판매 메시지를 생성합니다."""
    rate_message = "슘 1K당 0.07\n"  # 새로운 환율 정보
    creatures_message = "ㅡㅡ소나리아ㅡㅡ\n\n계좌로 팔아요!!\n\n" + rate_message + "<크리쳐>\n"

    # 크리처 목록을 순회하면서 메시지 구성
    for item in creatures:
        quantity = inventory.get(item, 0)  # inventory에서 최신 정보 가져오기
        prices_info = prices.get(item, {"현금 시세": "N/A"})
        cash_price = discounted_prices.get(item, prices_info["현금 시세"])  # 할인된 가격 사용
        if cash_price != "N/A":
            display_price = round_to_nearest(float(cash_price) * 0.0001)  # 수정된 반올림 함수 적용
        else:
            display_price = "N/A"
        creatures_message += f"• {item.title()} {display_price} (재고 {quantity})\n"

    # 아이템 목록 메시지 구성
    items_message = "\n<아이템>\n"
    for item in items:
        quantity = inventory.get(item, 0)  # inventory에서 최신 정보 가져오기
        prices_info = prices.get(item, {"현금 시세": "N/A"})
        cash_price = prices_info["현금 시세"]
        if cash_price != "N/A":
            display_price = round_and_adjust(float(cash_price) * 0.0001)  # 소수점 네 번째 자리 반올림 및 조정 적용
        else:
            display_price = "N/A"
        items_message += f"• {item.title()} {display_price} (재고 {quantity})\n"

    # 필수 메시지 추가
    final_message = creatures_message + items_message + "\n• 문상 X  계좌 O\n• 구매를 원하시면 갠으로! \n• 재고 확인 후 갠오세요!"

    await safe_send(interaction, final_message)

# 슬래시 커맨드: 구매 메시지 생성
@bot.tree.command(name='buy_message', description='Generate the buy message.')
async def buy_message(interaction: discord.Interaction):
    """구매 메시지를 생성합니다."""
    # 필수 문장 추가
    buy_message_content = "ㅡㅡ소나리아ㅡㅡ\n\n"  # 필수 문장

    # 재고가 0~1 사이인 크리쳐 목록 추가
    creature_lines = []
    for item in creatures:
        quantity = inventory.get(item, 0)
        if quantity != "N/A" and 0 <= int(quantity) <= 1:
            creature_lines.append(item.title())  # 재고가 0~1 사이인 크리쳐만 추가

    # 두 개씩 묶어 한 줄에 추가
    for i in range(0, len(creature_lines), 2):
        line = ", ".join(creature_lines[i:i + 2])
        buy_message_content += f"{line}\n"

    # 필수 문장 추가
    buy_message_content += "\n슘으로 구합니다\n정가 정도에 다 삽니다\n갠으로 제시 주세요"

    # 최종 메시지 전송
    await safe_send(interaction, buy_message_content)

# 슬래시 커맨드: 판매 기록 저장 및 인벤토리 업데이트
@bot.tree.command(name='판매', description='상품을 판매합니다.')
@app_commands.describe(amount='판매 총액', buyer_name='구매자 이름', item_name1='첫 번째 아이템', quantity1='첫 번째 아이템 수량')
@app_commands.autocomplete(item_name1=autocomplete_items, item_name2=autocomplete_items, item_name3=autocomplete_items, item_name4=autocomplete_items, item_name5=autocomplete_items)
async def sell_item(interaction: discord.Interaction, amount: int, buyer_name: str, item_name1: str = None, quantity1: int = 0, item_name2: str = None, quantity2: int = 0, item_name3: str = None, quantity3: int = 0, item_name4: str = None, quantity4: int = 0, item_name5: str = None, quantity5: int = 0):
    items_sold = []
    
    if item_name1 and quantity1 > 0:
        items_sold.append((item_name1, quantity1))
    if item_name2 and quantity2 > 0:
        items_sold.append((item_name2, quantity2))
    if item_name3 and quantity3 > 0:
        items_sold.append((item_name3, quantity3))
    if item_name4 and quantity4 > 0:
        items_sold.append((item_name4, quantity4))
    if item_name5 and quantity5 > 0:
        items_sold.append((item_name5, quantity5))

    # 재고 업데이트 및 판매 내역 기록
    if items_sold:
        for item, quantity in items_sold:
            current_quantity = inventory.get(item, 0)
            if current_quantity < quantity:
                await safe_send(interaction, f"재고가 부족하여 {item}을(를) {quantity}개 판매할 수 없습니다.")
                return
            inventory[item] -= quantity
        save_inventory(inventory)

    # 판매 내역을 통합하여 저장
    sale_record = {
        "amount": amount,
        "buyer_name": buyer_name,
        "items_sold": items_sold,
        "timestamp": time.time(),
        "user_id": interaction.user.id,  # 사용자 ID 저장
        "user_display_name": interaction.user.display_name  # 사용자 이름 저장
    }
    sales_collection.insert_one(sale_record)

    await safe_send(interaction, f"상품이 판매되었습니다! 총액: {amount}원")

# 슬래시 커맨드: 모든 유저의 판매 내역 확인
@bot.tree.command(name='판매내역', description='모든 유저의 판매 내역을 확인합니다.')
async def show_sales(interaction: discord.Interaction):
    all_sales_records = list(sales_collection.find().sort("timestamp", 1))
    if len(all_sales_records) == 0:  # 판매 내역이 없을 경우
        await safe_send(interaction, "판매 기록이 없습니다.")
        return

    user_sales = {}
    for record in all_sales_records:
        user_id = record.get("user_id")
        user_display_name = record.get("user_display_name", "알 수 없음")
        if user_display_name not in user_sales:
            user_sales[user_display_name] = []
        
        items_detail = ", ".join([f"{item} - {quantity}개" for item, quantity in record.get("items_sold", [])])
        sales_info = f"{items_detail} - {record.get('amount', '알 수 없음')}원 - 구매자: {record.get('buyer_name', '알 수 없음')} (판매 ID: {record['_id']})"
        user_sales[user_display_name].append(sales_info)
    
    final_message = ""
    for user, sales in user_sales.items():
        total_sales = sum(int(re.search(r"(\d+)원", sale).group(1)) for sale in sales if re.search(r"(\d+)원", sale))
        final_message += f"{user}님의 판매 기록:\n\n"
        final_message += "\n".join(sales)
        final_message += f"\n\n총 판매액: {total_sales}원\n\n"

    await safe_send(interaction, final_message)

# 슬래시 커맨드: 특정 판매 기록 삭제 및 인벤토리 복구 (어드민 전용)
@bot.tree.command(name='판매삭제', description='특정 판매 기록을 삭제하고, 인벤토리를 복구합니다.')
@app_commands.describe(sale_id='삭제할 판매 기록의 ID')
async def delete_sale(interaction: discord.Interaction, sale_id: str):
    if interaction.user.guild_permissions.administrator:
        try:
            # 판매 기록을 조회하여 인벤토리 복구에 필요한 정보 획득
            sale_record = sales_collection.find_one({"_id": ObjectId(sale_id)})
            if sale_record:
                # 인벤토리 복구
                items_sold = sale_record.get("items_sold", [])
                for item, quantity in items_sold:
                    current_quantity = inventory.get(item, 0)
                    inventory[item] = current_quantity + quantity
                save_inventory(inventory)

                # 판매 기록 삭제
                sales_collection.delete_one({"_id": ObjectId(sale_id)})
                await safe_send(interaction, f"판매 기록(ID: {sale_id})이 성공적으로 삭제되고, 인벤토리가 복구되었습니다.")
            else:
                await safe_send(interaction, f"판매 기록(ID: {sale_id})을 찾을 수 없습니다.")
        except Exception as e:
            await safe_send(interaction, f"오류가 발생했습니다: {str(e)}")
    else:
        await safe_send(interaction, "이 명령어를 사용할 권한이 없습니다.", ephemeral=True)

# 슬래시 커맨드: 판매 내역 초기화 (정산, 어드민 전용)
@bot.tree.command(name='정산', description='판매 내역을 초기화합니다.')
async def reset_sales(interaction: discord.Interaction):
    # 관리자 권한 확인 (예: 'ADMINISTRATOR' 권한이 있는 경우)
    if interaction.user.guild_permissions.administrator:
        sales_collection.delete_many({})  # 모든 판매 기록 삭제
        await safe_send(interaction, "판매 내역이 초기화되었습니다.")
    else:
        await safe_send(interaction, "이 명령어를 사용할 권한이 없습니다.", ephemeral=True)

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

# 디스코드 토큰을 환경 변수에서 가져와 실행
if __name__ == '__main__':
    discord_token = os.getenv('DISCORD_BOT_TOKEN')

    # 토큰이 제대로 로드되었는지 확인
    if discord_token is None:
        print("DISCORD_BOT_TOKEN이 설정되지 않았습니다. 환경 변수를 확인하세요.")
    else:
        bot.run(discord_token)
