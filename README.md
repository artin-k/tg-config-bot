# telegram-vpn-shop-bot

MVP اولیه بات تلگرام برای فروش اشتراک VPN/config با Python 3.11، aiogram 3، PostgreSQL، SQLAlchemy async، Alembic و Redis.

## امکانات فعلی

- `/start` و منوی اصلی فارسی
- خرید اشتراک، انتخاب پلن، پیش‌فاکتور، دریافت نام کاربری و ساخت سفارش
- پرداخت دستی با ارسال تصویر رسید
- اعلان پرداخت جدید برای ادمین‌ها
- تایید یا رد پرداخت توسط ادمین
- ساخت سرویس VPN با لینک‌های placeholder
- مشاهده سرویس‌های فعال کاربر
- نمایش تعرفه‌ها و پشتیبانی
- پنل مدیریت اولیه برای مشاهده پرداخت‌های در انتظار تایید، لیست پلن‌ها، افزودن پلن و فعال/غیرفعال کردن پلن

## ساخت بات در BotFather

1. در تلگرام به `@BotFather` پیام بدهید.
2. دستور `/newbot` را اجرا کنید.
3. نام و username بات را وارد کنید.
4. توکن دریافتی را در متغیر `BOT_TOKEN` داخل فایل `.env` قرار دهید.

## تنظیم محیط

ابتدا فایل نمونه را کپی کنید:

```bash
cp .env.example .env
```

سپس مقدارها را تنظیم کنید:

```env
BOT_TOKEN=توکن_بات
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/telegram_vpn_shop
REDIS_URL=
FSM_STORAGE=memory
ADMIN_IDS=123456789,987654321
SUPPORT_USERNAME=your_support_username
PAYMENT_CARD_NUMBER=0000-0000-0000-0000
PAYMENT_CARD_HOLDER=نام صاحب کارت
PAYMENT_DESCRIPTION=پرداخت سفارش اشتراک VPN
ORDER_EXPIRE_MINUTES=15
```

برای گرفتن Telegram ID ادمین‌ها می‌توانید از بات‌هایی مثل `@userinfobot` استفاده کنید. چند ادمین را با کاما در `ADMIN_IDS` وارد کنید.

## اجرا با Docker Compose

```bash
docker compose up --build
```

سرویس bot در زمان شروع، migrationها را اجرا می‌کند و سپس polling بات را شروع می‌کند.

## اجرای migration به صورت دستی

اگر فقط دیتابیس را بالا آورده‌اید:

```bash
docker compose up -d postgres redis
docker compose run --rm bot alembic upgrade head
```

پلن‌های اولیه در migration اول seed می‌شوند:

- `⚡ پلن S | 1 ماهه`، حجم ۵ گیگ، قیمت ۱,۱۰۰,۰۰۰ تومان
- `💎 پلن L | 1 ماهه`، حجم ۱۰ گیگ، قیمت ۲,۱۰۰,۰۰۰ تومان

## اجرای محلی بدون Docker

Python 3.11+ لازم است.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m bot.main
```

در ویندوز PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python -m bot.main
```

برای اجرای محلی، `DATABASE_URL` باید به PostgreSQL در دسترس از ماشین شما اشاره کند، مثلا `localhost`. اگر Redis نمی‌خواهید، مقدار `FSM_STORAGE=memory` بگذارید تا وضعیت‌های موقت بات در حافظه نگه‌داری شوند.

نمونه `.env` برای اجرای محلی بدون Docker و بدون Redis:

```env
BOT_TOKEN=توکن_بات
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/telegram_vpn_shop
REDIS_URL=
FSM_STORAGE=memory
ADMIN_IDS=123456789
SUPPORT_USERNAME=your_support_username
PAYMENT_CARD_NUMBER=0000-0000-0000-0000
PAYMENT_CARD_HOLDER=نام صاحب کارت
PAYMENT_DESCRIPTION=پرداخت سفارش اشتراک VPN
ORDER_EXPIRE_MINUTES=15
```

## جریان خرید

1. کاربر `/start` می‌زند.
2. از منوی اصلی `🔐 خرید اشتراک` را انتخاب می‌کند.
3. پلن را انتخاب می‌کند و پیش‌فاکتور می‌بیند.
4. نام کاربری معتبر وارد می‌کند.
5. سفارش و پرداخت دستی ساخته می‌شود.
6. کاربر تصویر رسید را ارسال می‌کند.
7. ادمین رسید را تایید می‌کند.
8. سرویس placeholder ساخته می‌شود و لینک config/subscription برای کاربر ارسال می‌شود.

## محدودیت‌های فعلی

- فقط پرداخت دستی پیاده‌سازی شده است.
- اتصال واقعی به پنل VPN هنوز وجود ندارد؛ `VPNPanelService` فعلا لینک‌های placeholder می‌سازد.
- Telegram Web App هنوز پیاده‌سازی نشده است.
- تمدید سرویس، کیف پول، زیرمجموعه‌گیری، آموزش، اکانت تست و گردونه شانس فعلا پیام «به‌زودی» نشان می‌دهند.

## توسعه بعدی

- برای اتصال به Marzban، 3x-ui یا Hiddify، پیاده‌سازی `app/services/vpn_panel.py` را با adapter واقعی جایگزین کنید.
- برای پرداخت آنلاین، سرویس جدیدی کنار `app/services/payment_service.py` اضافه کنید و فیلدهای `authority` و `ref_id` مدل Payment آماده استفاده هستند.
- برای Telegram Web App، لایه سرویس و repository مستقل از aiogram نوشته شده تا API یا Web App به‌راحتی روی همین domain logic سوار شود.
