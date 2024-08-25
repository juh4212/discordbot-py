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
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict
from discord.ui import TextInput  # TextInput을 discord.ui에서 가져옵니다.

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

        await interaction.response.send_message(discount_message)
    else:
        await interaction.response.send_message("할인율은 0과 100 사이의 값이어야 합니다.")

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
    final_message = creatures_message + items_message + "\n• 문상 X  계좌 O\n• 구매를 원하시면 갠으로! \n• 재고를 확 후 갠오세요!"

    await interaction.response.send_message(final_message)

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
    await interaction.response.send_message(buy_message_content)

# 슬래시 커맨드: 판매
@bot.tree.command(name='판매', description='여러 종류의 아이템을 판매합니다.')
@app_commands.describe(
    num_items='몇 종류의 아이템을 판매하시겠습니까? (최대 10종류)',
    item_name1='판매할 아이템 이름 1', quantity1='아이템 1의 갯수',
    item_name2='판매할 아이템 이름 2 (선택사항)', quantity2='아이템 2의 갯수 (선택사항)',
    item_name3='판매할 아이템 이름 3 (선택사항)', quantity3='아이템 3의 갯수 (선택사항)',
    item_name4='판매할 아이템 이름 4 (선택사항)', quantity4='아이템 4의 갯수 (선택사항)',
    item_name5='판매할 아이템 이름 5 (선택사항)', quantity5='아이템 5의 갯수 (선택사항)',
    item_name6='판매할 아이템 이름 6 (선택사항)', quantity6='아이템 6의 갯수 (선택사항)',
    item_name7='판매할 아이템 이름 7 (선택사항)', quantity7='아이템 7의 갯수 (선택사항)',
    item_name8='판매할 아이템 이름 8 (선택사항)', quantity8='아이템 8의 갯수 (선택사항)',
    item_name9='판매할 아이템 이름 9 (선택사항)', quantity9='아이템 9의 갯수 (선택사항)',
    item_name10='판매할 아이템 이름 10 (선택사항)', quantity10='아이템 10의 갯수 (선택사항)',
    amount='총 판매 금액', buyer_name='구매자 이름'
)
@app_commands.autocomplete(
    item_name1=autocomplete_items, item_name2=autocomplete_items, item_name3=autocomplete_items,
    item_name4=autocomplete_items, item_name5=autocomplete_items, item_name6=autocomplete_items,
    item_name7=autocomplete_items, item_name8=autocomplete_items, item_name9=autocomplete_items,
    item_name10=autocomplete_items
)
async def record_sales(
    interaction: discord.Interaction,
    num_items: int,
    item_name1: str, quantity1: int,
    item_name2: str = None, quantity2: int = None,
    item_name3: str = None, quantity3: int = None,
    item_name4: str = None, quantity4: int = None,
    item_name5: str = None, quantity5: int = None,
    item_name6: str = None, quantity6: int = None,
    item_name7: str = None, quantity7: int = None,
    item_name8: str = None, quantity8: int = None,
    item_name9: str = None, quantity9: int = None,
    item_name10: str = None, quantity10: int = None,
    amount: float, buyer_name: str
):
    nickname = interaction.user.display_name
    item_details = []
    for i in range(1, num_items + 1):
        item_name = eval(f'item_name{i}')
        quantity = eval(f'quantity{i}')
        if item_name and quantity:
            current_quantity = inventory.get(item_name, "N/A")
            if current_quantity == "N/A" or current_quantity < quantity:
                await interaction.response.send_message(f"재고가 부족합니다. 현재 {item_name}의 재고는 {current_quantity}개입니다.")
                return
            inventory[item_name] -= quantity
            item_details.append({"item_name": item_name, "quantity": quantity})
            save_inventory(inventory)

    for item in item_details:
        sale_entry = {
            "nickname": nickname,
            "item_name": item['item_name'],
            "quantity": item['quantity'],
            "amount": amount / num_items,
            "buyer_name": buyer_name,
            "timestamp": interaction.created_at
        }
        sales_collection.insert_one(sale_entry)

    await interaction.response.send_message(f"판매 기록 완료: {nickname}님이 총 {amount}원에 판매했습니다.")

# 슬래시 커맨드: 정산
@bot.tree.command(name='정산', description='모든 판매 내역을 정산하고, 유저별 총 금액을 표시합니다.')
async def finalize_sales(interaction: discord.Interaction):
    sales_data = sales_collection.find({})
    user_totals = defaultdict(float)
    
    for sale in sales_data:
        user_totals[sale['nickname']] += sale['amount']
    
    response_message = "정산 완료\n"
    for nickname, total in user_totals.items():
        response_message += f"{nickname}: {total}원 (총 금액)\n"
    
    sales_collection.delete_many({})  # 정산 후 모든 판매 기록 삭제
    await interaction.response.send_message(response_message)

# 슬래시 커맨드: 판매 기록 조회
@bot.tree.command(name='판매기록', description='특정 사용자의 판매 기록을 조회합니다.')
@app_commands.describe(nickname='조회할 디스코드 닉네임 (비워두면 모든 기록 조회)')
async def view_sales(interaction: discord.Interaction, nickname: str = None):
    if nickname:
        sales_data = list(sales_collection.find({"nickname": nickname}))
    else:
        sales_data = list(sales_collection.find({}))
    
    if len(sales_data) == 0:
        await interaction.response.send_message("판매 기록이 없습니다.")
        return

    # 사용자의 판매 기록을 분류하여 출력
    user_sales = defaultdict(list)
    user_totals = defaultdict(float)
    
    for sale in sales_data:
        sale_text = f"{sale['item_name']} - {sale['quantity']}개 - {sale['amount']}원 - 구매자: {sale['buyer_name']}"
        user_sales[sale['nickname']].append(sale_text)
        user_totals[sale['nickname']] += sale['amount']

    embeds = []
    for user, sales in user_sales.items():
        embed = discord.Embed(title=f"{user}님의 판매 기록", color=discord.Color.blue())
        for sale in sales:
            embed.add_field(name="기록", value=sale, inline=False)
        embed.add_field(name="총 판매액", value=f"{user_totals[user]}원", inline=False)
        embeds.append(embed)

    await interaction.response.send_message(embeds=embeds)

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
