import logging
import os
import sqlite3
import html
from datetime import datetime

from telegram import (Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
                      InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaDocument, InputMediaVideo, InputMedia)
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
                          filters, ConversationHandler, CallbackContext)
from telegram.constants import ParseMode

# ---------------------------
# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------------------
# Глобальные константы
SYSTEM_ADMIN_ID = int(os.environ.get('SYSTEM_ADMIN_ID', '310083499'))
GROUP_CHAT_ID = int(os.environ.get('GROUP_CHAT_ID', '-4743343026'))  # ID группы (форум-супергруппы)

# Состояния для пользовательского диалога
(
    USER_NAME,                 # Регистрация: Ввод имени
    USER_CLIENT,               # Регистрация: Клиент/не клиент
    USER_PHONE,                # Регистрация: Телефон
    USER_ADDRESS,              
    USER_ADDRESSES,          
    REQUEST_TYPE,           
    USER_PROBLEM_DESCRIPTION,  
    USER_MEDIA_UPLOAD,  
    USER_SOS_PHONE             
) = range(9)


(
    ADMIN_MAIN,                 # Главное меню админа
    ADMIN_CHOOSE_ADD_TYPE,      # Выбор типа админа для добавления
    ADMIN_WAIT_FOR_USER_ID,     # Ввод user_id для добавления админа
    ADMIN_LIST_MENU,            # Просмотр списка администраторов
    ADMIN_CHOOSE_ACTION,        # Выбор действия над администратором (повысить/понизить/удалить)
    ADMIN_CONFIRM_ACTION,       # Подтверждение действия над администратором
    EMPLOYEE_MENU,              # Меню для работы с сотрудниками
    EMPLOYEE_WAIT_FOR_USER_ID,  # Ввод user_id сотрудника для добавления
    BRIGADE_MENU,               # Меню бригад
    BRIGADE_WAIT_FOR_DETAILS,   # Ввод данных для создания бригады
    MAILING_WAIT_FOR_TEXT,      # Ввод текста для рассылки
    ADMIN_REQUESTS_LIST,        # Выбор заявки (список заявок в админ-панели)
    ADMIN_REQUEST_DETAIL,       # Детали заявки (inline клавиатура для управления заявкой)
    ADMIN_SALES_CARDS_MENU,     # Меню карточек отдела продаж
    ADMIN_CREATE_CARD_PHOTOS,   # Приём фото для карточки (до 15 файлов)
    ADMIN_SELECT_CARD_SECTION,  # Выбор раздела для карточки
    ADMIN_CREATE_CARD_TITLE,    # Ввод названия и описания карточки
    ADMIN_CREATE_CARD_DESCRIPTION,  # Дополнительный ввод (если понадобится)
    ADMIN_SELECT_CARD_EDIT,     # Выбор карточки для редактирования
    ADMIN_SELECT_CARD_DELETE,   # Выбор карточки для удаления
    ADMIN_DELETE_CARD_CONFIRM,  # Подтверждение удаления карточки
    ADMIN_CONTROL_REQUEST       # Управление заявкой (подтверждение изменения статуса, редактирование и т.д.)
) = range(18, 18 + 22)


# Дополнительные состояния для работы с заявками по категориям
ADMIN_REQ_CATEGORY = 40      # Выбор категории заявок
ADMIN_REQ_CATEGORY_LIST = 41 # Список заявок для выбранной категории


# Состояния для редактирования профиля пользователя
(
    EDIT_PROFILE_CHOICE,          # Выбор того, что изменить в профиле (Имя/Телефон/Адрес)
    EDIT_PROFILE_NAME,            # Редактирование имени
    EDIT_PROFILE_PHONE,           # Редактирование телефона
    EDIT_PROFILE_ADDRESS_OPTS,    # Выбор действия с адресом (Сменить, Добавить, Удалить)
    EDIT_PROFILE_ADDRESS_CHANGE_INDEX,  # Выбор номера адреса для изменения
    EDIT_PROFILE_ADDRESS_CHANGE_INPUT,  # Ввод нового адреса для замены
    EDIT_PROFILE_ADDRESS_ADD,     # Ввод нового адреса для добавления
    EDIT_PROFILE_ADDRESS_DEL      # Ввод номера адреса для удаления
) = range(100, 108)


# Состояния для фильтрации заявок по дате (Мои заявки / История обслуживания)
(
    FILTER_YEAR,   # Выбор года
    FILTER_MONTH,  # Выбор месяца
    FILTER_DAY     # Выбор дня
) = range(200, 203)

EMPLOYEE_WAIT_FOR_NAME = 300
EMPLOYEE_WAIT_FOR_NAME = 300
BRIGADE_ASSIGN_SELECT = 301
EMPLOYEE_PANEL = 302
EMPLOYEE_VIEW_BY_STATUS = 303
EMPLOYEE_VIEW_REQUEST = 304
EMPLOYEE_REPORT_TEXT = 305
EMPLOYEE_REPORT_FILES = 306
ADMIN_COMMENT_TEXT = 307
ADMIN_COMMENT_FILES = 308
ADMIN_VIEW_FILES = 309
REPORT_RECIPIENTS = 310
EMPLOYEE_SELECT_STATUS = 312
EMPLOYEE_SET_STATUS = 325

# ---------------------------
# Инициализация базы данных
conn = sqlite3.connect('bot_database.db', check_same_thread=False)
cursor = conn.cursor()

# Таблица пользователей
cursor.execute('''
CREATE TABLE IF NOT EXISTS users
(
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    phone TEXT,
    addresses TEXT,
    client TEXT
)
''')

# Таблица заявок (с group_message_id, file_message_id и request_category)
cursor.execute('''
CREATE TABLE IF NOT EXISTS requests
(
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    request_type TEXT,
    description TEXT,
    media_ids TEXT,
    created_at DATETIME,
    status TEXT DEFAULT 'Новая',
    group_message_id INTEGER,
    file_message_id INTEGER,
    request_category TEXT
)
''')

try:
    cursor.execute("ALTER TABLE requests ADD COLUMN brigade_id INTEGER")
    conn.commit()
except sqlite3.OperationalError as e:
    if "duplicate column name" not in str(e).lower():
        raise

# Таблица администраторов
cursor.execute('''
CREATE TABLE IF NOT EXISTS admins
(
    user_id INTEGER PRIMARY KEY,
    role TEXT
)
''')

