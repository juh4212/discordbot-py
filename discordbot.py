import discord
from discord.ext import commands
import json
import os

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

# 재고 파일 경로
inventory_file = "inventory.json"
prices_file = "prices.json"

def initialize_files():
    """파일을 초기화합니다."""
    if not os.path.exists(inventory_file):
        with open(inventory_file, "w") as f:
            json.dump(inventory, f)
    if not os.path.exists(prices_file):
        with open(prices_file, "w") as f:
            json.dump(prices, f)

def load_inventory():
    """재고를 JSON 파일에서 불러옵니다."""
    if os.path.exists(inventory_file):
        with open(inventory_file, "r") as f:
            return json.load(f)
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
    initialize_files()
    inventory = load_inventory()
    prices = load_prices()
    print(f'Logged in as {bot.user}')

# 명령어: 아이템 추가
@bot.command(name='add')
async def add_item(ctx, item: str, quantity: int):
    """고정된 아이템 목록에 아이템을 추가합니다."""
    if item in inventory:
        inventory[item] += quantity
        save_inventory()
        await ctx.send(f'아이템 "{item}"이(가) {quantity}개 추가되었습니다.')
    else:
        await ctx.send(f'아이템 "{item}"은(는) 사용할 수 없는 아이템입니다.')

# 명령어: 아이템 제거
@bot.command(name='remove')
async def remove_item(ctx, item: str, quantity: int):
    """고정된 아이템 목록에서 아이템을 제거합니다."""
    if item in inventory:
        if inventory[item] >= quantity:
            inventory[item] -= quantity
            save_inventory()
            await ctx.send(f'아이템 "{item}"이(가) {quantity}개 제거되었습니다.')
        else:
            await ctx.send(f'아이템 "{item}"의 재고가 부족합니다.')
    else:
        await ctx.send(f'아이템 "{item}"은(는) 사용할 수 없는 아이템입니다.')

# 명령어: 시세 업데이트
@bot.command(name='update_price')
async def update_price(ctx, item: str, shoom_price: int):
    """아이템의 시세를 업데이트합니다."""
    if item in prices:
        prices[item]["슘 시세"] = shoom_price
        prices[item]["현금 시세"] = shoom_price * 0.7
        save_prices()
        await ctx.send(f'아이템 "{item}"의 시세가 슘 시세: {shoom_price}슘, 현금 시세: {shoom_price * 0.7}원으로 업데이트되었습니다.')
    else:
        await ctx.send(f'아이템 "{item}"은(는) 사용할 수 없는 아이템입니다.')

# 명령어: 현재 재고 확인
@bot.command(name='inventory')
async def show_inventory(ctx):
    """현재 재고를 카테고리별로 임베드 형태로 표시합니다."""
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
    await ctx.send(embed=embed1)
    await ctx.send(embed=embed2)
    await ctx.send(embed=embed3)

# 봇 실행
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
bot.run(TOKEN)



