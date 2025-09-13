import os
import re, json, requests
from bs4 import BeautifulSoup
from telegram import Update, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Получаем токен из переменных окружения Render
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; EncarBot/1.0)"}

def norm_url(u):
    if not u: return None
    if u.startswith("//"): return "https:" + u
    if u.startswith("/"): return "https://m.encar.com" + u
    return u

def parse_encar(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    result = {"url": url}

    # JSON-LD данные
    for s in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            obj = json.loads(s.string)
            if isinstance(obj, dict) and ("image" in obj or "offers" in obj):
                result['title'] = obj.get("name") or obj.get("headline")
                imgs = obj.get("image") or []
                if isinstance(imgs, str): imgs = [imgs]
                result['images'] = [norm_url(i) for i in imgs if i]
                offers = obj.get("offers") or {}
                if isinstance(offers, dict):
                    result['price'] = offers.get("price")
                break
        except Exception:
            continue

    text = soup.get_text(" ", strip=True)

    # Цена
    if not result.get("price"):
        m = re.search(r"([\d,]+)\s*(원|₩|KRW)", text)
        if m:
            result['price'] = re.sub(r"[^\d]", "", m.group(1))

    # Пробег
    m = re.search(r"(주행거리|주행)\s*[:\-]?\s*([\d,]+)", text)
    if m:
        result['mileage_km'] = re.sub(r"[^\d]", "", m.group(2))

    # Год
    m = re.search(r"(19|20)\d{2}", text)
    if m:
        result['year'] = m.group(0)

    # Фотки fallback
    if not result.get("images"):
        imgs = []
        for img in soup.select("img"):
            src = img.get("data-src") or img.get("src")
            if src:
                imgs.append(norm_url(src))
        result['images'] = list(dict.fromkeys(imgs))

    return result

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Пришлите ссылку на объявление Encar 🚗")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith("http"):
        await update.message.reply_text("Это не ссылка 😅")
        return

    try:
        data = parse_encar(url)
    except Exception as e:
        await update.message.reply_text(f"Ошибка парсинга: {e}")
        return

    msg = f"🚗 {data.get('title','Без названия')}\n"
    if data.get("price"): msg += f"💰 Цена: {data['price']} ₩\n"
    if data.get("mileage_km"): msg += f"🛣️ Пробег: {data['mileage_km']} km\n"
    if data.get("year"): msg += f"📅 Год: {data['year']}\n"
    msg += f"🔗 {data['url']}"

    await update.message.reply_text(msg)

    # Фото (до 5 штук)
    imgs = data.get("images") or []
    if imgs:
        media = [InputMediaPhoto(i) for i in imgs[:5]]
        if len(media) == 1:
            await update.message.reply_photo(media[0].media)
        else:
            await update.message.reply_media_group(media)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.run_polling()

if __name__ == "__main__":
    main()
