import os
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, 
    CallbackQuery,
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    ReplyKeyboardMarkup, 
    KeyboardButton,
    LabeledPrice,
    PreCheckoutQuery,
    SuccessfulPayment,
    ShippingOption,
    ShippingQuery
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio
import traceback

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Константы
ADMIN_PASSWORD = "mmm111999abz"
DATA_FILE = "subscription_data.json"

# Инициализация
bot = Bot(token="8432859889:AAFt-Dia4jO8AFfH6xcvCJKoLxtGEyNDc6E")
dp = Dispatcher(storage=MemoryStorage())

# Хранение данных
class DataStorage:
    def __init__(self):
        self.data = self.load_data()
    
    def load_data(self) -> Dict[str, Any]:
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Ошибка загрузки данных: {e}")
        
        return {
            "users": {},
            "promo_codes": {},
            "active_promo_users": {},
            "bought_users": {},
            "transactions": []
        }
    
    def save_data(self):
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения данных: {e}")
    
    def get_user(self, user_id: int) -> Dict:
        user_id_str = str(user_id)
        if user_id_str not in self.data["users"]:
            self.data["users"][user_id_str] = {
                "stars": 0,
                "joined": datetime.now().isoformat(),
                "total_spent": 0
            }
            self.save_data()
        return self.data["users"][user_id_str]
    
    def update_user(self, user_id: int, data: Dict):
        user_id_str = str(user_id)
        if user_id_str in self.data["users"]:
            self.data["users"][user_id_str].update(data)
            self.save_data()
    
    def add_transaction(self, user_id: int, amount: int, description: str):
        transaction = {
            "user_id": user_id,
            "amount": amount,
            "description": description,
            "timestamp": datetime.now().isoformat()
        }
        self.data["transactions"].append(transaction)
        self.save_data()

storage = DataStorage()
admin_sessions = set()

# States
class AdminStates(StatesGroup):
    waiting_for_password = State()
    waiting_for_promo_creation = State()

class UserStates(StatesGroup):
    waiting_for_promo = State()

# Клавиатуры
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎮 Играть")],
            [KeyboardButton(text="⭐ Профиль"), KeyboardButton(text="🛒 Магазин")],
            [KeyboardButton(text="🎁 Активировать промо")]
        ],
        resize_keyboard=True
    )

def get_admin_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Promo Players", callback_data="admin_promo_players"),
                InlineKeyboardButton(text="💰 Buy Players", callback_data="admin_buy_players")
            ],
            [
                InlineKeyboardButton(text="➕ Create Promo", callback_data="admin_create_promo"),
                InlineKeyboardButton(text="📈 Статистика", callback_data="admin_stats")
            ],
            [InlineKeyboardButton(text="🔙 Выход", callback_data="admin_exit")]
        ]
    )

def get_plans_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Неделя - 10 Stars", callback_data="buy_week")],
            [InlineKeyboardButton(text="🚀 Месяц - 50 Stars", callback_data="buy_month")],
            [InlineKeyboardButton(text="👑 Полгода - 100 Stars", callback_data="buy_halfyear")],
            [InlineKeyboardButton(text="🏆 Год - 190 Stars", callback_data="buy_year")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_purchase")]
        ]
    )

# Проверка подписки
def check_subscription(user_id: int) -> Dict:
    user_id_str = str(user_id)
    now = datetime.now()
    
    # Проверка купленной подписки
    bought_data = storage.data["bought_users"].get(user_id_str)
    if bought_data:
        expiry = datetime.fromisoformat(bought_data["expiry"]) if isinstance(bought_data["expiry"], str) else bought_data["expiry"]
        if expiry > now:
            return {
                "active": True,
                "type": "buy",
                "plan": bought_data["plan"],
                "expiry": expiry
            }
    
    # Проверка промо подписки
    promo_data = storage.data["active_promo_users"].get(user_id_str)
    if promo_data:
        expiry = datetime.fromisoformat(promo_data["expiry"]) if isinstance(promo_data["expiry"], str) else promo_data["expiry"]
        if expiry > now:
            return {
                "active": True,
                "type": "promo",
                "promo_code": promo_data["promo_code"],
                "expiry": expiry
            }
    
    return {"active": False}