# Таблица сотрудников
cursor.execute('''
CREATE TABLE IF NOT EXISTS employees
(
    user_id INTEGER PRIMARY KEY,
    name TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER,
    user_id INTEGER,
    report_number INTEGER,
    text TEXT,
    media_ids TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# Таблица бригад
cursor.execute('''
CREATE TABLE IF NOT EXISTS brigades
(
    brigade_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    employee_ids TEXT
)
''')

# Таблица карточек отдела продаж
cursor.execute('''
CREATE TABLE IF NOT EXISTS sales_cards
(
    card_id INTEGER PRIMARY KEY AUTOINCREMENT,
    photos TEXT,
    title TEXT,
    description TEXT,
    section TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER,
    text TEXT,
    media_ids TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
''')

# Таблица для хранения ID тем (форум-топиков)
cursor.execute('''
CREATE TABLE IF NOT EXISTS topics
(
    topic_type TEXT PRIMARY KEY,
    thread_id TEXT
)
''')
conn.commit()

try:
    cursor.execute("ALTER TABLE requests ADD COLUMN request_category TEXT")
    conn.commit()
except sqlite3.OperationalError as e:
    if "duplicate column name" not in str(e):
        raise

# ---------------------------
# Класс для работы с БД
class Database:
    @staticmethod
    def get_user(user_id):
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()

    @staticmethod
    def get_ticket_rank(category: str, request_id: int) -> int:
        cursor.execute("SELECT COUNT(*) FROM requests WHERE request_category = ? AND request_id <= ?", (category, request_id))
        return cursor.fetchone()[0]
    
    @staticmethod
    def get_last_comment_for_request(request_id: int):
        cursor.execute("""
                    SELECT text FROM comments
                    WHERE request_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                    """, (request_id,))
        row = cursor.fetchone()
        return row[0] if row else None

    @staticmethod
    def get_requests_by_category(category: str):
        cursor.execute("SELECT * FROM requests WHERE request_category = ? ORDER BY created_at DESC", (category,))
        return cursor.fetchall()
    
    @staticmethod
    def get_custom_number(category: str) -> int:
        cursor.execute("SELECT COUNT(*) FROM requests WHERE request_category = ?", (category,))
        return cursor.fetchone()[0]
    
    @staticmethod
    def save_user(user_id, name, phone, addresses, client):
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, name, phone, addresses, client)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, name, phone, ','.join(addresses), client))
        conn.commit()
    
    @staticmethod
    def create_request(user_id, request_type, request_category, description, media_ids, created_at):
        cursor.execute('''
            INSERT INTO requests (user_id, request_type, request_category, description, media_ids, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, request_type, request_category, description,
              ','.join(media_ids) if media_ids else "", created_at))
        conn.commit()
        return cursor.lastrowid
    
    @staticmethod
    def get_user_requests(user_id):
        cursor.execute("SELECT * FROM requests WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        return cursor.fetchall()
    
    @staticmethod
    def get_all_requests():
        cursor.execute("SELECT * FROM requests ORDER BY created_at DESC")
        return cursor.fetchall()
    
    @staticmethod
    def get_request_by_id(request_id: int):
        cursor.execute("SELECT * FROM requests WHERE request_id = ?", (request_id,))
        return cursor.fetchone()
    
    @staticmethod
    def update_request_status(request_id: int, new_status: str):
        cursor.execute("UPDATE requests SET status = ? WHERE request_id = ?", (new_status, request_id))
        conn.commit()
    
    @staticmethod
    def update_request_group_message_id(request_id: int, message_id: int):
        cursor.execute("UPDATE requests SET group_message_id = ? WHERE request_id = ?", (message_id, request_id))
        conn.commit()
    
    @staticmethod
    def update_request_file_message_id(request_id: int, file_message_id: int):
        cursor.execute("UPDATE requests SET file_message_id = ? WHERE request_id = ?", (file_message_id, request_id))
        conn.commit()
    
    # Администраторы
    @staticmethod
    def get_admin(user_id: int):
        cursor.execute("SELECT * FROM admins WHERE user_id = ?", (user_id,))
        return cursor.fetchone()
    
    @staticmethod
    def add_admin(user_id: int, role: str):
        cursor.execute("INSERT OR REPLACE INTO admins (user_id, role) VALUES (?, ?)", (user_id, role))
        conn.commit()
    
    @staticmethod
    def get_all_admins():
        cursor.execute("SELECT * FROM admins")
        return cursor.fetchall()
    
    @staticmethod
    def update_admin_role(user_id: int, new_role: str):
        cursor.execute("UPDATE admins SET role = ? WHERE user_id = ?", (new_role, user_id))
        conn.commit()
    
    @staticmethod
    def remove_admin(user_id: int):
        cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        conn.commit()
    
    # Сотрудники
    @staticmethod
    def add_employee(user_id: int, name: str):
        cursor.execute("INSERT OR REPLACE INTO employees (user_id, name) VALUES (?, ?)", (user_id, name))
        conn.commit()
    
    @staticmethod
    def get_all_employees():
        cursor.execute("SELECT * FROM employees")
        return cursor.fetchall()
    
    @staticmethod
    def get_employee(user_id: int):
        cursor.execute("SELECT * FROM employees WHERE user_id = ?", (user_id,))
        return cursor.fetchone()
    
    # Бригады
    @staticmethod
    def add_brigade(name: str, employee_ids: list):
        employee_ids_str = ",".join(str(eid) for eid in employee_ids)
        cursor.execute("INSERT INTO brigades (name, employee_ids) VALUES (?, ?)", (name, employee_ids_str))
        conn.commit()
    
    @staticmethod
    def get_all_brigades():
        cursor.execute("SELECT * FROM brigades")
        return cursor.fetchall()
    
    # Карточки отдела продаж
    @staticmethod
    def add_sales_card(photos, title, description, section):
        cursor.execute('''
            INSERT INTO sales_cards (photos, title, description, section)
            VALUES (?, ?, ?, ?)
        ''', (','.join(photos), title, description, section))
        conn.commit()
    
    @staticmethod
    def get_all_sales_cards():
        cursor.execute("SELECT * FROM sales_cards ORDER BY card_id ASC")
        return cursor.fetchall()
    
    @staticmethod
    def get_sales_card(card_id: int):
        cursor.execute("SELECT * FROM sales_cards WHERE card_id = ?", (card_id,))
        return cursor.fetchone()
    
    @staticmethod
    def update_sales_card(card_id: int, photos=None, title=None, description=None, section=None):
        card = Database.get_sales_card(card_id)
        if not card:
            return False
        new_photos = photos if photos is not None else card[1]
        new_title = title if title is not None else card[2]
        new_description = description if description is not None else card[3]
        new_section = section if section is not None else card[4]
        if isinstance(new_photos, list):
            new_photos = ','.join(new_photos)
        cursor.execute('''
            UPDATE sales_cards SET photos = ?, title = ?, description = ?, section = ?
            WHERE card_id = ?
        ''', (new_photos, new_title, new_description, new_section, card_id))
        conn.commit()
        return True
    
    @staticmethod
    def get_last_comment_files_for_request(request_id: int):
        cursor.execute("""
            SELECT media_ids FROM comments
            WHERE request_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """, (request_id,))
        row = cursor.fetchone()
        if row and row[0]:
            return row[0].split(",")
        return []
    
    @staticmethod
    def delete_sales_card(card_id: int):
        cursor.execute("DELETE FROM sales_cards WHERE card_id = ?", (card_id,))
        conn.commit()
    
    # Темы (форум-топики)
    @staticmethod
    def get_topic(topic_type: str):
        cursor.execute("SELECT thread_id FROM topics WHERE topic_type = ?", (topic_type,))
        result = cursor.fetchone()
        return result[0] if result else None
    
    @staticmethod
    def add_comment(request_id: int, text: str, media_ids: str = ""):
        cursor.execute("""
        INSERT INTO comments (request_id, text, media_ids)
        VALUES (?, ?, ?)
    """, (request_id, text, media_ids))
        conn.commit()
    
    @staticmethod
    def save_topic(topic_type: str, thread_id: str):
        cursor.execute("INSERT OR REPLACE INTO topics (topic_type, thread_id) VALUES (?, ?)", (topic_type, thread_id))
        conn.commit()

def assign_request_to_brigade(request_id: int, brigade_id: int):
    # Удалено ALTER TABLE, так как оно вызывало ошибку и должно быть выполнено отдельно при инициализации
    cursor.execute(
        "UPDATE requests SET brigade_id = ? WHERE request_id = ?",
        (brigade_id, request_id)
    )
    conn.commit()

def get_brigade_by_id(brigade_id: int):
    cursor.execute(
        "SELECT brigade_id, name, employee_ids FROM brigades WHERE brigade_id = ?",
        (brigade_id,)
    )
    return cursor.fetchone()

def get_requests_for_brigade(brigade_id: int):
    cursor.execute(
        "SELECT * FROM requests WHERE brigade_id = ? ORDER BY created_at DESC",
        (brigade_id,)
    )
    return cursor.fetchall()

def get_requests_for_employee(emp_id: int):
    cursor.execute("SELECT brigade_id, name, employee_ids FROM brigades")
    brigades = cursor.fetchall()
    reqs = []
    for bid, name, eids in brigades:
        ids = [int(x) for x in (eids or "").split(',') if x]
        if emp_id in ids:
            reqs.extend(get_requests_for_brigade(bid))
    return reqs

def save_report(request_id, user_id, number, text, media_ids):
    with sqlite3.connect("bot_database.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO reports (request_id, user_id, report_number, text, media_ids)
            VALUES (?, ?, ?, ?, ?)
        """, (request_id, user_id, number, text, media_ids))
        conn.commit()

def get_request_by_id(request_id):
    with sqlite3.connect("bot_database.db") as conn:
        return conn.execute("SELECT * FROM requests WHERE request_id=?", (request_id,)).fetchone()

def get_user_by_request(request_id):
    with sqlite3.connect("bot_database.db") as conn:
        return conn.execute("""
            SELECT u.* FROM users u
            JOIN requests r ON u.user_id = r.user_id
            WHERE r.request_id=?
        """, (request_id,)).fetchone()

def get_last_admin_comment(request_id):
    with sqlite3.connect("bot_database.db") as conn:
        row = conn.execute("""
            SELECT text FROM comments
            WHERE request_id=?
            ORDER BY created_at DESC LIMIT 1
        """, (request_id,)).fetchone()
        return row[0] if row else None

def get_brigade_name_by_user(user_id):
    cursor.execute("SELECT brigade_id, name, employee_ids FROM brigades")
    for _, name, emp_ids in cursor.fetchall():
        if emp_ids:
            ids = [int(x) for x in emp_ids.split(',') if x.strip()]
            if user_id in ids:
                return name
    return "—"


def get_report_count_for_request(request_id):
    with sqlite3.connect("bot_database.db") as conn:
        row = conn.execute("""
            SELECT COUNT(*) FROM reports WHERE request_id=?
        """, (request_id,)).fetchone()
        return row[0] if row else 0


def get_reports_by_request(request_id):
    with sqlite3.connect("bot_database.db") as conn:
        return conn.execute("""
            SELECT * FROM reports WHERE request_id=? ORDER BY report_number ASC
        """, (request_id,)).fetchall()

def get_report_by_id(report_id):
    with sqlite3.connect("bot_database.db") as conn:
        row = conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
        if row:
            return {
                "id": row[0],
                "request_id": row[1],
                "user_id": row[2],
                "report_number": row[3],
                "text": row[4],
                "media_ids": row[5].split(",") if row[5] else [],
                "created_at": row[6]
            }


# Инициализируем системного админа, если его нет
if not Database.get_admin(SYSTEM_ADMIN_ID):
    Database.add_admin(SYSTEM_ADMIN_ID, 'system')

# ---------------------------
# Функция отправки заявки в группу (создаёт тему, если её нет)
async def send_to_group_request(context: CallbackContext, request_id: int, request_type: str, description: str,
                                created_at: datetime, user: tuple, _unused_custom_number: int):
    # Определяем тему и ключ для темы в зависимости от типа заявки.
    if request_type == "SOS":
        forum_topic_name = "SOS заявки"
        topic_key = "sos"
    elif request_type == "Запасные части":
        forum_topic_name = "Заявки Запасные части"
        topic_key = "spare_parts"
    elif request_type in ["Отдел продаж", "Отдел продаж (оборудование)"]:
        forum_topic_name = "Заявки Отдел продаж"
        topic_key = "sales"
    elif request_type in ["⚙ На установку оборудования", "Покупка оборудования"]:
        forum_topic_name = "Заявки на оборудование"
        topic_key = "equipment"
    else:
        forum_topic_name = "Заявки на обслуживание"
        topic_key = "service"
        if "ремонт" in request_type.lower():
            description += "\n#ремонт"

    if request_type in ["Запасные части", "Отдел продаж", "Отдел продаж (оборудование)", "Покупка оборудования"]:
        description = description.split("\n\n")[0].strip()

    # Определяем категорию заявки
    category = get_request_category(request_type)
    # Вычисляем номер заявки в данной категории как ранг в порядке создания:
    custom_number = Database.get_ticket_rank(category, request_id)
    
    created_at_str = created_at.strftime("%d.%m.%Y %H:%M")
    text = (
        f"Заявка #{custom_number}\n\n"
        f"Тип: {request_type}\n"
        f"Описание: {description}\n"
        f"Статус: Новая\n"
        f"Дата: {created_at_str}\n\n"
        f"Информация о пользователе:\n"
        f"ID: {user[0]}\n"
        f"Имя: {user[1]}\n"
        f"Телефон: {user[2]}\n"
        f"Адреса: {user[3]}"
    )
    sent_message = None
    thread_id = Database.get_topic(topic_key)
    if not thread_id:
        try:
            forum_topic = await context.bot.create_forum_topic(chat_id=GROUP_CHAT_ID, name=forum_topic_name)
            thread_id = str(forum_topic.message_thread_id)
            Database.save_topic(topic_key, thread_id)
        except Exception as e:
            logger.error("Ошибка создания темы (%s): %s", forum_topic_name, e)
            thread_id = None

    try:
        if thread_id is not None:
            sent_message = await context.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                message_thread_id=int(thread_id),
                text=text
            )
        else:
            sent_message = await context.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=text
            )
        if sent_message:
            Database.update_request_group_message_id(request_id, sent_message.message_id)
        logger.info("Заявка отправлена в группу успешно")
    except Exception as e:
        logger.error(f"Ошибка отправки заявки в группу: {e}")
    return sent_message

# Функция отправки файлов в отдельную тему "Файлы"
async def send_files_to_group(context: CallbackContext, request_id: int, media_ids: list, request_link: str):
    forum_topic_name = "Файлы"
    topic_key = "files"
    thread_id = Database.get_topic(topic_key)
    if not thread_id:
        try:
            forum_topic = await context.bot.create_forum_topic(chat_id=GROUP_CHAT_ID, name=forum_topic_name)
            thread_id = str(forum_topic.message_thread_id)
            Database.save_topic(topic_key, thread_id)
        except Exception as e:
            logger.error("Ошибка создания темы для файлов: %s", e)
            thread_id = None
    caption = f"Файлы заявки #{request_id}\nСсылка на заявку: {request_link}"
    file_msg = None
    try:
        if thread_id is not None:
            media = [InputMediaPhoto(media=mid) for mid in media_ids]
            sent_msgs = await context.bot.send_media_group(
                chat_id=GROUP_CHAT_ID,
                message_thread_id=int(thread_id),
                media=media
            )
            file_msg = await context.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                message_thread_id=int(thread_id),
                text=caption
            )
            Database.update_request_file_message_id(request_id, file_msg.message_id)
        else:
            media = [InputMediaPhoto(media=mid) for mid in media_ids]
            sent_msgs = await context.bot.send_media_group(
                chat_id=GROUP_CHAT_ID,
                media=media
            )
            file_msg = await context.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=caption
            )
            Database.update_request_file_message_id(request_id, file_msg.message_id)
    except Exception as e:
        logger.error(f"Ошибка отправки файлов: {e}")
    return file_msg

# ---------------------------
# Клавиатуры (пользовательские)
main_keyboard = ReplyKeyboardMarkup(
    [
        ['📝 Создать заявку', 'Запасные части', 'Отдел продаж'],
        ['Покупка оборудования'],
        ['👤 Профиль', '📋 Мои заявки'],
        ['🗓 История обслуживания']
    ],
    resize_keyboard=True
)

request_types_keyboard = ReplyKeyboardMarkup(
    [['🔧 На ремонт', '🛠 На обслуживание'],
     ['🔍 На анализ воды', '⚙ На установку оборудования'],
     ['🏠 На сервис', 'SOS'],
     ['❌ Отмена']],
    resize_keyboard=True
)

cancel_keyboard = ReplyKeyboardMarkup([['❌ Отмена']], resize_keyboard=True)

admin_main_keyboard = ReplyKeyboardMarkup(
    [
        ['Добавить админа', 'Администраторы'],
        ['Сотрудники', 'Бригады'],
        ['Заявки', 'Рассылка'],
        ['Карточки отдела продаж']
    ],
    resize_keyboard=True
)

add_admin_type_keyboard = ReplyKeyboardMarkup(
    [['Супер админ', 'Админ'], ['Назад']],
    resize_keyboard=True
)

def admin_action_keyboard(role):
    return ReplyKeyboardMarkup(
        [[('Понизить' if role=='super' else 'Повысить'), 'Удалить'], ['Назад']],
        resize_keyboard=True
    )

employee_menu_keyboard = ReplyKeyboardMarkup([['Добавить'], ['Назад']], resize_keyboard=True)
brigade_menu_keyboard = ReplyKeyboardMarkup([['Создать бригаду'], ['Назад']], resize_keyboard=True)

universal_admin_keyboard = ReplyKeyboardMarkup([['Главное меню']], resize_keyboard=True)


# ---------------------------
# Обработчики пользовательской части
async def start(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    if Database.get_admin(user_id):
        await update.message.reply_text("Добро пожаловать в админ‑панель", reply_markup=admin_main_keyboard)
        return ADMIN_MAIN
    if Database.get_employee(user_id):
        reply_markup = ReplyKeyboardMarkup(
            [['Заявки'], ['Назад']],
            resize_keyboard=True
        )
        await update.message.reply_text("👷 Панель сотрудника", reply_markup=reply_markup)
        return EMPLOYEE_PANEL

    user = Database.get_user(user_id)
    if user:
        await update.message.reply_text("Добро пожаловать! Выберите действие:", reply_markup=main_keyboard)
        return ConversationHandler.END
    await update.message.reply_text(
        "Добро пожаловать! Давайте пройдем регистрацию. Пожалуйста, введите ваше имя:",
        reply_markup=ReplyKeyboardRemove()
    )
    return USER_NAME


async def get_name(update: Update, context: CallbackContext) -> int:
    context.user_data['name'] = update.message.text
    reply_keyboard = [["Да", "Нет"]]
    await update.message.reply_text("Вы клиент? (Да/Нет):",
                                    reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True))
    return USER_CLIENT

async def get_client(update: Update, context: CallbackContext) -> int:
    context.user_data['client'] = update.message.text
    reply_keyboard = [[KeyboardButton("Поделиться контактом 📱", request_contact=True)]]
    await update.message.reply_text("Спасибо! Теперь поделитесь вашим номером телефона:",
                                    reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True))
    return USER_PHONE

async def get_phone(update: Update, context: CallbackContext) -> int:
    if update.message.contact:
        context.user_data['phone'] = update.message.contact.phone_number
    else:
        context.user_data['phone'] = update.message.text
    await update.message.reply_text("Отлично! Теперь введите ваш адрес:", reply_markup=ReplyKeyboardRemove())
    return USER_ADDRESS

async def get_address(update: Update, context: CallbackContext) -> int:
    if 'addresses' not in context.user_data:
        context.user_data['addresses'] = []
    context.user_data['addresses'].append(update.message.text)
    reply_keyboard = [["Да", "Нет"]]
    await update.message.reply_text("Адрес сохранен! Хотите добавить еще один адрес?",
                                    reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True))
    return USER_ADDRESSES

async def registration_complete(update: Update, context: CallbackContext) -> int:
    if update.message.text.lower() == 'да':
        await update.message.reply_text("Введите следующий адрес:", reply_markup=ReplyKeyboardRemove())
        return USER_ADDRESS
    user_id = update.message.from_user.id
    Database.save_user(user_id,
                       context.user_data['name'],
                       context.user_data['phone'],
                       context.user_data['addresses'],
                       context.user_data.get('client', "Нет"))
    await update.message.reply_text("Регистрация завершена! 🎉", reply_markup=main_keyboard)
    return ConversationHandler.END

async def create_request_start(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Выберите тип заявки:", reply_markup=request_types_keyboard)
    return REQUEST_TYPE

async def get_request_type(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    user = Database.get_user(user_id)
    if not user:
        await update.message.reply_text("❗️ Вам нужно пройти регистрацию для отправки заявки!")
        return ConversationHandler.END
    req_type = update.message.text
    if req_type == "🛠 На обслуживание":
        req_type = "обслуживание"
    context.user_data['request_type'] = req_type
    context.user_data['media_ids'] = []
    if update.message.text == "SOS":
        return await get_sos_phone(update, context)
    await update.message.reply_text("Опишите проблему подробно:", reply_markup=cancel_keyboard)
    return USER_PROBLEM_DESCRIPTION

async def get_problem_description(update: Update, context: CallbackContext) -> int:
    if update.message.text == "❌ Отмена":
        return await cancel(update, context)
    context.user_data['description'] = update.message.text
    await update.message.reply_text("При необходимости прикрепите фото/видео (до 3 файлов), затем нажмите '📎 Готово'",
                                    reply_markup=ReplyKeyboardMarkup([['📎 Готово'], ['❌ Отмена']], resize_keyboard=True))
    return USER_MEDIA_UPLOAD

async def handle_media(update: Update, context: CallbackContext) -> int:
    if update.message.text == "❌ Отмена":
        return await cancel(update, context)
    if update.message.photo:
        context.user_data.setdefault('media_ids', []).append(update.message.photo[-1].file_id)
    elif update.message.video:
        context.user_data.setdefault('media_ids', []).append(update.message.video.file_id)
    elif update.message.document:
        context.user_data.setdefault('media_ids', []).append(update.message.document.file_id)
    await update.message.reply_text(f"Файл получен ({len(context.user_data.get('media_ids', []))}). Если все файлы прикреплены, нажмите '📎 Готово'.",
                                    reply_markup=ReplyKeyboardMarkup([['📎 Готово'], ['❌ Отмена']], resize_keyboard=True))
    return USER_MEDIA_UPLOAD

def get_request_category(request_type: str) -> str:
    if request_type == "SOS":
        return "SOS"
    elif request_type in ["Отдел продаж", "Отдел продаж (оборудование)"]:
        return "Отдел продаж"
    elif request_type == "Запасные части":
        return "Запасные части"
    elif request_type == "Покупка оборудования":
        return "Покупка оборудования"
    else:
        return "Заявки на обслуживание"


async def finish_request(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    user = Database.get_user(user_id)
    if not user:
        await update.message.reply_text("❗️ Вам нужно пройти регистрацию для отправки заявки!")
        return ConversationHandler.END

    # сбор данных заявки
    request_type = context.user_data['request_type']
    description  = context.user_data['description']
    media_ids    = context.user_data.get('media_ids', [])[:3]
    created_at   = datetime.now()

    category       = get_request_category(request_type)
    custom_number = Database.get_custom_number(category) + 1

    # создаём заявку
    request_id    = Database.create_request(
        user_id, request_type, category, description, media_ids, created_at
    )
    # отправляем в группу и, при наличии, файлы
    sent_message = await send_to_group_request(
        context, request_id, request_type, description,
        created_at, user, custom_number
    )
    if media_ids and sent_message:
        chat_str     = str(GROUP_CHAT_ID)
        chat_link    = chat_str[4:] if chat_str.startswith("-100") else chat_str
        request_link = f"https://t.me/c/{chat_link}/{sent_message.chat.id}/{sent_message.message_id}"
        await send_files_to_group(context, request_id, media_ids, request_link)

    # ← НОВОЕ: оповещение админа о новой заявке
    await notify_admin_new_request(context, request_id)

    await update.message.reply_text(
        "✅ Заявка создана и отправлена в группу!",
        reply_markup=main_keyboard
    )
    return ConversationHandler.END

async def get_sos_phone(update: Update, context: CallbackContext) -> int:
    if update.message.text == "❌ Отмена":
        return await cancel(update, context)
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text
    user_id = update.message.from_user.id
    user = Database.get_user(user_id)
    if not user:
        await update.message.reply_text("❗️ Вам нужно пройти регистрацию для отправки SOS-заявки!")
        return ConversationHandler.END
    description = ""
    category = "SOS"
    custom_number = Database.get_custom_number(category) + 1
    request_id = Database.create_request(user_id, "SOS", category, description, [], datetime.now())
    await send_to_group_request(context, request_id, "SOS", description, datetime.now(), user, custom_number)
    await update.message.reply_text("✅ SOS-заявка создана и отправлена в группу!", reply_markup=main_keyboard)
    return ConversationHandler.END

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ConversationHandler, CallbackQueryHandler


# Изменённая функция показа профиля пользователя – добавлена inline‑кнопка "Изменить профиль"
async def show_profile(update: Update, context: CallbackContext) -> None:
    user = Database.get_user(update.message.from_user.id)
    if not user:
        await update.message.reply_text("Сначала пройдите регистрацию /start")
        return
    profile_text = (f"👤 Имя: {user[1]}\n📱 Телефон: {user[2]}\n"
                    f"🏠 Адреса:\n• " + "\n• ".join(user[3].split(',')) +
                    f"\n✅ Клиент: {user[4]}")
    # Добавляем inline-кнопку "Изменить профиль"
    inline_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("Изменить профиль", callback_data="edit_profile")]
    ])
    await update.message.reply_text(profile_text, reply_markup=inline_markup)

# ---------------------------------------------
# Обработчик inline-кнопки для редактирования профиля
async def edit_profile_start_callback(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    # Показываем меню выбора того, что изменить
    reply_keyboard = ReplyKeyboardMarkup(
        [['Имя', 'Телефон'], ['Адрес'], ['Назад']],
        one_time_keyboard=True, resize_keyboard=True
    )
    await query.message.reply_text("Что вы хотите изменить в профиле?", reply_markup=reply_keyboard)
    return EDIT_PROFILE_CHOICE

# Обработка выбора в меню редактирования профиля
async def edit_profile_choice(update: Update, context: CallbackContext) -> int:
    choice = update.message.text.strip()
    if choice == "Имя":
        await update.message.reply_text("Введите новое имя:", reply_markup=ReplyKeyboardRemove())
        return EDIT_PROFILE_NAME
    elif choice == "Телефон":
        await update.message.reply_text("Введите новый телефон:", reply_markup=ReplyKeyboardRemove())
        return EDIT_PROFILE_PHONE
    elif choice == "Адрес":
        reply_keyboard = ReplyKeyboardMarkup(
            [['Сменить Адрес', 'Добавить Адрес'], ['Удалить адрес'], ['Назад']],
            one_time_keyboard=True, resize_keyboard=True
        )
        await update.message.reply_text("Выберите действие с адресами:", reply_markup=reply_keyboard)
        return EDIT_PROFILE_ADDRESS_OPTS
    elif choice == "Назад":
        # Возврат к просмотру профиля
        await show_profile(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text("Пожалуйста, выберите один из вариантов.")
        return EDIT_PROFILE_CHOICE

# Редактирование имени пользователя
async def edit_profile_name(update: Update, context: CallbackContext) -> int:
    new_name = update.message.text.strip()
    user_id = update.message.from_user.id
    # Получаем текущие данные пользователя
    user = Database.get_user(user_id)
    if not user:
        await update.message.reply_text("Ошибка: пользователь не найден.")
        return ConversationHandler.END
    # Обновляем имя (остальные данные оставляем без изменений)
    Database.save_user(user_id, new_name, user[2], user[3].split(','), user[4])
    await update.message.reply_text("Имя успешно изменено!")
    await show_profile(update, context)
    return ConversationHandler.END

# Редактирование телефона пользователя
async def edit_profile_phone(update: Update, context: CallbackContext) -> int:
    new_phone = update.message.text.strip()
    user_id = update.message.from_user.id
    user = Database.get_user(user_id)
    if not user:
        await update.message.reply_text("Ошибка: пользователь не найден.")
        return ConversationHandler.END
    Database.save_user(user_id, user[1], new_phone, user[3].split(','), user[4])
    await update.message.reply_text("Телефон успешно изменён!")
    await show_profile(update, context)
    return ConversationHandler.END

# Обработка выбора действий с адресами
async def edit_profile_address_choice(update: Update, context: CallbackContext) -> int:
    choice = update.message.text.strip()
    if choice == "Сменить Адрес":
        await update.message.reply_text("Введите номер адреса для замены (начиная с 1):", reply_markup=ReplyKeyboardRemove())
        return EDIT_PROFILE_ADDRESS_CHANGE_INDEX
    elif choice == "Добавить Адрес":
        await update.message.reply_text("Введите новый адрес для добавления:", reply_markup=ReplyKeyboardRemove())
        return EDIT_PROFILE_ADDRESS_ADD
    elif choice == "Удалить адрес":
        user = Database.get_user(update.message.from_user.id)
        addresses = user[3].split(',')
        if len(addresses) < 2:
            await update.message.reply_text("Удалять адрес нельзя, так как в профиле только один адрес.")
            await show_profile(update, context)
            return ConversationHandler.END
        await update.message.reply_text("Введите номер адреса для удаления (начиная с 1):", reply_markup=ReplyKeyboardRemove())
        return EDIT_PROFILE_ADDRESS_DEL
    elif choice == "Назад":
        await show_profile(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text("Пожалуйста, выберите корректное действие.")
        return EDIT_PROFILE_ADDRESS_OPTS

# Получение номера адреса для замены
async def edit_profile_address_change_index(update: Update, context: CallbackContext) -> int:
    try:
        index = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Неверный формат. Введите число, обозначающее номер адреса.")
        return EDIT_PROFILE_ADDRESS_CHANGE_INDEX
    context.user_data['address_change_index'] = index - 1  # Приводим к индексации с 0
    await update.message.reply_text("Введите новый адрес:")
    return EDIT_PROFILE_ADDRESS_CHANGE_INPUT

# Получение нового адреса для замены выбранного
async def edit_profile_address_change_input(update: Update, context: CallbackContext) -> int:
    new_address = update.message.text.strip()
    user_id = update.message.from_user.id
    user = Database.get_user(user_id)
    addresses = user[3].split(',')
    index = context.user_data.get('address_change_index', -1)
    if index < 0 or index >= len(addresses):
        await update.message.reply_text("Неверно указан номер адреса.")
        return ConversationHandler.END
    addresses[index] = new_address
    Database.save_user(user_id, user[1], user[2], addresses, user[4])
    await update.message.reply_text("Адрес успешно изменён!")
    await show_profile(update, context)
    return ConversationHandler.END

# Добавление нового адреса
async def edit_profile_address_add(update: Update, context: CallbackContext) -> int:
    new_address = update.message.text.strip()
    user_id = update.message.from_user.id
    user = Database.get_user(user_id)
    addresses = user[3].split(',')
    addresses.append(new_address)
    Database.save_user(user_id, user[1], user[2], addresses, user[4])
    await update.message.reply_text("Адрес успешно добавлен!")
    await show_profile(update, context)
    return ConversationHandler.END

# Удаление адреса
async def edit_profile_address_del(update: Update, context: CallbackContext) -> int:
    try:
        index = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Неверный формат. Введите номер адреса.")
        return EDIT_PROFILE_ADDRESS_DEL
    user_id = update.message.from_user.id
    user = Database.get_user(user_id)
    addresses = user[3].split(',')
    if index < 1 or index > len(addresses):
        await update.message.reply_text("Указан неверный номер адреса.")
        return EDIT_PROFILE_ADDRESS_DEL
    # Удаляем адрес под номером index
    del addresses[index - 1]
    Database.save_user(user_id, user[1], user[2], addresses, user[4])
    await update.message.reply_text("Адрес успешно удалён!")
    await show_profile(update, context)
    return ConversationHandler.END

async def cancel(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    if Database.get_admin(user_id):
        await update.message.reply_text("Действие отменено. Главное меню админ-панели.", reply_markup=admin_main_keyboard)
        return ADMIN_MAIN
    else:
        await update.message.reply_text("Действие отменено", reply_markup=main_keyboard)
        return ConversationHandler.END
    
# ---------------------------
# Обработчики админ-панели
# После выбора заявки отправляем сначала полное описание, а затем панель управления как текстовые кнопки
async def admin_requests_category_menu(update: Update, context: CallbackContext) -> int:
    keyboard = [
        ['Заявки на обслуживание', 'Отдел продаж'],
        ['Запасные части', 'Покупка оборудования'],
        ['SOS'],
        ['Назад']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Выберите категорию заявок:", reply_markup=reply_markup)
    return ADMIN_REQ_CATEGORY


async def admin_list_requests_by_category(update: Update, context: CallbackContext) -> int:
    category = update.message.text
    if category == 'Назад':
        return await admin_main_menu(update, context)
    # Сохраним выбранную категорию в контексте для дальнейшего использования
    context.user_data['selected_category'] = category
    requests = Database.get_requests_by_category(category)
    keyboard = []
    if requests:
        total = len(requests)
        for i, req in enumerate(requests):
            custom_number = total - i
            keyboard.append([f"Заявка #{custom_number}"])
    else:
        keyboard.append(["Заявок нет"])
    keyboard.append(["Назад"])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(f"Заявки для категории «{category}»:", reply_markup=reply_markup)
    return ADMIN_REQ_CATEGORY_LIST

async def admin_show_requests_list(update: Update, context: CallbackContext) -> int:
    selected_category = context.user_data.get('selected_category', "Заявки на обслуживание")
    requests_all = Database.get_requests_by_category(selected_category)
    keyboard = []
    if requests_all:
        total = len(requests_all)
        for i, req in enumerate(requests_all):
            custom_number = total - i
            keyboard.append([f"Заявка #{custom_number}"])
    else:
        keyboard.append(["Заявок нет"])
    keyboard.append(["Назад"])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    message_text = f"Заявки для категории «{selected_category}»: \nВыберите заявку:"
    if update.message:
        await update.message.reply_text(message_text, reply_markup=reply_markup)
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.message.reply_text(message_text, reply_markup=reply_markup)
    else:
        logger.error("Нет сообщения для вывода списка заявок")
    return ADMIN_REQ_CATEGORY_LIST

# После выбора заявки в списке админ получает два сообщения: подробное описание и панель управления (reply-клавиатура)
async def admin_requests_list_handler(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == 'Назад':
        return await admin_main_menu(update, context)

    if text.startswith("Заявка #"):
        selected_category = context.user_data.get('selected_category', "Заявки на обслуживание")
        requests_all = Database.get_requests_by_category(selected_category)
        total = len(requests_all)

        try:
            num = int(text.split("#")[1])
        except:
            await update.message.reply_text("Неверный формат заявки", reply_markup=admin_main_keyboard)
            return ADMIN_MAIN

        req = None
        for i, r in enumerate(requests_all):
            if total - i == num:
                req = r
                break
        if not req:
            await update.message.reply_text("Заявка не найдена", reply_markup=admin_main_keyboard)
            return ADMIN_MAIN

        context.user_data['current_request'] = req
        user = Database.get_user(req[1])
        user_info = (
            f"ID: {user[0]}\nИмя: {user[1]}\nТелефон: {user[2]}\nАдреса: {user[3]}"
            if user else "Информация о пользователе отсутствует"
        )

        detail_text = (
            f"Заявка #{num}\n\n"
            f"Тип: {req[2]}\n"
            f"Описание: {req[3]}\n"
            f"Статус: {req[6]}\n"
            f"Дата: {req[5]}\n\n"
            f"Информация о пользователе:\n{user_info}"
        )

        await update.message.reply_text(detail_text)

        control_keyboard = ReplyKeyboardMarkup([
            ['Добавить комментарий'],
            ['Изменить статус', 'Файлы'],
            ['📄 Отчеты'],
            ['Назад']
        ], resize_keyboard=True)

        await update.message.reply_text("Панель управления заявкой:", reply_markup=control_keyboard)
        return ADMIN_CONTROL_REQUEST

    return await admin_show_requests_list(update, context)

# Обработка текстовых команд из панели управления заявкой
async def admin_control_request_handler(update: Update, context: CallbackContext) -> int:
    text = update.message.text.strip()
    req = context.user_data.get('current_request')
    
    if text == 'Назад':
        return await admin_show_requests_list(update, context)
    
    if text == 'Добавить комментарий':
        await update.message.reply_text("Введите текст комментария:", reply_markup=ReplyKeyboardRemove())
        return ADMIN_COMMENT_TEXT
        
    if text == 'Изменить статус':
        status_kb = ReplyKeyboardMarkup(
            [['Новая', 'В работе', 'Завершена'], ['Назад']],
            resize_keyboard=True
        )
        await update.message.reply_text("Выберите новый статус:", reply_markup=status_kb)
        return ADMIN_CONTROL_REQUEST
    
    if text == 'Файлы':
        media_ids = req[4].split(',') if req[4] else []
        if not media_ids:
            await update.message.reply_text("Файлы отсутствуют.")
            return ADMIN_CONTROL_REQUEST
        
        await update.message.reply_text("Файлы заявки:")
        media_group = []
        for file_id in media_ids:
            if file_id.startswith('AgAC'):  # Photo
                media_group.append(InputMediaPhoto(file_id))
            else:  # Document
                media_group.append(InputMediaDocument(file_id))
        
        await context.bot.send_media_group(
            chat_id=update.message.chat_id,
            media=media_group
        )
        return ADMIN_CONTROL_REQUEST

    if text in ['Новая', 'В работе', 'Завершена']:
        # Обновляем статус...
        new_status = text
        Database.update_request_status(req[0], new_status)
        user = Database.get_user(req[1])
        # Формат даты
        try:
            dt = datetime.fromisoformat(req[5])
        except:
            dt = datetime.strptime(req[5], '%Y-%m-%d %H:%M:%S.%f')
        date_str = dt.strftime("%d.%m.%Y %H:%M")
        # Номер в категории
        custom_number = Database.get_ticket_rank(req[9], req[0])
        # Новый текст
        new_text = (
            f"Заявка #{custom_number}\n\n"
            f"Тип: {req[2]}\n"
            f"Описание: {req[3]}\n"
            f"Статус: {new_status}\n"
            f"Дата: {date_str}\n\n"
        )
        if user:
            new_text += (
                "Информация о пользователе:\n"
                f"ID: {user[0]}\n"
                f"Имя: {user[1]}\n"
                f"Телефон: {user[2]}\n"
                f"Адреса: {user[3]}"
            )
        else:
            new_text += "Информация о пользователе отсутствует"

        # Пытаемся отредактировать старое сообщение, иначе отправляем новое
        if req[7]:
            try:
                await context.bot.edit_message_text(
                    chat_id=GROUP_CHAT_ID,
                    message_id=req[7],
                    text=new_text
                )
            except:
                thread = Database.get_topic(req[9])
                kwargs = {"chat_id": GROUP_CHAT_ID, "text": new_text}
                if thread:
                    kwargs["message_thread_id"] = int(thread)
                sent = await context.bot.send_message(**kwargs)
                Database.update_request_group_message_id(req[0], sent.message_id)
        else:
            thread = Database.get_topic(req[9])
            kwargs = {"chat_id": GROUP_CHAT_ID, "text": new_text}
            if thread:
                kwargs["message_thread_id"] = int(thread)
            sent = await context.bot.send_message(**kwargs)
            Database.update_request_group_message_id(req[0], sent.message_id)

        # Уведомление об изменении статуса
        chat_str = str(GROUP_CHAT_ID)
        link_id = req[7] or sent.message_id
        link = f"https://t.me/c/{chat_str[4:] if chat_str.startswith('-100') else chat_str}/{link_id}"
        notify = (
            f"Статус заявки #{custom_number} изменён на: {new_status}\n"
            f"Категория: {req[9]}\n"
            f"Ссылка: {link}"
        )
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=notify)

        await update.message.reply_text("Статус изменён", reply_markup=admin_main_keyboard)
        return ADMIN_MAIN

    if text == 'Файлы':
        media_ids = req[4].split(',') if req[4] else []
        if not media_ids:
            await update.message.reply_text("Файлы отсутствуют.", reply_markup=admin_main_keyboard)
            return ADMIN_MAIN
        # Отправляем медиа‑группу
        sent = await context.bot.send_media_group(
            chat_id=update.message.chat_id,
            media=[InputMediaPhoto(media=m) for m in media_ids]
        )
        context.user_data['admin_files_msg_ids'] = [m.message_id for m in sent]
        # Кнопка «Назад»
        back = await update.message.reply_text(
            "Нажмите 'Назад', чтобы скрыть файлы",
            reply_markup=ReplyKeyboardMarkup([['Назад']], resize_keyboard=True)
        )
        context.user_data['admin_files_back_msg_id'] = back.message_id
        return ADMIN_VIEW_FILES

    await update.message.reply_text("Неверная команда.", reply_markup=admin_main_keyboard)
    return ADMIN_MAIN

async def admin_main_menu(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Админ-панель", reply_markup=admin_main_keyboard)
    return ADMIN_MAIN

async def admin_choose_add_type(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == 'Назад':
        return await admin_main_menu(update, context)
    if text not in ['Супер админ', 'Админ']:
        await update.message.reply_text("Пожалуйста, выберите корректный тип", reply_markup=add_admin_type_keyboard)
        return ADMIN_CHOOSE_ADD_TYPE
    context.user_data['add_admin_role'] = text.lower()
    await update.message.reply_text("Введите user_id пользователя, которого хотите назначить:", reply_markup=universal_admin_keyboard)
    return ADMIN_WAIT_FOR_USER_ID

async def admin_receive_user_id(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text.lower() in ['назад', 'главное меню']:
        return await admin_main_menu(update, context)
    try:
        user_id = int(text.strip())
    except ValueError:
        await update.message.reply_text("Неверный формат user_id. Введите число.", reply_markup=universal_admin_keyboard)
        return ADMIN_WAIT_FOR_USER_ID
    role = context.user_data.get('add_admin_role')
    caller = Database.get_admin(update.message.from_user.id)
    if role == 'супер админ' and caller[1] not in ['system']:
        await update.message.reply_text("Только системный админ может назначать супер админов.", reply_markup=admin_main_keyboard)
        return await admin_main_menu(update, context)
    Database.add_admin(user_id, 'super' if role=='супер админ' else 'admin')
    await update.message.reply_text(f"Пользователь {user_id} успешно добавлен на роль: {role.capitalize()}",
                                    reply_markup=universal_admin_keyboard)
    return ADMIN_MAIN

async def admin_list_choice(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == 'Назад':
        return await admin_main_menu(update, context)
    try:
        uid = int(text.split()[0])
    except Exception:
        await update.message.reply_text("Неверный формат, попробуйте еще раз", reply_markup=universal_admin_keyboard)
        return ADMIN_MAIN
    context.user_data['target_admin_id'] = uid
    target = Database.get_admin(uid)
    if not target:
        await update.message.reply_text("Админ не найден", reply_markup=universal_admin_keyboard)
        return await admin_main_menu(update, context)
    reply_markup = admin_action_keyboard(target[1])
    await update.message.reply_text(f"Выбран админ: {uid} ({target[1]}). Выберите действие:", reply_markup=reply_markup)
    return ADMIN_MAIN

async def employee_menu(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == 'Добавить':
        await update.message.reply_text(
            "Введите user_id сотрудника, которого хотите добавить:",
            reply_markup=universal_admin_keyboard
        )
        return EMPLOYEE_WAIT_FOR_USER_ID  # ← обязательно
    elif text == 'Назад':
        return await admin_main_menu(update, context)
    else:
        return await admin_main_menu(update, context)

async def employee_receive_user_id(update: Update, context: CallbackContext) -> int:
    text = update.message.text.strip()
    if text.lower() in ['назад', 'главное меню']:
        return await admin_main_menu(update, context)
    try:
        emp_id = int(text)
    except ValueError:
        await update.message.reply_text(
            "Неверный формат user_id. Введите число.",
            reply_markup=universal_admin_keyboard
        )
        return EMPLOYEE_WAIT_FOR_USER_ID
    context.user_data['new_emp_id'] = emp_id  # ← вот это обязательно
    await update.message.reply_text(
        "Введите ФИО сотрудника:",
        reply_markup=universal_admin_keyboard
    )
    return EMPLOYEE_WAIT_FOR_NAME


async def brigade_menu(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == 'Создать бригаду':
        employees = Database.get_all_employees()
        if not employees:
            await update.message.reply_text(
                "Сотрудников нет, сначала добавьте сотрудника.",
                reply_markup=brigade_menu_keyboard
            )
            return BRIGADE_MENU

        await update.message.reply_text(
            "Введите название бригады и через запятую ID сотрудников.\n"
            "Пример: Бригада А, 123456, 654321",
            reply_markup=universal_admin_keyboard
        )
        return BRIGADE_WAIT_FOR_DETAILS

    if text == 'Назад':
        return await admin_main_menu(update, context)

    # на всякий случай — снова меню бригад
    return BRIGADE_MENU

async def handle_brigade_details(update: Update, context: CallbackContext) -> int:
    text = update.message.text.strip()
    try:
        parts = [p.strip() for p in text.split(',')]
        name = parts[0]
        ids = [int(p) for p in parts[1:] if p.isdigit()]
        if not name or not ids:
            raise ValueError
    except Exception:
        await update.message.reply_text(
            "❌ Неверный формат. Введите так:\n"
            "Название, id1, id2, id3",
            reply_markup=universal_admin_keyboard
        )
        return BRIGADE_WAIT_FOR_DETAILS

    # сохраняем
    Database.add_brigade(name, ids)
    await update.message.reply_text(
        f"✅ Бригада «{name}» создана ({len(ids)} чел.)",
        reply_markup=brigade_menu_keyboard
    )
    return BRIGADE_MENU

async def mailing_handler(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    count = 0
    for user in users:
        try:
            await context.bot.send_message(chat_id=user[0], text=f"Рассылка: {text}")
            count += 1
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение пользователю {user[0]}: {e}")
    await update.message.reply_text(f"Рассылка отправлена {count} пользователям.", reply_markup=universal_admin_keyboard)
    return await admin_main_menu(update, context)

# ---------------------------
# Обработчики карточек отдела продаж
async def sales_cards_user_view(update: Update, context: CallbackContext) -> None:
    section = update.message.text
    all_cards = Database.get_all_sales_cards()
    # Фильтруем карточки по разделу
    cards = [card for card in all_cards if card[4] == section]
    if not cards:
        await update.message.reply_text(f"Нет карточек для раздела {section}.")
        return
    context.user_data['sales_cards'] = cards
    context.user_data['sales_card_index'] = 0
    await send_sales_card(update, context, 0)

async def send_sales_card(update: Update, context: CallbackContext, index: int) -> None:
    cards = context.user_data.get('sales_cards')
    if not cards or index < 0 or index >= len(cards):
        return
    card = cards[index]
    photos = card[1].split(',')
    title = card[2]
    description = card[3]
    section = card[4]
    caption = f"<b>{title}</b>\n\n{description}"
    card_id = card[0]
    keyboard_buttons = []
    keyboard_buttons.append([
        InlineKeyboardButton(f"Фото {len(photos)}", callback_data=f"view_photos_{card_id}"),
        InlineKeyboardButton("Заявка", callback_data=f"send_request_{card_id}")
    ])
    nav_buttons = []
    total = len(cards)
    if total > 1:
        current = index
        if current > 0:
            nav_buttons.append(InlineKeyboardButton("Предыдущее", callback_data=f"card_{current-1}"))
        if current < total - 1:
            nav_buttons.append(InlineKeyboardButton("Следующее", callback_data=f"card_{current+1}"))
    if nav_buttons:
        keyboard_buttons.append(nav_buttons)
    keyboard_buttons.append([InlineKeyboardButton("Главное меню", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard_buttons)
    if update.message:
        await update.message.reply_photo(photo=photos[0], caption=caption, parse_mode="HTML", reply_markup=reply_markup)
    else:
        try:
            media = InputMediaPhoto(media=photos[0], caption=caption, parse_mode="HTML")
            await update.callback_query.edit_message_media(media=media, reply_markup=reply_markup)
        except Exception as e:
            await update.callback_query.message.reply_photo(photo=photos[0], caption=caption, parse_mode="HTML", reply_markup=reply_markup)

# Функция для навигации между карточками – редактирование сообщения
async def edit_sales_card_message(query, context, card, index, total):
    photos = card[1].split(',')
    card_id = card[0]
    title = card[2]
    description = card[3]
    section = card[4]
    caption = f"<b>{title}</b>\n\n{description}\n\nРаздел: {section}"
    keyboard_buttons = []
    keyboard_buttons.append([
        InlineKeyboardButton(f"Фото {len(photos)}", callback_data=f"view_photos_{card_id}"),
        InlineKeyboardButton("Заявка", callback_data=f"send_request_{card_id}")
    ])
    nav_buttons = []
    if total > 1:
        if index > 0:
            nav_buttons.append(InlineKeyboardButton("Предыдущее", callback_data=f"card_{index-1}"))
        if index < total - 1:
            nav_buttons.append(InlineKeyboardButton("Следующее", callback_data=f"card_{index+1}"))
    if nav_buttons:
        keyboard_buttons.append(nav_buttons)
    keyboard_buttons.append([InlineKeyboardButton("Главное меню", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard_buttons)
    media = InputMediaPhoto(media=photos[0], caption=caption, parse_mode="HTML")
    try:
        await query.edit_message_media(media=media, reply_markup=reply_markup)
    except Exception as e:
        await query.message.reply_photo(photo=photos[0], caption=caption, parse_mode="HTML", reply_markup=reply_markup)

# Callback-обработчик для карточек
async def sales_cards_callback_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    data = query.data
    await query.answer()
    
    if data.startswith("card_"):
        try:
            index = int(data.split("_")[1])
        except Exception:
            return
        cards = context.user_data.get('sales_cards')
        if not cards or index < 0 or index >= len(cards):
            return
        context.user_data['sales_card_index'] = index
        card = cards[index]
        await edit_sales_card_message(query, context, card, index, len(cards))
    
    elif data.startswith("view_photos_"):
        try:
            card_id = int(data.split("_")[2])
        except Exception:
            return
        card = Database.get_sales_card(card_id)
        if not card:
            await query.edit_message_text("Карточка не найдена.")
            return
        photos = card[1].split(',')
        if photos:
            # Отправляем медиа-группу
            sent_msgs = await context.bot.send_media_group(
                chat_id=query.message.chat_id,
                media=[InputMediaPhoto(media=ph) for ph in photos]
            )
            # Сохраняем ID сообщений медиа-группы для последующего удаления
            context.user_data['media_group_msg_ids'] = [msg.message_id for msg in sent_msgs]
            # Отправляем дополнительное сообщение с кнопкой "Назад" прямо под медиа-группой
            back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="photos_back")]])
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Нажмите 'Назад', чтобы удалить фото.",
                reply_markup=back_markup
            )
        else:
            await query.edit_message_text("Фотографии отсутствуют.")
    
    elif data == "photos_back":
        # Получаем id сообщений медиа-группы и удаляем их, а также сообщение с кнопкой "Назад"
        try:
            # Удаляем сообщение с кнопкой "Назад"
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
        except Exception as e:
            logger.error(f"Ошибка удаления сообщения с кнопкой 'Назад': {e}")
        msg_ids = context.user_data.get('media_group_msg_ids', [])
        for msg_id in msg_ids:
            try:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
            except Exception as e:
                logger.error(f"Ошибка удаления сообщения медиа-группы (ID: {msg_id}): {e}")
        context.user_data.pop('media_group_msg_ids', None)
    
    elif data.startswith("send_request_"):
        try:
            card_id = int(data.split("_")[2])
        except Exception:
            await query.message.reply_text("Неверный формат запроса.")
            return
        card = Database.get_sales_card(card_id)
        if not card:
            await query.message.reply_text("Карточка не найдена.")
            return
        user_id = query.from_user.id
        user = Database.get_user(user_id)
        if not user:
            await query.message.reply_text("Вы не зарегистрированы.")
            return
        created_at = datetime.now()
        # Формируем описание заявки с упоминанием названия карточки
        request_desc = f"{card[2]}\n\n{card[3]}"
        request_type = card[4]
        request_id = Database.create_request(user_id, request_type, request_type, request_desc, [], created_at)
        custom_number = Database.get_custom_number(request_type) + 1
        await send_to_group_request(context, request_id, request_type, request_desc, created_at, user, custom_number)
        await query.message.reply_text("Заявка отправлена в группу!")
    
    elif data == "main_menu":
        await query.message.reply_text("Главное меню", reply_markup=main_keyboard)

# ---------------------------
# Админ-панель: обработчики управления заявками текстовыми кнопками
async def admin_main_menu(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Админ-панель", reply_markup=admin_main_keyboard)
    return ADMIN_MAIN

async def admin_entry(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    admin = Database.get_admin(user_id)
    if not admin:
        await update.message.reply_text("У вас нет прав для доступа к админ-панели")
        return ConversationHandler.END
    await update.message.reply_text("Добро пожаловать в админ-панель", reply_markup=admin_main_keyboard)
    return ADMIN_MAIN

async def admin_main_menu(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Админ-панель", reply_markup=admin_main_keyboard)
    return ADMIN_MAIN

async def admin_menu_choice(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == 'Добавить админа':
        await update.message.reply_text("Выберите тип админа:", reply_markup=add_admin_type_keyboard)
        return ADMIN_CHOOSE_ADD_TYPE
    elif text == 'Администраторы':
        admins = Database.get_all_admins()
        buttons = []
        for a in admins:
            buttons.append(f"{a[0]} ({a[1]})")
        if not buttons:
            await update.message.reply_text("Список администраторов пуст", reply_markup=universal_admin_keyboard)
            return ADMIN_MAIN
        reply_markup = ReplyKeyboardMarkup([[b] for b in buttons] + [['Назад']], resize_keyboard=True)
        await update.message.reply_text("Список администраторов:", reply_markup=reply_markup)
        return ADMIN_LIST_MENU
    elif text == 'Сотрудники':
        employees = Database.get_all_employees()
        if not employees:
            await update.message.reply_text("Сотрудников пока нет", reply_markup=employee_menu_keyboard)
            return EMPLOYEE_MENU
        else:
            response = "Список сотрудников:\n"
            for emp in employees:
                response += f"{emp[0]} - {emp[1]}\n"
            await update.message.reply_text(response, reply_markup=employee_menu_keyboard)
            return EMPLOYEE_MENU
    elif text == 'Бригады':
        brigades = Database.get_all_brigades()
        if not brigades:
            await update.message.reply_text("Бригад нет", reply_markup=brigade_menu_keyboard)
            return BRIGADE_MENU
        else:
            response = "Список бригад:\n"
            for b in brigades:
                emps = b[2].split(',') if b[2] else []
                response += f"{b[1]} - участников: {len(emps)}\n"
            await update.message.reply_text(response, reply_markup=brigade_menu_keyboard)
            return BRIGADE_MENU
    elif text == 'Заявки':
        # Вызываем новую функцию, которая выводит категории заявок
        return await admin_requests_category_menu(update, context)
    elif text == 'Рассылка':
        await update.message.reply_text("Введите текст для рассылки:", reply_markup=universal_admin_keyboard)
        return MAILING_WAIT_FOR_TEXT
    elif text == 'Карточки отдела продаж':
        # Обеспечиваем вывод меню карточек, а не списка заявок
        sales_cards_menu_keyboard = ReplyKeyboardMarkup(
            [['Создать карточку', 'Редактировать карточку'],
             ['Удалить карточку', 'Назад']],
            resize_keyboard=True)
        await update.message.reply_text("Меню карточек отдела продаж:", reply_markup=sales_cards_menu_keyboard)
        return ADMIN_SALES_CARDS_MENU
    else:
        await update.message.reply_text("Неизвестная команда", reply_markup=admin_main_keyboard)
        return ADMIN_MAIN

async def admin_choose_add_type(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == 'Назад':
        return await admin_main_menu(update, context)
    if text not in ['Супер админ', 'Админ']:
        await update.message.reply_text("Пожалуйста, выберите корректный тип", reply_markup=add_admin_type_keyboard)
        return ADMIN_CHOOSE_ADD_TYPE
    context.user_data['add_admin_role'] = text.lower()
    await update.message.reply_text("Введите user_id пользователя, которого хотите назначить:", reply_markup=universal_admin_keyboard)
    return ADMIN_WAIT_FOR_USER_ID

async def admin_receive_user_id(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text.lower() in ['назад', 'главное меню']:
        return await admin_main_menu(update, context)
    try:
        user_id = int(text.strip())
    except ValueError:
        await update.message.reply_text("Неверный формат user_id. Введите число.", reply_markup=universal_admin_keyboard)
        return ADMIN_WAIT_FOR_USER_ID
    role = context.user_data.get('add_admin_role')
    caller = Database.get_admin(update.message.from_user.id)
    if role == 'супер админ' and caller[1] not in ['system']:
        await update.message.reply_text("Только системный админ может назначать супер админов.", reply_markup=admin_main_keyboard)
        return await admin_main_menu(update, context)
    Database.add_admin(user_id, 'super' if role=='супер админ' else 'admin')
    await update.message.reply_text(f"Пользователь {user_id} успешно добавлен на роль: {role.capitalize()}",
                                    reply_markup=universal_admin_keyboard)
    return ADMIN_MAIN

async def admin_list_choice(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == 'Назад':
        return await admin_main_menu(update, context)
    try:
        uid = int(text.split()[0])
    except Exception:
        await update.message.reply_text("Неверный формат, попробуйте еще раз", reply_markup=universal_admin_keyboard)
        return ADMIN_LIST_MENU
    context.user_data['target_admin_id'] = uid
    target = Database.get_admin(uid)
    if not target:
        await update.message.reply_text("Админ не найден", reply_markup=universal_admin_keyboard)
        return await admin_main_menu(update, context)
    reply_markup = admin_action_keyboard(target[1])
    await update.message.reply_text(f"Выбран админ: {uid} ({target[1]}). Выберите действие:", reply_markup=reply_markup)
    return ADMIN_CHOOSE_ACTION

async def admin_take_action(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == 'Назад':
        return await admin_main_menu(update, context)
    if text not in ['Повысить', 'Понизить', 'Удалить']:
        await update.message.reply_text("Неверный выбор, попробуйте снова", reply_markup=universal_admin_keyboard)
        return ADMIN_CHOOSE_ACTION
    context.user_data['admin_action'] = text
    target_admin_id = context.user_data.get('target_admin_id')
    await update.message.reply_text(f"Подтвердите действие: {text} для пользователя {target_admin_id} (напишите Да/Нет)",
                                    reply_markup=ReplyKeyboardMarkup([['Да', 'Нет']], one_time_keyboard=True, resize_keyboard=True))
    return ADMIN_CONFIRM_ACTION

async def admin_confirm_action(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text != 'Да':
        await update.message.reply_text("Действие отменено", reply_markup=universal_admin_keyboard)
        return await admin_main_menu(update, context)
    action = context.user_data.get('admin_action')
    target_admin_id = context.user_data.get('target_admin_id')
    target = Database.get_admin(target_admin_id)
    if not target:
        await update.message.reply_text("Админ не найден", reply_markup=universal_admin_keyboard)
        return await admin_main_menu(update, context)
    if action == 'Повысить':
        Database.update_admin_role(target_admin_id, 'super')
        await update.message.reply_text(f"Пользователь {target_admin_id} повышен до Супер админа", reply_markup=universal_admin_keyboard)
    elif action == 'Понизить':
        Database.update_admin_role(target_admin_id, 'admin')
        await update.message.reply_text(f"Пользователь {target_admin_id} понижен до Админа", reply_markup=universal_admin_keyboard)
    elif action == 'Удалить':
        Database.remove_admin(target_admin_id)
        await update.message.reply_text(f"Пользователь {target_admin_id} удален из списка администраторов", reply_markup=universal_admin_keyboard)
    return await admin_main_menu(update, context)

async def admin_sales_cards_menu(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == 'Создать карточку':
        # Запрашиваем выбор раздела для карточки
        section_keyboard = ReplyKeyboardMarkup(
            [['Отдел продаж', 'Запасные части', 'Покупка оборудования'], ['Назад']],
            resize_keyboard=True
        )
        await update.message.reply_text("Выберите раздел для создания карточки:", reply_markup=section_keyboard)
        return ADMIN_SELECT_CARD_SECTION
    elif text == 'Редактировать карточку':
        return await admin_edit_card_start(update, context)
    elif text == 'Удалить карточку':
        return await admin_delete_card_start(update, context)
    elif text == 'Назад':
        return await admin_main_menu(update, context)
    else:
        await update.message.reply_text("Выберите корректное действие.", reply_markup=ReplyKeyboardMarkup(
            [['Создать карточку', 'Редактировать карточку'], ['Удалить карточку', 'Назад']],
            resize_keyboard=True
        ))
        return ADMIN_SALES_CARDS_MENU

# Выбор раздела для создания карточки
async def admin_select_card_section(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == 'Назад':
        return await admin_sales_cards_menu(update, context)
    context.user_data['card_section'] = text
    # Переходим к приёму фотографий (до 15)
    context.user_data['sales_card_photos'] = []
    await update.message.reply_text("Отправьте фото для карточки (до 15). После загрузки фото нажмите 'Готово'.",
                                    reply_markup=ReplyKeyboardMarkup([['Готово', 'Отмена']], resize_keyboard=True))
    return ADMIN_CREATE_CARD_PHOTOS

async def admin_create_card_photos(update: Update, context: CallbackContext) -> int:
    if update.message.photo:
        photos = context.user_data.get('sales_card_photos', [])
        photos.append(update.message.photo[-1].file_id)
        if len(photos) >= 15:
            await update.message.reply_text("Достигнуто максимальное количество фотографий. Введите текстовую информацию (название и описание):")
            context.user_data['sales_card_photos'] = photos
            return ADMIN_CREATE_CARD_TITLE
        else:
            context.user_data['sales_card_photos'] = photos
            await update.message.reply_text(f"Фото получено ({len(photos)}). Можете прикрепить ещё фото или нажмите 'Готово'.",
                                            reply_markup=ReplyKeyboardMarkup([['Готово', 'Отмена']], resize_keyboard=True))
            return ADMIN_CREATE_CARD_PHOTOS
    else:
        return ADMIN_CREATE_CARD_PHOTOS
    
async def admin_create_card_photos_done(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == "Готово":
        photos = context.user_data.get('sales_card_photos', [])
        if not photos:
            await update.message.reply_text("Пожалуйста, прикрепите хотя бы одно фото.")
            return ADMIN_CREATE_CARD_PHOTOS
        await update.message.reply_text("Введите текстовую информацию для карточки.\nФормат: первая строка – название, затем пустая строка, далее описание и дополнительные данные.")
        return ADMIN_CREATE_CARD_TITLE
    elif text == "Отмена":
        await update.message.reply_text("Создание карточки отменено.", reply_markup=admin_main_keyboard)
        return ADMIN_MAIN
    else:
        await update.message.reply_text("Пожалуйста, отправьте фото или нажмите 'Готово'.")
        return ADMIN_CREATE_CARD_PHOTOS

# Приём текстовой информации для карточки, где первая строка – название
async def admin_create_card_title(update: Update, context: CallbackContext) -> int:
    full_text = update.message.text.strip()
    parts = full_text.splitlines()
    # Проверяем, что есть как минимум две строки и вторая строка пустая
    if len(parts) < 2 or parts[1].strip() != "":
        await update.message.reply_text("Ошибка форматирования. Первая строка должна быть названием, затем пустая строка, а после – описание и дополнительные данные.")
        return ADMIN_CREATE_CARD_TITLE
    title = parts[0].strip()
    description = "\n".join(parts[2:]).strip() if len(parts) > 2 else ""
    photos = context.user_data.get('sales_card_photos', [])
    section = context.user_data.get('card_section', "Отдел продаж")
    Database.add_sales_card(photos, title, description, section)
    await update.message.reply_text("Карточка создана успешно!", reply_markup=admin_main_keyboard)
    context.user_data.pop('sales_card_photos', None)
    context.user_data.pop('card_section', None)
    return ADMIN_MAIN

async def admin_edit_card_start(update: Update, context: CallbackContext) -> int:
    cards = Database.get_all_sales_cards()
    if not cards:
        await update.message.reply_text("Нет карточек для редактирования.", reply_markup=admin_main_keyboard)
        return ADMIN_MAIN
    buttons = [[f"{card[0]} - {card[2]}"] for card in cards]
    buttons.append(["Назад"])
    reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    await update.message.reply_text("Выберите карточку для редактирования:", reply_markup=reply_markup)
    return ADMIN_SELECT_CARD_EDIT

async def admin_select_card_edit(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == "Назад":
        return await admin_main_menu(update, context)
    try:
        card_id = int(text.split()[0])
    except Exception:
        await update.message.reply_text("Неверный формат. Попробуйте ещё раз.")
        return ADMIN_SELECT_CARD_EDIT
    await update.message.reply_text("Функция редактирования карточки пока не реализована.", reply_markup=admin_main_keyboard)
    return ADMIN_MAIN

async def admin_delete_card_start(update: Update, context: CallbackContext) -> int:
    cards = Database.get_all_sales_cards()
    if not cards:
        await update.message.reply_text("Нет карточек для удаления.", reply_markup=admin_main_keyboard)
        return ADMIN_MAIN
    buttons = [[f"{card[0]} - {card[2]}"] for card in cards]
    buttons.append(["Назад"])
    reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    await update.message.reply_text("Выберите карточку для удаления:", reply_markup=reply_markup)
    return ADMIN_SELECT_CARD_DELETE

async def admin_select_card_delete(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == "Назад":
        return await admin_main_menu(update, context)
    try:
        card_id = int(text.split()[0])
    except Exception:
        await update.message.reply_text("Неверный формат. Попробуйте ещё раз.")
        return ADMIN_SELECT_CARD_DELETE
    context.user_data['delete_card_id'] = card_id
    await update.message.reply_text(f"Подтвердите удаление карточки {card_id}: Напишите 'Да' для подтверждения или 'Нет' для отмены.",
                                    reply_markup=ReplyKeyboardMarkup([['Да', 'Нет']], resize_keyboard=True))
    return ADMIN_DELETE_CARD_CONFIRM

async def admin_delete_card_confirm(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == "Да":
        card_id = context.user_data.get('delete_card_id')
        Database.delete_sales_card(card_id)
        await update.message.reply_text(f"Карточка {card_id} удалена.", reply_markup=admin_main_keyboard)
    else:
        await update.message.reply_text("Удаление отменено.", reply_markup=admin_main_keyboard)
    return ADMIN_MAIN

def get_available_years(user_id: int) -> list:
    reqs = Database.get_user_requests(user_id)
    years = set()
    for req in reqs:
        try:
            dt = datetime.fromisoformat(req[5])
        except Exception:
            dt = datetime.strptime(req[5], "%Y-%m-%d %H:%M:%S.%f")
        years.add(dt.year)
    return sorted(list(years), reverse=True)

def get_available_months(user_id: int, year: int) -> list:
    reqs = Database.get_user_requests(user_id)
    months = set()
    for req in reqs:
        try:
            dt = datetime.fromisoformat(req[5])
        except Exception:
            dt = datetime.strptime(req[5], "%Y-%m-%d %H:%M:%S.%f")
        if dt.year == year:
            months.add(dt.month)
    return sorted(list(months))

def get_available_days(user_id: int, year: int, month: int) -> list:
    reqs = Database.get_user_requests(user_id)
    days = set()
    for req in reqs:
        try:
            dt = datetime.fromisoformat(req[5])
        except Exception:
            dt = datetime.strptime(req[5], "%Y-%m-%d %H:%M:%S.%f")
        if dt.year == year and dt.month == month:
            days.add(dt.day)
    return sorted(list(days))

def get_requests_by_date(user_id: int, year: int, month: int, day: int) -> list:
    reqs = Database.get_user_requests(user_id)
    filtered = []
    for req in reqs:
        try:
            dt = datetime.fromisoformat(req[5])
        except Exception:
            dt = datetime.strptime(req[5], "%Y-%m-%d %H:%M:%S.%f")
        if dt.year == year and dt.month == month and dt.day == day:
            filtered.append(req)
    return filtered

# Словарь для отображения названий месяцев на русском
MONTH_NAMES = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь",
    7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}

# ----------------------------------------------------------------
# Функции для показа заявок и истории с кнопкой для сортировки

# Функция вывода всех заявок пользователя (в "Мои заявки" выводятся все)
async def show_requests(update: Update, context: CallbackContext) -> None:
    requests_list = Database.get_user_requests(update.message.from_user.id)
    if not requests_list:
        await update.message.reply_text("У вас нет активных заявок")
        return
    response = "📋 Ваши заявки:\n\n"
    for req in requests_list:
        response += f"🔹 #{req[0]} {req[2]}\nСтатус: {req[6]}\nДата: {req[5]}\n\n"
    inline_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("Сортировать по дате", callback_data="filter_requests")]
    ])
    await update.message.reply_text(response, reply_markup=inline_markup)

# Функция вывода истории обслуживания – фильтруем и показываем только заявки на обслуживание.
async def show_history(update: Update, context: CallbackContext) -> None:
    # Получаем все заявки пользователя
    reqs = Database.get_user_requests(update.message.from_user.id)
    # Фильтруем заявки: оставляем только те, у которых request_category == "Заявки на обслуживание"
    reqs = [req for req in reqs if req[9] == "Заявки на обслуживание"]
    if not reqs:
        await update.message.reply_text("История обслуживания пуста")
        return
    history = {}
    # Группировка заявок по году, месяцу и дню
    for req in reqs:
        try:
            dt = datetime.strptime(req[5], '%Y-%m-%d %H:%M:%S.%f')
        except Exception:
            dt = datetime.fromisoformat(req[5])
        year = dt.year
        month = dt.strftime("%B")
        day = dt.day
        history.setdefault(year, {}).setdefault(month, {}).setdefault(day, []).append(req)
    text = "🗓 История обслуживания:\n"
    for year in sorted(history.keys(), reverse=True):
        text += f"\n{year}:\n"
        for month in sorted(history[year].keys(), reverse=True):
            text += f"  {month}:\n"
            for day in sorted(history[year][month].keys(), reverse=True):
                text += f"    {day}:\n"
                for req in history[year][month][day]:
                    text += f"      Заявка #{req[0]}: {req[2]} - {req[6]}\n"
    inline_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("Сортировать по дате", callback_data="filter_requests")]
    ])
    await update.message.reply_text(text, reply_markup=inline_markup)

# ----------------------------------------------------------------
# Обработчик inline-кнопки "Сортировать по дате"
async def filter_requests_callback(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    return await start_requests_filter(update, context)

# ----------------------------------------------------------------
# Функции для фильтрации по дате (ConversationHandler)

async def start_requests_filter(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id if update.message else update.callback_query.from_user.id
    years = get_available_years(user_id)
    if not years:
        if update.message:
            await update.message.reply_text("У вас нет заявок.")
        else:
            await update.callback_query.edit_message_text("У вас нет заявок.")
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(str(year), callback_data=f"filter_year:{year}")] for year in years]
    keyboard.append([InlineKeyboardButton("Отмена", callback_data="filter_cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text("Выберите год:", reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text("Выберите год:", reply_markup=reply_markup)
    return FILTER_YEAR

async def filter_year_handler(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    try:
        _, year_str = query.data.split(":")
        year = int(year_str)
    except Exception:
        await query.edit_message_text("Ошибка при выборе года.")
        return ConversationHandler.END
    context.user_data['filter_year'] = year
    user_id = query.from_user.id
    months = get_available_months(user_id, year)
    if not months:
        await query.edit_message_text("Заявки за выбранный год отсутствуют.")
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(MONTH_NAMES.get(m, str(m)), callback_data=f"filter_month:{year}:{m}")]
                for m in months]
    keyboard.append([InlineKeyboardButton("Назад", callback_data="filter_back_year")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"Выберите месяц за {year}:", reply_markup=reply_markup)
    return FILTER_MONTH

async def filter_month_handler(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    try:
        _, year_str, month_str = query.data.split(":")
        year = int(year_str)
        month = int(month_str)
    except Exception:
        await query.edit_message_text("Ошибка при выборе месяца.")
        return ConversationHandler.END
    context.user_data['filter_month'] = month
    user_id = query.from_user.id
    days = get_available_days(user_id, year, month)
    if not days:
        await query.edit_message_text("Заявки за выбранный месяц отсутствуют.")
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(str(d), callback_data=f"filter_day:{year}:{month}:{d}")]
                for d in days]
    keyboard.append([InlineKeyboardButton("Назад", callback_data="filter_back_month")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"Выберите день за {MONTH_NAMES.get(month, month)} {year}:", reply_markup=reply_markup)
    return FILTER_DAY

async def filter_day_handler(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    try:
        _, year_str, month_str, day_str = query.data.split(":")
        year = int(year_str)
        month = int(month_str)
        day = int(day_str)
    except Exception:
        await query.edit_message_text("Ошибка при выборе дня.")
        return ConversationHandler.END
    requests_on_day = get_requests_by_date(query.from_user.id, year, month, day)
    if not requests_on_day:
        await query.edit_message_text("Нет заявок за выбранный день.")
        return ConversationHandler.END
    text = f"Заявки за {day} {MONTH_NAMES.get(month, month)} {year}:\n\n"
    for req in requests_on_day:
        text += f"🔹 #{req[0]} – {req[2]} (Статус: {req[6]})\n"
    keyboard = [[InlineKeyboardButton("Назад", callback_data=f"filter_back_day:{year}:{month}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)
    return ConversationHandler.END

async def filter_back_year_handler(update: Update, context: CallbackContext) -> int:
    return await start_requests_filter(update, context)

async def filter_back_month_handler(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    year = context.user_data.get('filter_year')
    if not year:
        return await start_requests_filter(update, context)
    user_id = query.from_user.id
    months = get_available_months(user_id, year)
    keyboard = [[InlineKeyboardButton(MONTH_NAMES.get(m, str(m)), callback_data=f"filter_month:{year}:{m}")]
                for m in months]
    keyboard.append([InlineKeyboardButton("Назад", callback_data="filter_back_year")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"Выберите месяц за {year}:", reply_markup=reply_markup)
    return FILTER_MONTH

async def filter_back_day_handler(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    try:
        _, year_str, month_str = query.data.split(":")
        year = int(year_str)
        month = int(month_str)
    except Exception:
        return await filter_year_handler(update, context)
    days = get_available_days(query.from_user.id, year, month)
    keyboard = [[InlineKeyboardButton(str(d), callback_data=f"filter_day:{year}:{month}:{d}")]
                for d in days]
    keyboard.append([InlineKeyboardButton("Назад", callback_data="filter_back_month")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"Выберите день за {MONTH_NAMES.get(month, month)} {year}:", reply_markup=reply_markup)
    return FILTER_DAY

async def filter_cancel_handler(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer("Операция отменена.")
    await query.edit_message_text("Операция отменена.")
    return ConversationHandler.END

async def notify_admin_new_request(context: CallbackContext, request_id: int):
    req = Database.get_request_by_id(request_id)
    user = Database.get_user(req[1])
    # Парсим дату
    try:
        dt = datetime.fromisoformat(req[5])
    except Exception:
        dt = datetime.strptime(req[5], '%Y-%m-%d %H:%M:%S.%f')
    date_str = dt.strftime("%d.%m.%Y %H:%M")
    # Номер в категории
    custom_number = Database.get_ticket_rank(req[9], request_id)
    text = (
        "📢 *Новая заявка!*\n\n"
        f"Заявка #{custom_number}\n\n"
        f"Тип: {req[2]}\n"
        f"Описание: {req[3]}\n"
        f"Статус: {req[6]}\n"
        f"Дата: {date_str}\n\n"
        "*Информация о пользователе:*\n"
        f"ID: {user[0]}\n"
        f"Имя: {user[1]}\n"
        f"Телефон: {user[2]}\n"
        f"Адреса: {user[3]}"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("Назначить бригаду", callback_data=f"assign_brigade_{request_id}")
    ]])
    await context.bot.send_message(
        chat_id=SYSTEM_ADMIN_ID,
        text=text,
        parse_mode="Markdown",
        reply_markup=kb
    )


async def assign_brigade_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    request_id = int(query.data.split("_")[-1])
    brigades = Database.get_all_brigades()
    buttons = [
        [InlineKeyboardButton(b[1], callback_data=f"brigade_select_{request_id}_{b[0]}")]
        for b in brigades
    ]
    buttons.append([InlineKeyboardButton("Отмена", callback_data="brigade_cancel")])
    await query.message.edit_text(
        "Выберите бригаду для заявки:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return BRIGADE_ASSIGN_SELECT

async def brigade_select_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    _, _, req_id, brigade_id = query.data.split("_")
    req_id, brigade_id = int(req_id), int(brigade_id)
    assign_request_to_brigade(req_id, brigade_id)
    await query.message.edit_text("✅ Заявка закреплена за бригадой")
    await send_to_brigade_employees(context, req_id, brigade_id)
    return ADMIN_MAIN

async def send_to_brigade_employees(context: CallbackContext, request_id: int, brigade_id: int):
    b = get_brigade_by_id(brigade_id)
    req = Database.get_request_by_id(request_id)
    
    # Проверка файлов пользователя
    user_files = req[4].split(',') if req[4] else []
    # Проверка файлов админа из последнего комментария
    admin_files = Database.get_last_comment_files_for_request(request_id)

    # Формирование текста
    text = (
        f"🆕 *Новая заявка #{Database.get_ticket_rank(req[9], req[0])}* для вашей бригады\n\n"
        f"Тип: {req[2]}\n"
        f"Описание: {req[3]}\n"
        f"Статус: {req[6]}\n"
        f"Дата: {req[5]}\n\n"
        "*Информация о пользователе:*\n"
        f"ID: {req[1]}\n"
        f"Имя: {Database.get_user(req[1])[1]}\n"
        f"Телефон: {Database.get_user(req[1])[2]}\n"
        f"Адреса: {Database.get_user(req[1])[3]}"
    )

    # Создание кнопок
    buttons = []
    if user_files:
        buttons.append([InlineKeyboardButton("📎 Файлы клиента", callback_data=f"user_files_{request_id}")])
    if admin_files:
        buttons.append([InlineKeyboardButton("📁 Файлы админа", callback_data=f"admin_files_{request_id}")])
    buttons.append([InlineKeyboardButton("📤 Внести отчет", callback_data=f"emp_report_{request_id}")])
    
    kb = InlineKeyboardMarkup(buttons)

    # Отправка сотрудникам
    emp_ids = [int(x) for x in (b[2] or "").split(',') if x]
    for emp in emp_ids:
        await context.bot.send_message(
            chat_id=emp,
            text=text,
            parse_mode="Markdown",
            reply_markup=kb
        )


async def handle_add_employee_name(update: Update, context: CallbackContext) -> int:
    emp_id = context.user_data.get('new_emp_id')  # ← лучше через .get() чтобы не падал
    if not emp_id:
        await update.message.reply_text("Ошибка: ID сотрудника не найден. Начните заново.", reply_markup=universal_admin_keyboard)
        return EMPLOYEE_MENU
    name = update.message.text.strip()
    Database.add_employee(emp_id, name)
    await update.message.reply_text(f"Сотрудник {name} добавлен!", reply_markup=employee_menu_keyboard)
    return EMPLOYEE_MENU


# --- Панель сотрудника и просмотр заявок по статусам ---
async def show_employee_panel(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Открытые",    callback_data="emp_status_Новая")],
        [InlineKeyboardButton("В процессе",  callback_data="emp_status_В работе")],
        [InlineKeyboardButton("Выполненные", callback_data="emp_status_Завершена")],
        [InlineKeyboardButton("Назад",        callback_data="emp_panel_back")]
    ])
    await query.message.edit_text(
        "👷 *Панель бригады.* Выберите статус заявок:",
        parse_mode="Markdown",
        reply_markup=kb
    )
    return EMPLOYEE_VIEW_BY_STATUS

async def employee_view_by_status(update, context):
    text = update.message.text.strip()
    if text == "Назад":
        return await employee_panel_handler(update, context)

    if not text.startswith("Заявка #"):
        await update.message.reply_text("Выберите заявку из списка.")
        return EMPLOYEE_VIEW_BY_STATUS

    try:
        number = int(text.replace("Заявка #", ""))
    except:
        await update.message.reply_text("Неверный номер.")
        return EMPLOYEE_VIEW_BY_STATUS

    requests = context.user_data.get("employee_filtered_requests", [])
    total = len(requests)
    if number < 1 or number > total:
        await update.message.reply_text("Заявка не найдена.")
        return EMPLOYEE_VIEW_BY_STATUS

    req = requests[total - number]
    context.user_data["current_request"] = req

    return await employee_request_actions(update, context)

async def employee_request_actions(update, context):
    req = context.user_data["current_request"]
    user = Database.get_user(req[1])
    custom_number = Database.get_ticket_rank(req[9], req[0])
    date_str = req[5]

    text = (
        f"📌 Заявка #{custom_number}\n\n"
        f"🔧 Тип: {req[2]}\n"
        f"📝 Описание: {req[3]}\n"
        f"🔄 Статус: {req[6]}\n"
        f"📅 Дата: {date_str}\n\n"
        f"👤 Клиент: {user[1]}\n"
        f"📞 Телефон: {user[2]}\n"
        f"🏠 Адреса: {user[3]}"
    )

    kb = ReplyKeyboardMarkup([
        ['Изменить статус', 'Внести отчет'],
        ['Файлы', 'Файлы админа'],
        ['Назад']
    ], resize_keyboard=True)

    await update.message.reply_text(text, reply_markup=kb)
    return EMPLOYEE_VIEW_REQUEST

async def employee_request_action_handler(update, context):
    text = update.message.text.strip()
    req = context.user_data.get("current_request")

    if text == "🔙 Назад":
        return await employee_panel_handler(update, context)

    if text == "📝 Изменить статус":
        kb = ReplyKeyboardMarkup([
            ['Новая', 'В работе', 'Завершена'],
            ['Отмена']
        ], resize_keyboard=True)
        await update.message.reply_text("Выберите новый статус заявки:", reply_markup=kb)
        return EMPLOYEE_SET_STATUS

    if text == "📤 Внести отчет":
        request_id = context.user_data.get('current_request', [None])[0]
        if not request_id:
            await update.message.reply_text("Ошибка: заявка не определена.")
            return EMPLOYEE_VIEW_REQUEST
        context.user_data["report_request_id"] = request_id
        await update.message.reply_text("✍️ Введите текст отчета:", reply_markup=ReplyKeyboardRemove())
        return EMPLOYEE_REPORT_TEXT

    if text == "📎 Файлы":
        if not req[4]:
            await update.message.reply_text("Нет файлов клиента.")
        else:
            await context.bot.send_media_group(chat_id=update.message.chat_id, media=[
                InputMediaPhoto(f) for f in req[4].split(",")
            ])
        return EMPLOYEE_VIEW_REQUEST

    if text == "📁 Файлы админа":
        files = Database.get_last_comment_files_for_request(req[0])
        if not files:
            await update.message.reply_text("Нет файлов от админа.")
        else:
            await context.bot.send_media_group(chat_id=update.message.chat_id, media=[
                InputMediaPhoto(f) for f in files
            ])
        return EMPLOYEE_VIEW_REQUEST

    await update.message.reply_text("Выберите действие из меню.")
    return EMPLOYEE_VIEW_REQUEST

async def employee_set_status_manual(update: Update, context: CallbackContext) -> int:
    status = update.message.text.strip()
    if status == "Отмена":
        return await employee_view_request(update, context)

    req = context.user_data["current_request"]
    # обновляем статус в БД
    Database.update_request_status(req[0], status)

    # уведомляем клиента
    user = Database.get_user(req[1])
    custom_number = Database.get_ticket_rank(req[9], req[0])
    await context.bot.send_message(
        chat_id=user[0],
        text=f"✅ Статус вашей заявки #{custom_number} изменён на: {status}"
    )

    # готовим новый текст для группы
    created_at = datetime.fromisoformat(req[5]) if isinstance(req[5], str) else req[5]
    date_str = created_at.strftime("%d.%m.%Y %H:%M")
    new_text = (
        f"📌 Заявка #{custom_number}\n\n"
        f"🔧 Тип: {req[2]}\n"
        f"📝 Описание: {req[3]}\n"
        f"🔄 Статус: {status}\n"
        f"📅 Дата: {date_str}\n\n"
        f"👤 Клиент: {user[1]}\n"
        f"📞 Телефон: {user[2]}\n"
        f"🏠 Адреса: {user[3]}"
    )

    # пытаемся отредактировать старое сообщение, иначе шлём новое
    group_msg_id = req[7]
    try:
        await context.bot.edit_message_text(
            chat_id=GROUP_CHAT_ID,
            message_id=group_msg_id,
            text=new_text
        )
    except:
        sent = await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=new_text)
        Database.update_request_group_message_id(req[0], sent.message_id)

    await update.message.reply_text(f"✅ Статус заявки #{custom_number} обновлён на: {status}", reply_markup=ReplyKeyboardMarkup([['Заявки'], ['Назад']], resize_keyboard=True))
    return EMPLOYEE_PANEL


async def employee_control_request_handler(update: Update, context: CallbackContext) -> int:
    text = update.message.text.strip()
    req = context.user_data.get('current_request')
    if not req:
        await update.message.reply_text("Заявка не найдена.", reply_markup=ReplyKeyboardMarkup([['Заявки'], ['Назад']], resize_keyboard=True))
        return EMPLOYEE_PANEL

    # Назад в панель
    if text == 'Назад':
        panel_kb = ReplyKeyboardMarkup([['Заявки'], ['Назад']], resize_keyboard=True)
        await update.message.reply_text("👷 Панель сотрудника", reply_markup=panel_kb)
        return EMPLOYEE_PANEL

    # Изменить статус
    if text == 'Изменить статус':
        status_kb = ReplyKeyboardMarkup([['Новая', 'В работе', 'Завершена'], ['Назад']], resize_keyboard=True)
        await update.message.reply_text("Выберите новый статус заявки:", reply_markup=status_kb)
        return EMPLOYEE_VIEW_REQUEST

    # Выбор нового статуса
    if text in ['Новая', 'В работе', 'Завершена']:
        Database.update_request_status(req[0], text)
        await update.message.reply_text(f"✅ Статус заявки обновлён на: {text}", reply_markup=ReplyKeyboardMarkup([['Изменить статус','Внести отчет'], ['Файлы','Файлы админа'], ['Назад']], resize_keyboard=True))
        return EMPLOYEE_VIEW_REQUEST

    # Показать файлы клиента
    if text in ['Файлы', '📎 Файлы']:
        media_ids = req[4].split(',') if req[4] else []
        if not media_ids:
            await update.message.reply_text("Файлы отсутствуют.")
        else:
            await context.bot.send_media_group(chat_id=update.message.chat_id,
                                              media=[InputMediaPhoto(m) for m in media_ids])
        return EMPLOYEE_VIEW_REQUEST

    # Показать файлы админа
    if text in ['Файлы админа', '📁 Файлы админа']:
        admin_ids = Database.get_last_comment_files_for_request(req[0])
        if not admin_ids:
            await update.message.reply_text("Файлы от админа отсутствуют.")
        else:
            await context.bot.send_media_group(chat_id=update.message.chat_id,
                                              media=[InputMediaPhoto(m) for m in admin_ids])
        return EMPLOYEE_VIEW_REQUEST

    # Внести отчёт (любая из этих форм)
    if text in ['Внести отчет', '📤 Внести отчет', '📄 Внести отчет']:
        # сохраним ID заявки
        context.user_data["report_request_id"] = req[0]
        await update.message.reply_text("✍️ Введите текст отчёта:", reply_markup=ReplyKeyboardRemove())
        return EMPLOYEE_REPORT_TEXT

    # По умолчанию
    await update.message.reply_text("Пожалуйста, выберите действие из меню.")
    return EMPLOYEE_VIEW_REQUEST



async def employee_view_request(update, context):
    req = context.user_data["current_request"]
    user = Database.get_user(req[1])
    custom_number = Database.get_ticket_rank(req[9], req[0])
    created_at = datetime.fromisoformat(req[5]) if isinstance(req[5], str) else req[5]
    date_str = created_at.strftime("%d.%m.%Y %H:%M")

    text = (
        f"📌 Заявка #{custom_number}\n\n"
        f"🔧 Тип: {req[2]}\n"
        f"📝 Описание: {req[3]}\n"
        f"🔄 Статус: {req[6]}\n"
        f"📅 Дата: {date_str}\n\n"
        f"👤 Клиент: {user[1]}\n"
        f"📞 Телефон: {user[2]}\n"
        f"🏠 Адреса: {user[3]}\n\n"
        "⬇️ Доступные действия:"
    )

    buttons = [
        ['📤 Внести отчет', '📝 Изменить статус'],
    ]
    if req[4]:
        buttons.append(['📎 Файлы'])
    if Database.get_last_comment_files_for_request(req[0]):
        buttons.append(['📁 Файлы админа'])
    buttons.append(['🔙 Назад'])

    await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
    return EMPLOYEE_VIEW_REQUEST

async def employee_select_status(update: Update, context: CallbackContext) -> int:
    text = update.message.text.strip()
    if text == 'Назад':
        return await employee_panel_handler(update, context)

    context.user_data['selected_status'] = text
    all_requests = get_requests_for_employee(update.message.from_user.id)
    requests = [r for r in all_requests if r[6] == text]

    if not requests:
        await update.message.reply_text("Заявки с таким статусом не найдены.", reply_markup=ReplyKeyboardMarkup([['Назад']], resize_keyboard=True))
        return EMPLOYEE_PANEL

    keyboard = []
    total = len(requests)
    for i, req in enumerate(requests):
        keyboard.append([f"Заявка #{total - i}"])
    keyboard.append(['Назад'])

    context.user_data['employee_filtered_requests'] = requests

    await update.message.reply_text("Выберите заявку:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return EMPLOYEE_VIEW_BY_STATUS

async def employee_set_status(update, context):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    request_id, new_status = int(parts[-2]), parts[-1]

    Database.update_request_status(request_id, new_status)
    req = Database.get_request_by_id(request_id)
    user = Database.get_user(req[1])

    custom_number = Database.get_ticket_rank(req[9], req[0])
    created_at = datetime.fromisoformat(req[5]) if isinstance(req[5], str) else req[5]
    date_str = created_at.strftime("%d.%m.%Y %H:%M")

    # Уведомляем пользователя
    await context.bot.send_message(
        chat_id=user[0],
        text=f"✅ Статус вашей заявки #{custom_number} изменён на: {new_status}"
    )

    # Обновляем в группе
    group_msg_id = req[7]
    text = (
        f"📌 Заявка #{custom_number}\n\n"
        f"🔧 Тип: {req[2]}\n"
        f"📝 Описание: {req[3]}\n"
        f"🔄 Статус: {new_status}\n"
        f"📅 Дата: {date_str}\n\n"
        f"👤 Клиент: {user[1]}\n"
        f"📞 Телефон: {user[2]}\n"
        f"🏠 Адреса: {user[3]}\n\n"
    )
    try:
        await context.bot.edit_message_text(
            chat_id=GROUP_CHAT_ID,
            message_id=group_msg_id,
            text=text
        )
    except:
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=text)

    await employee_view_request(update, context)

# Добавьте этот обработчик
async def back_to_request_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    request_id = int(query.data.split("_")[-1])
    
    req = Database.get_request_by_id(request_id)
    user = Database.get_user(req[1])
    last_comment = Database.get_last_comment_for_request(request_id)
    created_at = datetime.fromisoformat(req[5]) if isinstance(req[5], str) else req[5]
    
    text = (
        f"📌 Заявка #{Database.get_ticket_rank(req[9], req[0])}\n\n"
        f"🔧 Тип: {req[2]}\n"
        f"📝 Описание: {req[3]}\n"
        f"🔄 Статус: {req[6]}\n"
        f"📅 Дата: {created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"👤 Информация о клиенте:\n"
        f"ID: {user[0]}\n"
        f"Имя: {user[1]}\n"
        f"📞 Телефон: {user[2]}\n"
        f"🏠 Адреса: {', '.join(user[3].split(','))}\n\n"
    )
    
    if last_comment:
        text += f"💬 Последний комментарий админа:\n{last_comment}\n\n"
    
    user_files = req[4].split(',') if req[4] else []
    admin_files = Database.get_last_comment_files_for_request(request_id)
    
    buttons = []
    if user_files:
        buttons.append([InlineKeyboardButton("📎 Файлы клиента", callback_data=f"user_files_{request_id}")])
    if admin_files:
        buttons.append([InlineKeyboardButton("📁 Файлы админа", callback_data=f"admin_files_{request_id}")])
    buttons.append([InlineKeyboardButton("📤 Внести отчет", callback_data=f"emp_report_{request_id}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="emp_panel_back")])
    
    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def show_files_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    data = query.data.split("_")
    request_id = int(data[-1])
    
    # Определяем тип файлов
    file_type = data[0]  # 'user' или 'admin'
    
    # Получаем файлы
    if file_type == 'user':
        files = Database.get_request_by_id(request_id)[4].split(',')
    else:
        files = Database.get_last_comment_files_for_request(request_id)
    
    if not files:
        await query.answer("📭 Файлов не найдено")
        return
    
    # Создаем медиа-группу с определением типа
    media_group = []
    for file_id in files:
        # Определяем тип файла по расширению (упрощенно)
        if file_id.startswith('AgAC'):  # Если это фото (префикс file_id фото)
            media_group.append(InputMediaPhoto(media=file_id))
        else:
            media_group.append(InputMediaDocument(media=file_id))
    
    try:
        # Отправляем медиа-группу
        await context.bot.send_media_group(
            chat_id=query.message.chat_id,
            media=media_group
        )
    except Exception :
        logger.error(f"Ошибка отправки файлов: {e}")
        await query.answer("⚠️ Ошибка при отправке файлов")

    # Добавляем кнопку "Назад"
    back_button = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад", callback_data=f"back_to_request_{request_id}")]
    ])
    await query.message.reply_text("Файлы выше ↑", reply_markup=back_button)


async def start_employee_report(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    request_id = int(query.data.split("_")[-1])
    context.user_data["report_request_id"] = request_id

    await query.message.reply_text("✍️ Введите текст отчета:", reply_markup=ReplyKeyboardRemove())
    return EMPLOYEE_REPORT_TEXT

async def employee_report_text(update: Update, context: CallbackContext) -> int:
    """Первый шаг: попросить прикрепить файлы и нажать Готово."""
    await update.message.reply_text(
        "📎 Прикрепите файлы (фото/видео/документы), затем нажмите 'Готово'",
        reply_markup=ReplyKeyboardMarkup([['Готово']], resize_keyboard=True)
    )
    return EMPLOYEE_REPORT_FILES

def format_report_text(report_number, request, user, brigade_name, report_text, request_id):
    req = Database.get_request_by_id(request_id)
    addresses = user[4] if user[4] else "—"

    return f"""<b>Отчет по заявке #{Database.get_ticket_rank(req[9], req[0])}</b>

<blockquote>
📌 Заявка #{Database.get_ticket_rank(req[9], req[0])}

🔧 Тип: {html.escape(request[2])}
📝 Описание: {html.escape(request[4])}
🔄 Статус: {html.escape(request[6])}
📅 Дата: {request[7]}

👤 Клиент: {html.escape(user[1])}
📞 Телефон: {html.escape(user[2])}
🏠 Адреса: {html.escape(addresses)}
</blockquote>

<b>Бригада:</b> {html.escape(brigade_name)}
<b>Отчет #{report_number}:</b>
"{html.escape(report_text)}"
"""

async def employee_report_files(update: Update, context: CallbackContext) -> int:
    """Обрабатываем либо медиа, либо нажатие 'Готово'."""
    text = update.message.text.strip()
    request_id = context.user_data.get("report_request_id")
    if not request_id:
        await update.message.reply_text("Ошибка: заявка не определена.", reply_markup=ReplyKeyboardMarkup([['Заявки'], ['Назад']], resize_keyboard=True))
        return EMPLOYEE_PANEL

    # прикрепление файлов
    if update.message.photo or update.message.document or update.message.video:
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
        elif update.message.video:
            file_id = update.message.video.file_id
        else:
            file_id = update.message.document.file_id
        context.user_data.setdefault("report_files", []).append(file_id)
        await update.message.reply_text(f"Файл получен ({len(context.user_data['report_files'])}). Когда закончите — нажмите 'Готово'")
        return EMPLOYEE_REPORT_FILES

    # нажатие кнопки Готово
    if text == 'Готово':
        files = context.user_data.get("report_files", [])
        # спрашиваем, кому отправлять отчёт
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("В группу",       callback_data="report_to_group"),
                InlineKeyboardButton("Админам",        callback_data="report_to_admin"),
            ],
            [
                InlineKeyboardButton("Пользователю",   callback_data="report_to_user"),
                InlineKeyboardButton("Всех сразу",     callback_data="report_to_all"),
            ]
        ])
        await update.message.reply_text(
            "Куда отправить отчёт?",
            reply_markup=kb
        )
        return REPORT_RECIPIENTS

    # если текст не «Готово» — возвращаемся к прикреплению
    await update.message.reply_text("Прикрепите файлы или нажмите 'Готово'", reply_markup=ReplyKeyboardMarkup([['Готово']], resize_keyboard=True))
    return EMPLOYEE_REPORT_FILES

async def view_reports_list(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    request = context.user_data.get("current_request")
    request_id = request[0]
    reports = get_reports_by_request(request_id)

    if not reports:
        await query.message.reply_text("По этой заявке отчётов пока нет.")
        return

    buttons = [
        [InlineKeyboardButton(f"Отчет #{r[3]}", callback_data=f"report_details_{r[0]}")]
        for r in reports
    ]
    markup = InlineKeyboardMarkup(buttons)
    await query.message.reply_text(f"Отчёты по заявке #{request_id}:", reply_markup=markup)

async def report_details_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    report_id = int(query.data.split("_")[-1])
    report = get_report_by_id(report_id)
    request = get_request_by_id(report["request_id"])
    user = get_user_by_request(report["request_id"])
    comment = get_last_admin_comment(report["request_id"])
    brigade = get_brigade_name_by_user(report["user_id"])

    text = format_report_text(request, user, comment, brigade, report["report_number"])
    await query.message.reply_text(text, parse_mode=ParseMode.HTML)

async def handle_report_recipients(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    request_id = context.user_data.get("report_request_id")
    report_text = context.user_data.get("report_text")
    media_ids = context.user_data.get("report_files", [])

    if not request_id or not report_text:
        await query.message.reply_text("Ошибка при подготовке отчета.")
        return ConversationHandler.END

    # Получение всех данных
    request = get_request_by_id(request_id)
    user = get_user_by_request(request_id)
    comment = get_last_admin_comment(request_id)
    brigade = get_brigade_name_by_user(user_id)
    report_number = get_report_count_for_request(request_id) + 1

    # Формат текста отчета (!!! ПЕРЕДАЕМ report_text)
    text = format_report_text(report_number, request, user, brigade, report_text, request_id)


    # Сохраняем отчет
    save_report(request_id, user_id, report_number, report_text, ",".join(media_ids))

    # Подготовка медиа
    media = []
    for file_id in media_ids:
        if file_id.startswith("BQAC") or file_id.endswith(".doc"):
            media.append(InputMediaDocument(media=file_id))
        else:
            media.append(InputMediaPhoto(media=file_id))

    # Определяем получателей
    send_to_admin = query.data in ["report_to_admin", "report_to_all"]
    send_to_user = query.data in ["report_to_user", "report_to_all"]

    # Всегда отправляем в группу
    if media:
        await context.bot.send_media_group(chat_id=GROUP_CHAT_ID, media=media)
    await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=text, parse_mode=ParseMode.HTML)

    # Отправка админу (если нужно)
    if send_to_admin:
        for admin in Database.get_all_admins():
            try:
                if media:
                    await context.bot.send_media_group(chat_id=admin[0], media=media)
                await context.bot.send_message(chat_id=admin[0], text=text, parse_mode=ParseMode.HTML)
            except Exception as e:
                print(f"Ошибка при отправке админу {admin[0]}: {e}")

    # Отправка пользователю (если нужно)
    if send_to_user and user:
        try:
            if media:
                await context.bot.send_media_group(chat_id=user[0], media=media)
            await context.bot.send_message(chat_id=user[0], text=text, parse_mode=ParseMode.HTML)
        except Exception as e:
            print(f"Ошибка при отправке клиенту {user[0]}: {e}")

    await query.message.reply_text("Отчет успешно отправлен ✅")
    return ConversationHandler.END

async def send_to_admins(context, text, files):
    admins = Database.get_all_admins()
    for admin in admins:
        await send_message_with_files(context, admin[0], text, files)

async def send_to_client(context, request_id, text, files):
    req = Database.get_request_by_id(request_id)
    await send_message_with_files(context, req[1], text, files)

async def send_message_with_files(context, chat_id, text, files):
    try:
        await context.bot.send_message(chat_id, text)
        if files:
            media = []
            for file_id in files:
                if file_id.startswith('AgAC'):  # Проверка на фото
                    media.append(InputMediaPhoto(file_id))
                else:
                    media.append(InputMediaDocument(file_id))
            await context.bot.send_media_group(chat_id, media)
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")

async def admin_start_comment(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("📝 Введите текст комментария администратора:")
    return ADMIN_COMMENT_TEXT

async def admin_files_back(update: Update, context: CallbackContext) -> int:
    chat_id = update.message.chat_id
    # удаляем все медиа и сообщение с кнопкой
    for mid in context.user_data.get('admin_files_msg_ids', []):
        await context.bot.delete_message(chat_id=chat_id, message_id=mid)
    await context.bot.delete_message(chat_id=chat_id, message_id=context.user_data.get('admin_files_back_msg_id'))
    # очищаем
    context.user_data.pop('admin_files_msg_ids', None)
    context.user_data.pop('admin_files_back_msg_id', None)
    # возвращаем панель управления текущей заявкой
    return await admin_requests_list_handler(update, context)

async def admin_comment_text(update: Update, context: CallbackContext) -> int:
    context.user_data['admin_comment_text'] = update.message.text
    context.user_data['admin_comment_files'] = []
    buttons = [['Пропустить']] if not context.user_data['admin_comment_files'] else [['Готово']]
    buttons.append(['Назад'])
    await update.message.reply_text(
        "📎 Прикрепите файлы или нажмите кнопку:",
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )
    return ADMIN_COMMENT_FILES

# 1. Исправление ошибки с бригадой в админ-панели
async def admin_comment_files(update: Update, context: CallbackContext) -> int:
    if update.message.text == 'Пропустить':
        req = context.user_data.get('current_request')
        text = context.user_data.get('admin_comment_text', '')
        files = context.user_data.get('admin_comment_files', [])
        
        # Сохранение комментария
        Database.add_comment(req[0], text, ",".join(files) if files else "")
        
        # Уведомление бригады
        brigade = get_brigade_by_id(req[8])
        if brigade:
            for emp_id in brigade[2].split(','):
                try:
                    # Отправка текста
                    await context.bot.send_message(
                        chat_id=int(emp_id),
                        text=f"📌 Новый комментарий к заявке #{Database.get_ticket_rank(req[9], req[0])}:\n{text}"
                    )
                    # Отправка файлов если есть
                    if files:
                        media = [InputMediaPhoto(fid) if fid.startswith('AgAC') else InputMediaDocument(fid) for fid in files]
                        await context.bot.send_media_group(int(emp_id), media)
                except Exception as e:
                    logger.error(f"Ошибка отправки сотруднику {emp_id}: {e}")

        await update.message.reply_text("✅ Комментарий добавлен!", reply_markup=admin_main_keyboard)
        return ADMIN_MAIN

    # Обработка файлов
    file_id = None
    if update.message.document:
        file_id = update.message.document.file_id
    elif update.message.photo:
        file_id = update.message.photo[-1].file_id
    
    if file_id:
        context.user_data.setdefault('admin_comment_files', []).append(file_id)
        await update.message.reply_text(f"📎 Файлов прикреплено: {len(context.user_data['admin_comment_files'])}")
    
    return ADMIN_COMMENT_FILES


async def employee_panel_handler(update: Update, context: CallbackContext) -> int:
    text = update.message.text.strip()

    if text == 'Заявки':
        status_keyboard = ReplyKeyboardMarkup(
            [['Новая', 'В работе', 'Завершена'], ['Назад']],
            resize_keyboard=True
        )
        await update.message.reply_text("Выберите статус заявок:", reply_markup=status_keyboard)
        return EMPLOYEE_SELECT_STATUS

    if text == 'Назад':
        # Возврат в панель сотрудника вместо выхода
        panel_keyboard = ReplyKeyboardMarkup(
            [['Заявки'], ['Назад']],
            resize_keyboard=True
        )
        await update.message.reply_text("👷 Панель сотрудника", reply_markup=panel_keyboard)
        return EMPLOYEE_PANEL

    await update.message.reply_text("Пожалуйста, выберите действие из меню.")
    return EMPLOYEE_PANEL


async def show_reports(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    request_id = int(query.data.split("_")[-1])
    reports = get_reports_by_request(request_id)

    if not reports:
        await query.message.reply_text("По этой заявке пока нет отчетов.")
        return

    for report in reports:
        text = f"<b>Отчет #{report[3]}</b>\n{html.escape(report[4])}"  # report_number, text
        await context.bot.send_message(chat_id=query.from_user.id, text=text, parse_mode=ParseMode.HTML)

async def handle_add_employee_name(update: Update, context: CallbackContext) -> int:
    emp_id = context.user_data.get('new_emp_id')
    if not emp_id:
        await update.message.reply_text("Ошибка: ID сотрудника не найден. Начните заново.", reply_markup=universal_admin_keyboard)
        return EMPLOYEE_MENU

    # проверяем, есть ли уже такой сотрудник
    if Database.get_employee(emp_id):
        await update.message.reply_text(f"Сотрудник с ID {emp_id} уже существует.", reply_markup=employee_menu_keyboard)
        return EMPLOYEE_MENU

    name = update.message.text.strip()
    Database.add_employee(emp_id, name)
    await update.message.reply_text(f"Сотрудник {name} (ID {emp_id}) добавлен!", reply_markup=employee_menu_keyboard)
    return EMPLOYEE_MENU

async def handle_brigade_details(update: Update, context: CallbackContext) -> int:
    text = update.message.text.strip()
    try:
        parts = [p.strip() for p in text.split(',')]
        name = parts[0]
        ids = [int(p) for p in parts[1:] if p.isdigit()]
        if not name or not ids:
            raise ValueError
    except Exception:
        await update.message.reply_text(
            "❌ Неверный формат. Введите так:\n"
            "Название, id1, id2, id3",
            reply_markup=universal_admin_keyboard
        )
        return BRIGADE_WAIT_FOR_DETAILS

    # проверяем существование каждого сотрудника
    invalid = [eid for eid in ids if not Database.get_employee(eid)]
    if invalid:
        await update.message.reply_text(
            f"❌ Сотрудники с ID {', '.join(map(str, invalid))} не найдены в системе.",
            reply_markup=universal_admin_keyboard
        )
        return BRIGADE_WAIT_FOR_DETAILS

    # сохраняем корректную бригаду
    Database.add_brigade(name, ids)
    await update.message.reply_text(
        f"✅ Бригада «{name}» создана ({len(ids)} чел.)",
        reply_markup=brigade_menu_keyboard
    )
    return BRIGADE_MENU


def main() -> None:
    TOKEN = os.environ.get('BOT_TOKEN', '8089002718:AAE5-BTHdznLcRfNNs3d_ZmtKWSwYTb4MPw')
    application = ApplicationBuilder().token(TOKEN).build()

    # ConversationHandler для фильтрации заявок/истории по дате
    filter_requests_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^(📋 Мои заявки|🗓 История обслуживания)$'), start_requests_filter)],
        states={
            FILTER_YEAR:  [CallbackQueryHandler(filter_year_handler,   pattern="^filter_year:")],
            FILTER_MONTH: [CallbackQueryHandler(filter_month_handler,  pattern="^filter_month:")],
            FILTER_DAY:   [
                CallbackQueryHandler(filter_day_handler,      pattern="^filter_day:"),
                CallbackQueryHandler(filter_back_day_handler, pattern="^filter_back_day:")
            ]
        },
        fallbacks=[
            CallbackQueryHandler(filter_cancel_handler,      pattern="^filter_cancel$"),
            CallbackQueryHandler(filter_back_year_handler,   pattern="^filter_back_year$"),
            CallbackQueryHandler(filter_back_month_handler,  pattern="^filter_back_month$")
        ],
        allow_reentry=True
    )

    # ConversationHandler для редактирования профиля
    edit_profile_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_profile_start_callback, pattern="^edit_profile$")],
        states={
            EDIT_PROFILE_CHOICE:           [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_profile_choice)],
            EDIT_PROFILE_NAME:             [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_profile_name)],
            EDIT_PROFILE_PHONE:            [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_profile_phone)],
            EDIT_PROFILE_ADDRESS_OPTS:     [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_profile_address_choice)],
            EDIT_PROFILE_ADDRESS_CHANGE_INDEX: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_profile_address_change_index)],
            EDIT_PROFILE_ADDRESS_CHANGE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_profile_address_change_input)],
            EDIT_PROFILE_ADDRESS_ADD:      [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_profile_address_add)],
            EDIT_PROFILE_ADDRESS_DEL:      [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_profile_address_del)],
        },
        fallbacks=[MessageHandler(filters.Regex('^Назад$'), lambda update, context: ConversationHandler.END)]
    )

    # ConversationHandler для создания заявки
    request_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Text("📝 Создать заявку"), create_request_start)],
        states={
            REQUEST_TYPE: [
                MessageHandler(filters.Regex('^❌ Отмена$'), cancel),
                MessageHandler(filters.Regex(r'^(🔧|🛠|🔍|⚙|🏠|SOS).*'), get_request_type)
            ],
            USER_PROBLEM_DESCRIPTION: [
                MessageHandler(filters.Regex('^❌ Отмена$'), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_problem_description)
            ],
            USER_MEDIA_UPLOAD: [
                MessageHandler(filters.Regex('^❌ Отмена$'), cancel),
                MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.AUDIO | filters.VOICE, handle_media),
                MessageHandler(filters.Text("📎 Готово"), finish_request)
            ],
            USER_SOS_PHONE: [
                MessageHandler(filters.Regex('^❌ Отмена$'), cancel),
                MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), get_sos_phone)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # Основной ConversationHandler (регистрация, админ, панель сотрудника)
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            # регистрация
            USER_NAME:      [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            USER_CLIENT:    [MessageHandler(filters.Regex('^(Да|Нет)$'), get_client)],
            USER_PHONE:     [MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), get_phone)],
            USER_ADDRESS:   [MessageHandler(filters.TEXT & ~filters.COMMAND, get_address)],
            USER_ADDRESSES: [MessageHandler(filters.Regex('^(Да|Нет)$'), registration_complete)],

            # админ-панель
            ADMIN_MAIN:             [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_menu_choice)],
            ADMIN_CHOOSE_ADD_TYPE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_choose_add_type)],
            ADMIN_WAIT_FOR_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_receive_user_id)],
            ADMIN_REQ_CATEGORY:     [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_list_requests_by_category)],
            ADMIN_REQ_CATEGORY_LIST:[MessageHandler(filters.TEXT & ~filters.COMMAND, admin_requests_list_handler)],
            ADMIN_CONTROL_REQUEST:  [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_control_request_handler)],
            MAILING_WAIT_FOR_TEXT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, mailing_handler)],
            ADMIN_SALES_CARDS_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_sales_cards_menu)],
            ADMIN_CREATE_CARD_PHOTOS: [
                MessageHandler(filters.PHOTO,                            admin_create_card_photos),
                MessageHandler(filters.TEXT & ~filters.COMMAND,          admin_create_card_photos_done)
            ],
            ADMIN_SELECT_CARD_SECTION:[MessageHandler(filters.TEXT & ~filters.COMMAND, admin_select_card_section)],
            ADMIN_CREATE_CARD_TITLE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_create_card_title)],
            ADMIN_SELECT_CARD_EDIT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_select_card_edit)],
            ADMIN_SELECT_CARD_DELETE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_select_card_delete)],
            ADMIN_DELETE_CARD_CONFIRM: [MessageHandler(filters.Regex('^(Да|Нет)$'), admin_delete_card_confirm)],

            # управление сотрудниками и бригадами
            EMPLOYEE_MENU:             [MessageHandler(filters.TEXT & ~filters.COMMAND, employee_menu)],
            EMPLOYEE_WAIT_FOR_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, employee_receive_user_id)],
            EMPLOYEE_WAIT_FOR_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_employee_name)],
            BRIGADE_MENU:              [MessageHandler(filters.TEXT & ~filters.COMMAND, brigade_menu)],
            BRIGADE_WAIT_FOR_DETAILS:  [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_brigade_details)],

            # панель сотрудника
            EMPLOYEE_PANEL:        [MessageHandler(filters.TEXT & ~filters.COMMAND, employee_panel_handler)],
            EMPLOYEE_SELECT_STATUS:[MessageHandler(filters.TEXT & ~filters.COMMAND, employee_select_status)],
            EMPLOYEE_VIEW_BY_STATUS:[MessageHandler(filters.TEXT & ~filters.COMMAND, employee_view_by_status)],
            EMPLOYEE_VIEW_REQUEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, employee_control_request_handler)],
            EMPLOYEE_REPORT_TEXT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, employee_report_text)],
            EMPLOYEE_REPORT_FILES: [MessageHandler(filters.Document.ALL | filters.PHOTO, employee_report_files)],
            REPORT_RECIPIENTS:     [CallbackQueryHandler(handle_report_recipients, pattern="^report_")],

            # комментарий администратора
            ADMIN_COMMENT_TEXT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_comment_text)],
            ADMIN_COMMENT_FILES: [MessageHandler(filters.Document.ALL | filters.PHOTO | filters.TEXT, admin_comment_files)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    # Регистрируем ConversationHandler'ы
    application.add_handler(filter_requests_conv_handler)
    application.add_handler(edit_profile_conv_handler)
    application.add_handler(request_conv)
    application.add_handler(conv_handler)

    # CallbackQueryHandler'ы
    application.add_handler(CallbackQueryHandler(start_employee_report, pattern="^emp_report_\\d+$"))
    application.add_handler(CallbackQueryHandler(assign_brigade_callback,   pattern="^assign_brigade_"))
    application.add_handler(CallbackQueryHandler(brigade_select_callback,   pattern="^brigade_select_"))
    application.add_handler(CallbackQueryHandler(lambda q, c: (q.answer(), q.message.delete()), pattern="^brigade_cancel$"))
    application.add_handler(CallbackQueryHandler(back_to_request_handler,   pattern=r"^back_to_request_\d+$"))
    application.add_handler(CallbackQueryHandler(show_files_handler,        pattern="^(user_files|admin_files)_"))
    application.add_handler(CallbackQueryHandler(show_reports,              pattern=r"^show_reports_\d+$"))
    application.add_handler(CallbackQueryHandler(sales_cards_callback_handler,
                                                pattern="^(card_|view_photos_|send_request_|photos_back|main_menu)"))
    application.add_handler(CallbackQueryHandler(filter_requests_callback,  pattern="^filter_requests$"))

    # Общие MessageHandler'ы
    application.add_handler(MessageHandler(filters.Regex('^👤 Профиль$'),         show_profile))
    application.add_handler(MessageHandler(filters.Regex('^📋 Мои заявки$'),       show_requests))
    application.add_handler(MessageHandler(filters.Regex('^🗓 История обслуживания$'), show_history))
    application.add_handler(MessageHandler(filters.Text("Отдел продаж"),         sales_cards_user_view))
    application.add_handler(MessageHandler(filters.Text("Запасные части"),        sales_cards_user_view))
    application.add_handler(MessageHandler(filters.Text("Покупка оборудования"),  sales_cards_user_view))

    application.run_polling()


if __name__ == '__main__':
    main()