# Основные команды
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user = storage.get_user(message.from_user.id)
    
    welcome_text = (
        "🎮 *Добро пожаловать в бот подписок!*\n\n"
        "✨ *Ваши возможности:*\n"
        "• 🎮 Доступ к контенту (требуется подписка)\n"
        "• ⭐ Покупайте подписки за Telegram Stars\n"
        "• 🎁 Активируйте промо-коды\n\n"
        f"💰 *Ваш баланс:* {user['stars']} ⭐\n\n"
        "*Внимание:* Для покупки подписки нужна активная подписка Telegram Premium и включенная опция Stars в настройках Telegram."
    )
    
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@dp.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_password)
    await message.answer("🔐 *Введите пароль для админ-панели:*", parse_mode="Markdown")

@dp.message(AdminStates.waiting_for_password)
async def process_admin_password(message: Message, state: FSMContext):
    if message.text == ADMIN_PASSWORD:
        admin_sessions.add(message.from_user.id)
        await state.clear()
        
        # Статистика
        total_users = len(storage.data["users"])
        active_promo = len([v for v in storage.data["active_promo_users"].values() 
                          if datetime.fromisoformat(v["expiry"]) > datetime.now()])
        active_bought = len([v for v in storage.data["bought_users"].values() 
                           if datetime.fromisoformat(v["expiry"]) > datetime.now()])
        
        admin_text = (
            "👨‍💻 *Админ-панель*\n\n"
            f"📊 *Статистика:*\n"
            f"• 👥 Пользователей: {total_users}\n"
            f"• 🎁 Активных промо: {active_promo}\n"
            f"• 💰 Купленных подписок: {active_bought}\n"
            f"• 📅 Промо-кодов: {len(storage.data['promo_codes'])}"
        )
        
        await message.answer(admin_text, parse_mode="Markdown", reply_markup=get_admin_keyboard())
    else:
        await message.answer("❌ *Неверный пароль!*", parse_mode="Markdown")

@dp.message(F.text == "🎮 Играть")
async def cmd_play(message: Message):
    sub = check_subscription(message.from_user.id)
    if not sub["active"]:
        await message.answer(
            "❌ *У вас нет активной подписки!*\n\n"
            "Для доступа необходимо:\n"
            "1. 🛒 Купить подписку в магазине\n"
            "2. 🎁 Активировать промо-код\n\n"
            "Выберите действие в меню ниже:",
            parse_mode="Markdown"
        )
        return
    
    await message.answer("🎮 *Доступ к контенту открыт!*\nНаслаждайтесь! 🚀", parse_mode="Markdown")

@dp.message(F.text == "⭐ Профиль")
async def cmd_profile(message: Message):
    user = storage.get_user(message.from_user.id)
    sub = check_subscription(message.from_user.id)
    
    profile_text = (
        f"👤 *Ваш профиль*\n"
        f"🆔 ID: `{message.from_user.id}`\n"
        f"💰 Баланс: *{user['stars']}* ⭐\n"
        f"📅 Регистрация: {datetime.fromisoformat(user['joined']).strftime('%d.%m.%Y')}\n\n"
    )
    
    if sub["active"]:
        expiry_str = sub["expiry"].strftime("%d.%m.%Y %H:%M")
        if sub["type"] == "buy":
            profile_text += f"✅ *Активная подписка (куплена)*\n📋 План: {sub['plan']}\n⏰ Истекает: {expiry_str}"
        else:
            profile_text += f"✅ *Активная подписка (промо)*\n🎁 Промо-код: {sub['promo_code']}\n⏰ Истекает: {expiry_str}"
    else:
        profile_text += "❌ *Нет активной подписки*"
    
    await message.answer(profile_text, parse_mode="Markdown")

@dp.message(F.text == "🛒 Магазин")
async def cmd_shop(message: Message):
    user = storage.get_user(message.from_user.id)
    
    shop_text = (
        "🛒 *Магазин подписок*\n\n"
        "🎮 *Неделя* - 10 ⭐\n"
        "• Доступ на 7 дней\n\n"
        "🚀 *Месяц* - 50 ⭐\n"
        "• Доступ на 30 дней\n\n"
        "👑 *Полгода* - 100 ⭐\n"
        "• Доступ на 180 дней\n\n"
        "🏆 *Год* - 190 ⭐\n"
        "• Доступ на 365 дней\n\n"
        f"💰 *Ваш баланс:* {user['stars']} ⭐\n\n"
        "*Примечание:* Для покупки нужны звезды."
    )
    await message.answer(shop_text, parse_mode="Markdown", reply_markup=get_plans_keyboard())

@dp.message(F.text == "🎁 Активировать промо")
async def cmd_activate_promo(message: Message, state: FSMContext):
    await state.set_state(UserStates.waiting_for_promo)
    await message.answer("✏️ *Введите промо-код:*", parse_mode="Markdown")

@dp.message(UserStates.waiting_for_promo)
async def process_promo_code(message: Message, state: FSMContext):
    promo_code = message.text.upper().strip()
    user_id = message.from_user.id
    user_id_str = str(user_id)
    
    promo_data = storage.data["promo_codes"].get(promo_code)
    
    if not promo_data:
        await message.answer("❌ *Промо-код не найден!*", parse_mode="Markdown")
        await state.clear()
        return
    
    if promo_data.get("uses_left", 0) <= 0:
        await message.answer("❌ *Этот промо-код уже использован!*", parse_mode="Markdown")
        await state.clear()
        return
    
    # Проверяем активную промо подписку
    current_promo = storage.data["active_promo_users"].get(user_id_str)
    if current_promo:
        expiry = datetime.fromisoformat(current_promo["expiry"])
        if expiry > datetime.now():
            await message.answer("❌ *У вас уже есть активная промо-подписка!*", parse_mode="Markdown")
            await state.clear()
            return
    
    # Активируем промо
    days = promo_data.get("duration_days", 1)
    expiry = datetime.now() + timedelta(days=days)
    
    storage.data["active_promo_users"][user_id_str] = {
        "expiry": expiry.isoformat(),
        "promo_code": promo_code,
        "activated_at": datetime.now().isoformat()
    }
    
    promo_data["uses_left"] -= 1
    storage.save_data()
    
    success_text = (
        f"✅ *Промо-код активирован!*\n\n"
        f"🎁 Код: `{promo_code}`\n"
        f"📅 Действует: {days} дней\n"
        f"⏰ Истекает: {expiry.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"Теперь вы можете играть! 🎮"
    )
    
    await message.answer(success_text, parse_mode="Markdown")
    await state.clear()

# Админ обработчики
@dp.callback_query(F.data.startswith("admin_"))
async def admin_callback_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if user_id not in admin_sessions:
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    if callback.data == "admin_promo_players":
        active_users = []
        now = datetime.now()
        
        for uid, data in storage.data["active_promo_users"].items():
            expiry = datetime.fromisoformat(data["expiry"])
            if expiry > now:
                days_left = (expiry - now).days
                active_users.append(f"👤 ID: `{uid}`\n🎁 Код: `{data['promo_code']}`\n⏳ Дней: {days_left}")
        
        text = "📊 *Активные промо-пользователи:*\n\n"
        if active_users:
            text += "\n\n".join(active_users[:10])
            if len(active_users) > 10:
                text += f"\n\n... и еще {len(active_users) - 10} пользователей"
        else:
            text += "Нет активных промо-пользователей"
        
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_admin_keyboard())
    
    elif callback.data == "admin_buy_players":
        active_buyers = []
        now = datetime.now()
        
        for uid, data in storage.data["bought_users"].items():
            expiry = datetime.fromisoformat(data["expiry"])
            if expiry > now:
                days_left = (expiry - now).days
                active_buyers.append(f"👤 ID: `{uid}`\n📋 План: {data['plan']}\n⏳ Дней: {days_left}")
        
        text = "💰 *Пользователи с купленными подписками:*\n\n"
        if active_buyers:
            text += "\n\n".join(active_buyers[:10])
            if len(active_buyers) > 10:
                text += f"\n\n... и еще {len(active_buyers) - 10} пользователей"
        else:
            text += "Нет активных покупок"
        
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_admin_keyboard())
    
    elif callback.data == "admin_create_promo":
        await state.set_state(AdminStates.waiting_for_promo_creation)
        instructions = (
            "➕ *Создание промо-кода*\n\n"
            "Введите данные в формате:\n"
            "`<код> <дней> <использований>`\n\n"
            "*Пример:*\n"
            "`SUPERCODE 30 5`\n\n"
            "Для отмены отправьте /cancel"
        )
        await callback.message.edit_text(instructions, parse_mode="Markdown")
    
    elif callback.data == "admin_stats":
        total_users = len(storage.data["users"])
        total_stars = sum(user.get("stars", 0) for user in storage.data["users"].values())
        
        stats_text = (
            "📈 *Статистика бота*\n\n"
            f"👥 *Пользователи:*\n"
            f"• Всего: {total_users}\n"
            f"• С промо: {len(storage.data['active_promo_users'])}\n"
            f"• С покупками: {len(storage.data['bought_users'])}\n\n"
            f"💰 *Экономика:*\n"
            f"• Всего звезд: {total_stars} ⭐\n\n"
            f"🎁 *Промо-коды:*\n"
            f"• Всего: {len(storage.data['promo_codes'])}\n"
            f"• Активных: {sum(1 for p in storage.data['promo_codes'].values() if p.get('uses_left', 0) > 0)}"
        )
        
        await callback.message.edit_text(stats_text, parse_mode="Markdown", reply_markup=get_admin_keyboard())
    
    elif callback.data == "admin_exit":
        admin_sessions.discard(user_id)
        await state.clear()
        await callback.message.edit_text("✅ Вы вышли из админ-панели")
    
    await callback.answer()

# Создание промо-кодов
@dp.message(AdminStates.waiting_for_promo_creation)
async def create_promo(message: Message, state: FSMContext):
    try:
        logger.info(f"Получен запрос на создание промо: {message.text}")
        
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer("❌ *Неверный формат!*\n\nНужно: `<код> <дней> <использований>`\nПример: `TESTCODE 30 5`", parse_mode="Markdown")
            return
        
        promo_code = parts[0].upper()
        days = int(parts[1])
        uses = int(parts[2])
        
        if promo_code in storage.data["promo_codes"]:
            await message.answer("❌ *Этот промо-код уже существует!*", parse_mode="Markdown")
            return
        
        if days <= 0 or days > 365:
            await message.answer("❌ *Количество дней должно быть от 1 до 365!*", parse_mode="Markdown")
            return
        
        if uses <= 0 or uses > 1000:
            await message.answer("❌ *Количество использований должно быть от 1 до 1000!*", parse_mode="Markdown")
            return
        
        # Создаем промо-код
        storage.data["promo_codes"][promo_code] = {
            "uses_left": uses,
            "max_uses": uses,
            "duration_days": days,
            "created_by": message.from_user.id,
            "created_at": datetime.now().isoformat(),
            "used_by": []
        }
        
        storage.save_data()
        
        logger.info(f"Создан промо-код: {promo_code}, дней: {days}, использований: {uses}")
        
        success_text = (
            f"✅ *Промо-код успешно создан!*\n\n"
            f"🎁 *Код:* `{promo_code}`\n"
            f"📅 *Дней:* {days}\n"
            f"🔢 *Использований:* {uses}\n\n"
            f"*Для использования:*\nПользователь должен отправить: `{promo_code}`"
        )
        
        await message.answer(success_text, parse_mode="Markdown")
        await state.clear()
        
        # Возвращаем в админ-панель
        admin_text = "👨‍💻 *Админ-панель*\n\nПромо-код создан! Выберите действие:"
        await message.answer(admin_text, parse_mode="Markdown", reply_markup=get_admin_keyboard())
        
    except ValueError as e:
        logger.error(f"ValueError при создании промо: {e}")
        await message.answer(f"❌ *Ошибка чисел!*\nПроверьте что дни и использования - это числа!\n\nОшибка: {str(e)}", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка при создании промо: {e}\n{traceback.format_exc()}")
        await message.answer(f"❌ *Неизвестная ошибка!*\n\nОшибка: {str(e)}", parse_mode="Markdown")

# ВАЖНО: Функция для настройки платежей через Stars
async def create_stars_invoice(chat_id: int, title: str, description: str, payload: str, price: int):
    """Создание инвойса для Telegram Stars"""
    
    # Для Telegram Stars используется специальный provider_token
    provider_token = ""  # Для Stars можно оставить пустым
    
    # ВАЖНОЕ ИСПРАВЛЕНИЕ: Для Stars цена указывается в нужных единицах
    # В Telegram Stars минимальная цена зависит от региона
    # Если price=100 (Stars), то в системе это 100 единиц
    
    prices = [LabeledPrice(label=title, amount=price)]  # Убрал умножение на 100!
    
    return await bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        payload=payload,
        provider_token=provider_token,
        currency="XTR",  # Код валюты для Telegram Stars
        prices=prices,
        start_parameter=f"stars_payment_{payload}",
        need_name=False,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
        is_flexible=False,
        protect_content=True,
        request_timeout=15
    )

# Покупка через Telegram Stars (ИСПРАВЛЕННАЯ с правильными ценами)
@dp.callback_query(F.data.startswith("buy_"))
async def buy_subscription(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    # Цены в Stars (то что видит пользователь)
    plans = {
        "buy_week": {"name": "Неделя", "days": 7, "price": 10, "payload": "week_sub"},
        "buy_month": {"name": "Месяц", "days": 30, "price": 50, "payload": "month_sub"},
        "buy_halfyear": {"name": "Полгода", "days": 180, "price": 100, "payload": "halfyear_sub"},
        "buy_year": {"name": "Год", "days": 365, "price": 190, "payload": "year_sub"}
    }
    
    if callback.data == "cancel_purchase":
        await callback.message.edit_text("❌ Покупка отменена")
        await callback.answer()
        return
    
    plan = plans.get(callback.data)
    if not plan:
        await callback.answer("❌ Неизвестный план")
        return
    
    try:
        # Показываем информационное сообщение
        info_text = (
            f"🔄 *Создание платежа...*\n\n"
            f"📋 План: {plan['name']}\n"
            f"💰 Стоимость: {plan['price']} Stars\n"
            f"📅 Доступ на {plan['days']} дней\n\n"
            f"*Для продолжения:*\n"
            f"1. Убедитесь что у вас включены Stars\n"
            f"2. Подтвердите оплату в окне Telegram"
        )
        
        msg = await callback.message.edit_text(info_text, parse_mode="Markdown")
        
        # Пытаемся создать инвойс с правильной ценой
        try:
            await create_stars_invoice(
                chat_id=callback.message.chat.id,
                title=f"Подписка: {plan['name']}",
                description=f"Доступ к контенту на {plan['days']} дней",
                payload=plan["payload"],
                price=plan["price"]  # Передаем цену как есть
            )
            
        except Exception as invoice_error:
            logger.error(f"Ошибка создания инвойса: {invoice_error}")
            
            # Проверяем возможные причины
            error_text = (
                f"❌ *Не удалось создать платеж!*\n\n"
                f"*Возможные причины:*\n"
                f"1. Бот не настроен для приема платежей\n"
                f"2. У вас нет Telegram Premium\n"
                f"3. Stars не активированы в настройках\n"
                f"4. Регион не поддерживает Stars\n\n"
                f"*Что делать:*\n"
                f"• Убедитесь что у вас Telegram Premium\n"
                f"• Включите Stars в настройках Telegram\n"
                f"• Обратитесь к администратору"
            )
            
            await msg.edit_text(error_text, parse_mode="Markdown")
            return
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Общая ошибка при покупке: {e}\n{traceback.format_exc()}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)

# Shipping query handler (необходим для платежей)
@dp.shipping_query()
async def shipping_handler(shipping_query: ShippingQuery):
    # Для цифровых товаров доставка не требуется
    await shipping_query.answer(
        ok=True,
        shipping_options=[
            ShippingOption(
                id='digital',
                title='Цифровой товар',
                prices=[LabeledPrice(label='Доставка', amount=0)]
            )
        ]
    )

# Pre-checkout обработчик
@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    try:
        # Всегда подтверждаем pre-checkout для Stars
        await pre_checkout_query.answer(ok=True)
        logger.info(f"Pre-checkout подтвержден: {pre_checkout_query.id}")
    except Exception as e:
        logger.error(f"Ошибка в pre-checkout: {e}")
        await pre_checkout_query.answer(ok=False, error_message="Ошибка обработки платежа")

# Обработка успешного платежа
@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    try:
        payment = message.successful_payment
        user_id = message.from_user.id
        
        logger.info(f"Получен успешный платеж: {payment.invoice_payload}, сумма: {payment.total_amount}")
        
        # Определяем какой план куплен по payload
        plans_payloads = {
            "week_sub": {"name": "Неделя", "days": 7, "price": 10},
            "month_sub": {"name": "Месяц", "days": 30, "price": 50},
            "halfyear_sub": {"name": "Полгода", "days": 180, "price": 100},
            "year_sub": {"name": "Год", "days": 365, "price": 190}
        }
        
        plan = plans_payloads.get(payment.invoice_payload)
        if plan:
            # Добавляем подписку
            expiry = datetime.now() + timedelta(days=plan["days"])
            storage.data["bought_users"][str(user_id)] = {
                "expiry": expiry.isoformat(),
                "plan": plan["name"],
                "price": plan["price"],
                "bought_at": datetime.now().isoformat(),
                "payment_id": payment.telegram_payment_charge_id
            }
            
            # Добавляем транзакцию
            storage.add_transaction(user_id, -plan["price"], f"Покупка подписки {plan['name']}")
            
            # Обновляем баланс пользователя
            user = storage.get_user(user_id)
            user["stars"] = user.get("stars", 0) - plan["price"]
            user["total_spent"] = user.get("total_spent", 0) + plan["price"]
            storage.update_user(user_id, user)
            
            storage.save_data()
            
            success_text = (
                f"✅ *Подписка успешно куплена!*\n\n"
                f"📋 План: *{plan['name']}*\n"
                f"💰 Стоимость: {plan['price']} Stars\n"
                f"⏰ Истекает: {expiry.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"💫 *Спасибо за покупку!* 🎉\n"
                f"Теперь вы можете играть! 🎮"
            )
            
            await message.answer(success_text, parse_mode="Markdown")
            
            logger.info(f"Пользователь {user_id} купил подписку {plan['name']} за {plan['price']} Stars")
            
            # Уведомление администратора
            try:
                admin_notification = (
                    f"💰 *Новая покупка!*\n\n"
                    f"👤 Пользователь: {message.from_user.full_name}\n"
                    f"🆔 ID: {user_id}\n"
                    f"📋 План: {plan['name']}\n"
                    f"💰 Сумма: {plan['price']} Stars"
                )
                
                # Отправляем всем админам
                for admin_id in admin_sessions:
                    try:
                        await bot.send_message(admin_id, admin_notification, parse_mode="Markdown")
                    except:
                        pass
            except:
                pass
                
        else:
            logger.warning(f"Неизвестный payload платежа: {payment.invoice_payload}")
            await message.answer("✅ Платеж получен, но произошла ошибка активации. Обратитесь к администратору.")
            
    except Exception as e:
        logger.error(f"Ошибка обработки платежа: {e}\n{traceback.format_exc()}")
        await message.answer("✅ Платеж получен, но произошла ошибка. Обратитесь к администратору.")

# Отмена состояний
@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    
    await state.clear()
    await message.answer("❌ Действие отменено", reply_markup=get_main_keyboard())

# Команда для проверки платежей
@dp.message(Command("test_payment"))
async def test_payment(message: Message):
    """Тестовая команда для проверки платежей"""
    try:
        await create_stars_invoice(
            chat_id=message.chat.id,
            title="Тестовая подписка",
            description="Тестовый доступ на 1 день",
            payload="test_payment",
            price=1  # 1 Star
        )
    except Exception as e:
        logger.error(f"Ошибка тестового платежа: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")

async def main():
    logger.info("Запуск бота подписок...")
    
    # Проверяем настройки бота
    me = await bot.get_me()
    logger.info(f"Бот запущен: @{me.username}")
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")

if __name__ == "__main__":
    asyncio.run(main())