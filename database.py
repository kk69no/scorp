"""
Database layer — aiosqlite + all CRUD operations.
"""

import aiosqlite
import secrets
import csv
import io
from datetime import datetime, date, time, timedelta
from typing import Optional

from config import DATABASE_PATH, NOSHOW_BLACKLIST_THRESHOLD


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id     INTEGER UNIQUE NOT NULL,
                username        TEXT,
                full_name       TEXT NOT NULL,
                phone           TEXT,
                birthday        TEXT,
                referral_code   TEXT UNIQUE,
                notify_reminders  INTEGER DEFAULT 1,
                notify_promos     INTEGER DEFAULT 1,
                notify_birthday   INTEGER DEFAULT 1,
                pending_discount  INTEGER DEFAULT 0 NOT NULL,
                referred_by     INTEGER REFERENCES users(id),
                loyalty_points  INTEGER DEFAULT 0,
                visits_count    INTEGER DEFAULT 0,
                noshow_count    INTEGER DEFAULT 0,
                is_blacklisted  INTEGER DEFAULT 0,
                is_admin        INTEGER DEFAULT 0,
                created_at      TEXT DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS bookings (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL REFERENCES users(id),
                booking_date    TEXT NOT NULL,
                start_time      TEXT NOT NULL,
                end_time        TEXT NOT NULL,
                duration_hours  INTEGER NOT NULL,
                guests_count    INTEGER NOT NULL DEFAULT 1,
                base_price      INTEGER NOT NULL DEFAULT 0,
                extras_price    INTEGER NOT NULL DEFAULT 0,
                discount        INTEGER NOT NULL DEFAULT 0,
                total_price     INTEGER NOT NULL DEFAULT 0,
                prepaid         INTEGER DEFAULT 0,
                status          TEXT NOT NULL DEFAULT 'pending',
                admin_note      TEXT DEFAULT '',
                created_at      TEXT DEFAULT (datetime('now', 'localtime')),
                reminded        INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS booking_extras (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id      INTEGER NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
                category        TEXT NOT NULL,
                item_name       TEXT NOT NULL,
                price           INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL REFERENCES users(id),
                booking_id      INTEGER REFERENCES bookings(id),
                rating          INTEGER NOT NULL,
                comment         TEXT,
                created_at      TEXT DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS blocked_dates (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                blocked_date    TEXT NOT NULL,
                reason          TEXT,
                created_at      TEXT DEFAULT (datetime('now', 'localtime'))
            );

            CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings(booking_date);
            CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id);
            CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);
            CREATE INDEX IF NOT EXISTS idx_users_tg ON users(telegram_id);
            CREATE INDEX IF NOT EXISTS idx_users_ref ON users(referral_code);

            CREATE TABLE IF NOT EXISTS promo_codes (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                code            TEXT UNIQUE NOT NULL,
                discount_percent INTEGER DEFAULT 0,
                discount_amount INTEGER DEFAULT 0,
                max_uses        INTEGER DEFAULT 0,
                used_count      INTEGER DEFAULT 0,
                valid_to        TEXT,
                created_by      INTEGER,
                is_active       INTEGER DEFAULT 1,
                created_at      TEXT DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS admin_logs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_telegram_id INTEGER NOT NULL,
                action          TEXT NOT NULL,
                details         TEXT,
                created_at      TEXT DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS user_notes (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL REFERENCES users(id),
                admin_telegram_id INTEGER NOT NULL,
                note            TEXT NOT NULL,
                created_at      TEXT DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS consoles (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT UNIQUE NOT NULL,
                status          TEXT DEFAULT 'active',
                note            TEXT DEFAULT '',
                updated_at      TEXT DEFAULT (datetime('now', 'localtime'))
            );
        """)
        await db.commit()
    finally:
        await db.close()


# ─── Users ───────────────────────────────────────────────

def _gen_referral_code() -> str:
    return secrets.token_hex(4).upper()


async def get_user(telegram_id: int) -> Optional[dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def create_user(
    telegram_id: int,
    username: str | None,
    full_name: str,
    phone: str | None = None,
    birthday: str | None = None,
    referred_by_code: str | None = None,
) -> dict:
    db = await get_db()
    try:
        referral_code = _gen_referral_code()

        referred_by_id = None
        if referred_by_code:
            cur = await db.execute(
                "SELECT id FROM users WHERE referral_code = ?", (referred_by_code,)
            )
            ref_row = await cur.fetchone()
            if ref_row:
                referred_by_id = ref_row["id"]

        await db.execute(
            """INSERT INTO users (telegram_id, username, full_name, phone, birthday,
                                  referral_code, referred_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (telegram_id, username, full_name, phone, birthday,
             referral_code, referred_by_id),
        )
        await db.commit()

        if referred_by_id:
            from config import LOYALTY_REFERRAL_POINTS
            await db.execute(
                "UPDATE users SET loyalty_points = loyalty_points + ? WHERE id = ?",
                (LOYALTY_REFERRAL_POINTS, referred_by_id),
            )
            await db.commit()

        return await get_user(telegram_id)
    finally:
        await db.close()


async def update_user(telegram_id: int, **kwargs) -> None:
    if not kwargs:
        return
    db = await get_db()
    try:
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [telegram_id]
        await db.execute(
            f"UPDATE users SET {sets} WHERE telegram_id = ?", vals
        )
        await db.commit()
    finally:
        await db.close()


async def get_user_by_id(user_id: int) -> Optional[dict]:
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_all_users() -> list[dict]:
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM users WHERE is_blacklisted = 0")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_all_users_including_blocked() -> list[dict]:
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM users ORDER BY created_at DESC")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def search_users(query: str) -> list[dict]:
    db = await get_db()
    try:
        q = f"%{query}%"
        cur = await db.execute(
            """SELECT * FROM users
               WHERE full_name LIKE ? OR phone LIKE ? OR username LIKE ?
               ORDER BY created_at DESC LIMIT 20""",
            (q, q, q),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def set_admin(telegram_id: int) -> None:
    await update_user(telegram_id, is_admin=1)


async def remove_admin(telegram_id: int) -> None:
    await update_user(telegram_id, is_admin=0)


async def get_admins() -> list[dict]:
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM users WHERE is_admin = 1")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def is_admin(telegram_id: int) -> bool:
    from config import ADMIN_IDS
    if telegram_id in ADMIN_IDS:
        return True
    user = await get_user(telegram_id)
    return bool(user and user["is_admin"])


async def blacklist_user(telegram_id: int) -> None:
    await update_user(telegram_id, is_blacklisted=1)


async def unblacklist_user(telegram_id: int) -> None:
    await update_user(telegram_id, is_blacklisted=0)


async def increment_noshow(user_id: int) -> bool:
    """Returns True if user should be blacklisted."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE users SET noshow_count = noshow_count + 1 WHERE id = ?",
            (user_id,),
        )
        await db.commit()
        cur = await db.execute(
            "SELECT telegram_id, noshow_count FROM users WHERE id = ?", (user_id,)
        )
        row = await cur.fetchone()
        if row and row["noshow_count"] >= NOSHOW_BLACKLIST_THRESHOLD:
            await blacklist_user(row["telegram_id"])
            return True
        return False
    finally:
        await db.close()


async def add_loyalty_points(telegram_id: int, points: int) -> None:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE users SET loyalty_points = loyalty_points + ? WHERE telegram_id = ?",
            (points, telegram_id),
        )
        await db.commit()
    finally:
        await db.close()


async def set_loyalty_points(telegram_id: int, points: int) -> None:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE users SET loyalty_points = ? WHERE telegram_id = ?",
            (points, telegram_id),
        )
        await db.commit()
    finally:
        await db.close()


async def increment_visits(telegram_id: int) -> int:
    """Returns new visit count."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE users SET visits_count = visits_count + 1 WHERE telegram_id = ?",
            (telegram_id,),
        )
        await db.commit()
        cur = await db.execute(
            "SELECT visits_count FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cur.fetchone()
        return row["visits_count"] if row else 0
    finally:
        await db.close()


# ─── Bookings ────────────────────────────────────────────

async def create_booking(
    user_id: int,
    booking_date: str,
    start_time: str,
    end_time: str,
    duration_hours: int,
    guests_count: int,
    base_price: int,
    extras_price: int,
    discount: int,
    total_price: int,
    extras: list[dict] | None = None,
    admin_note: str = "",
) -> int:
    db = await get_db()
    try:
        cur = await db.execute(
            """INSERT INTO bookings
               (user_id, booking_date, start_time, end_time, duration_hours,
                guests_count, base_price, extras_price, discount, total_price,
                status, admin_note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmed', ?)""",
            (user_id, booking_date, start_time, end_time, duration_hours,
             guests_count, base_price, extras_price, discount, total_price, admin_note),
        )
        booking_id = cur.lastrowid

        if extras:
            for ext in extras:
                await db.execute(
                    """INSERT INTO booking_extras (booking_id, category, item_name, price)
                       VALUES (?, ?, ?, ?)""",
                    (booking_id, ext["category"], ext["item_name"], ext["price"]),
                )

        await db.commit()
        return booking_id
    finally:
        await db.close()


async def get_booking(booking_id: int) -> Optional[dict]:
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
        row = await cur.fetchone()
        if not row:
            return None
        booking = dict(row)

        cur2 = await db.execute(
            "SELECT * FROM booking_extras WHERE booking_id = ?", (booking_id,)
        )
        extras = await cur2.fetchall()
        booking["extras"] = [dict(e) for e in extras]
        return booking
    finally:
        await db.close()


async def get_user_bookings(telegram_id: int, active_only: bool = False) -> list[dict]:
    db = await get_db()
    try:
        user = await get_user(telegram_id)
        if not user:
            return []

        if active_only:
            query = """SELECT * FROM bookings
                       WHERE user_id = ? AND status IN ('confirmed', 'pending')
                       AND (booking_date > date('now', 'localtime')
                            OR (booking_date = date('now', 'localtime')
                                AND end_time > time('now', 'localtime')))
                       ORDER BY booking_date, start_time"""
        else:
            query = """SELECT * FROM bookings WHERE user_id = ?
                       ORDER BY booking_date DESC, start_time DESC LIMIT 20"""

        cur = await db.execute(query, (user["id"],))
        rows = await cur.fetchall()
        result = []
        for row in rows:
            b = dict(row)
            cur2 = await db.execute(
                "SELECT * FROM booking_extras WHERE booking_id = ?", (b["id"],)
            )
            b["extras"] = [dict(e) for e in await cur2.fetchall()]
            result.append(b)
        return result
    finally:
        await db.close()


async def get_user_bookings_by_id(user_id: int, limit: int = 10) -> list[dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT * FROM bookings WHERE user_id = ?
               ORDER BY booking_date DESC, start_time DESC LIMIT ?""",
            (user_id, limit),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_last_booking(telegram_id: int) -> Optional[dict]:
    db = await get_db()
    try:
        user = await get_user(telegram_id)
        if not user:
            return None
        cur = await db.execute(
            """SELECT * FROM bookings WHERE user_id = ? AND status = 'completed'
               ORDER BY created_at DESC LIMIT 1""",
            (user["id"],),
        )
        row = await cur.fetchone()
        if not row:
            return None
        b = dict(row)
        cur2 = await db.execute(
            "SELECT * FROM booking_extras WHERE booking_id = ?", (b["id"],)
        )
        b["extras"] = [dict(e) for e in await cur2.fetchall()]
        return b
    finally:
        await db.close()


async def cancel_booking(booking_id: int) -> bool:
    db = await get_db()
    try:
        cur = await db.execute(
            "UPDATE bookings SET status = 'cancelled' WHERE id = ? AND status IN ('confirmed', 'pending')",
            (booking_id,),
        )
        await db.commit()
        return cur.rowcount > 0
    finally:
        await db.close()


async def update_booking_status(booking_id: int, status: str) -> None:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE bookings SET status = ? WHERE id = ?", (status, booking_id)
        )
        await db.commit()
    finally:
        await db.close()


async def update_booking_fields(booking_id: int, **kwargs) -> None:
    if not kwargs:
        return
    db = await get_db()
    try:
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [booking_id]
        await db.execute(f"UPDATE bookings SET {sets} WHERE id = ?", vals)
        await db.commit()
    finally:
        await db.close()


async def mark_reminded(booking_id: int) -> None:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE bookings SET reminded = 1 WHERE id = ?", (booking_id,)
        )
        await db.commit()
    finally:
        await db.close()


async def get_guests_at_time(booking_date: str, time_str: str) -> int:
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT COALESCE(SUM(guests_count), 0) as total
               FROM bookings
               WHERE booking_date = ?
                 AND start_time <= ? AND end_time > ?
                 AND status IN ('confirmed', 'pending')""",
            (booking_date, time_str, time_str),
        )
        row = await cur.fetchone()
        return row["total"] if row else 0
    finally:
        await db.close()


async def get_available_capacity(booking_date: str, start_time: str, duration_hours: int) -> int:
    from config import MAX_CAPACITY
    min_avail = MAX_CAPACITY

    start_h, start_m = map(int, start_time.split(":"))
    for h_offset in range(duration_hours):
        check_h = (start_h + h_offset) % 24
        check_time = f"{check_h:02d}:00"
        booked = await get_guests_at_time(booking_date, check_time)
        avail = MAX_CAPACITY - booked
        if avail < min_avail:
            min_avail = avail

    return max(0, min_avail)


async def get_bookings_for_date(booking_date: str) -> list[dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT b.*, u.full_name, u.phone, u.telegram_id
               FROM bookings b JOIN users u ON b.user_id = u.id
               WHERE b.booking_date = ? AND b.status IN ('confirmed', 'pending')
               ORDER BY b.start_time""",
            (booking_date,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_bookings_for_period(start_date: str, end_date: str) -> list[dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT b.*, u.full_name, u.phone, u.telegram_id
               FROM bookings b JOIN users u ON b.user_id = u.id
               WHERE b.booking_date BETWEEN ? AND ?
                 AND b.status IN ('confirmed', 'pending', 'completed')
               ORDER BY b.booking_date, b.start_time""",
            (start_date, end_date),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_upcoming_reminders() -> list[dict]:
    from config import REMINDER_BEFORE_HOURS
    db = await get_db()
    try:
        now = datetime.now()
        remind_time = now + timedelta(hours=REMINDER_BEFORE_HOURS)

        cur = await db.execute(
            """SELECT b.*, u.telegram_id
               FROM bookings b JOIN users u ON b.user_id = u.id
               WHERE b.status = 'confirmed'
                 AND b.reminded = 0
                 AND b.booking_date = ?
                 AND b.start_time <= ?
                 AND b.start_time > ?""",
            (now.strftime("%Y-%m-%d"),
             remind_time.strftime("%H:%M"),
             now.strftime("%H:%M")),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_completed_needing_feedback() -> list[dict]:
    from config import FEEDBACK_AFTER_MINUTES
    db = await get_db()
    try:
        now = datetime.now()
        check_after = now - timedelta(minutes=FEEDBACK_AFTER_MINUTES + 10)
        check_before = now - timedelta(minutes=FEEDBACK_AFTER_MINUTES)

        cur = await db.execute(
            """SELECT b.*, u.telegram_id
               FROM bookings b
               JOIN users u ON b.user_id = u.id
               LEFT JOIN reviews r ON r.booking_id = b.id
               WHERE b.status = 'completed'
                 AND r.id IS NULL
                 AND b.booking_date = ?
                 AND b.end_time BETWEEN ? AND ?""",
            (now.strftime("%Y-%m-%d"),
             check_after.strftime("%H:%M"),
             check_before.strftime("%H:%M")),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def auto_complete_expired() -> int:
    """Auto-complete bookings whose end time has passed. Returns count."""
    db = await get_db()
    try:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M")

        cur = await db.execute(
            """UPDATE bookings SET status = 'completed'
               WHERE status = 'confirmed'
                 AND (booking_date < ?
                      OR (booking_date = ? AND end_time <= ?))""",
            (today, today, current_time),
        )
        await db.commit()
        return cur.rowcount
    finally:
        await db.close()


# ─── Blocked dates ───────────────────────────────────────

async def block_date(blocked_date: str, reason: str = "") -> None:
    db = await get_db()
    try:
        await db.execute(
            "INSERT OR REPLACE INTO blocked_dates (blocked_date, reason) VALUES (?, ?)",
            (blocked_date, reason),
        )
        await db.commit()
    finally:
        await db.close()


async def unblock_date(blocked_date: str) -> None:
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM blocked_dates WHERE blocked_date = ?", (blocked_date,)
        )
        await db.commit()
    finally:
        await db.close()


async def is_date_blocked(check_date: str) -> bool:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT 1 FROM blocked_dates WHERE blocked_date = ?", (check_date,)
        )
        return await cur.fetchone() is not None
    finally:
        await db.close()


async def get_all_blocked_dates() -> list[dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM blocked_dates WHERE blocked_date >= date('now','localtime') ORDER BY blocked_date"
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ─── Reviews ─────────────────────────────────────────────

async def create_review(user_id: int, booking_id: int | None, rating: int, comment: str = "") -> int:
    db = await get_db()
    try:
        cur = await db.execute(
            "INSERT INTO reviews (user_id, booking_id, rating, comment) VALUES (?, ?, ?, ?)",
            (user_id, booking_id, rating, comment),
        )
        await db.commit()
        return cur.lastrowid
    finally:
        await db.close()


async def get_average_rating() -> tuple[float, int]:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT AVG(rating) as avg_r, COUNT(*) as cnt FROM reviews"
        )
        row = await cur.fetchone()
        avg = round(row["avg_r"], 1) if row["avg_r"] else 0.0
        return avg, row["cnt"]
    finally:
        await db.close()


async def get_all_reviews(limit: int = 30) -> list[dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT r.*, u.full_name, u.telegram_id
               FROM reviews r JOIN users u ON r.user_id = u.id
               ORDER BY r.created_at DESC LIMIT ?""",
            (limit,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ─── Stats ───────────────────────────────────────────────

async def get_stats() -> dict:
    db = await get_db()
    try:
        stats = {}

        cur = await db.execute("SELECT COUNT(*) as c FROM users")
        stats["total_users"] = (await cur.fetchone())["c"]

        cur = await db.execute(
            "SELECT COUNT(*) as c FROM bookings WHERE status = 'confirmed'"
        )
        stats["active_bookings"] = (await cur.fetchone())["c"]

        cur = await db.execute(
            "SELECT COUNT(*) as c FROM bookings WHERE status = 'completed'"
        )
        stats["completed_bookings"] = (await cur.fetchone())["c"]

        cur = await db.execute(
            """SELECT COUNT(*) as c FROM bookings
               WHERE status = 'confirmed' AND booking_date = date('now', 'localtime')"""
        )
        stats["today_bookings"] = (await cur.fetchone())["c"]

        cur = await db.execute(
            "SELECT COALESCE(SUM(total_price), 0) as s FROM bookings WHERE status = 'completed'"
        )
        stats["total_revenue"] = (await cur.fetchone())["s"]

        cur = await db.execute(
            """SELECT COALESCE(SUM(total_price), 0) as s FROM bookings
               WHERE status = 'completed'
                 AND booking_date >= date('now', 'localtime', '-7 days')"""
        )
        stats["week_revenue"] = (await cur.fetchone())["s"]

        cur = await db.execute(
            """SELECT COALESCE(SUM(total_price), 0) as s FROM bookings
               WHERE status = 'completed'
                 AND booking_date >= date('now', 'localtime', '-30 days')"""
        )
        stats["month_revenue"] = (await cur.fetchone())["s"]

        cur = await db.execute(
            """SELECT COALESCE(AVG(total_price), 0) as a FROM bookings
               WHERE status = 'completed'"""
        )
        stats["avg_check"] = round((await cur.fetchone())["a"])

        avg_r, cnt_r = await get_average_rating()
        stats["avg_rating"] = avg_r
        stats["reviews_count"] = cnt_r

        cur = await db.execute(
            "SELECT COUNT(*) as c FROM bookings WHERE status = 'no_show'"
        )
        stats["noshows"] = (await cur.fetchone())["c"]

        cur = await db.execute(
            "SELECT COUNT(*) as c FROM bookings WHERE status = 'cancelled'"
        )
        stats["cancellations"] = (await cur.fetchone())["c"]

        # Popular hours
        cur = await db.execute(
            """SELECT start_time, COUNT(*) as c FROM bookings
               WHERE status IN ('confirmed', 'completed')
               GROUP BY start_time ORDER BY c DESC LIMIT 5"""
        )
        stats["popular_hours"] = [dict(r) for r in await cur.fetchall()]

        # Popular weekdays
        cur = await db.execute(
            """SELECT
                 CASE CAST(strftime('%w', booking_date) AS INTEGER)
                   WHEN 0 THEN 'Вс' WHEN 1 THEN 'Пн' WHEN 2 THEN 'Вт'
                   WHEN 3 THEN 'Ср' WHEN 4 THEN 'Чт' WHEN 5 THEN 'Пт'
                   WHEN 6 THEN 'Сб'
                 END as day_name,
                 COUNT(*) as c
               FROM bookings
               WHERE status IN ('confirmed', 'completed')
               GROUP BY day_name ORDER BY c DESC"""
        )
        stats["popular_days"] = [dict(r) for r in await cur.fetchall()]

        # Avg guests per booking
        cur = await db.execute(
            """SELECT COALESCE(AVG(guests_count), 0) as a FROM bookings
               WHERE status IN ('confirmed', 'completed')"""
        )
        stats["avg_guests"] = round((await cur.fetchone())["a"], 1)

        # Avg duration
        cur = await db.execute(
            """SELECT COALESCE(AVG(duration_hours), 0) as a FROM bookings
               WHERE status IN ('confirmed', 'completed')"""
        )
        stats["avg_duration"] = round((await cur.fetchone())["a"], 1)

        # New users this week
        cur = await db.execute(
            """SELECT COUNT(*) as c FROM users
               WHERE created_at >= datetime('now', 'localtime', '-7 days')"""
        )
        stats["new_users_week"] = (await cur.fetchone())["c"]

        # Repeat rate
        cur = await db.execute(
            """SELECT COUNT(*) as c FROM users WHERE visits_count >= 2"""
        )
        stats["repeat_users"] = (await cur.fetchone())["c"]

        return stats
    finally:
        await db.close()


async def get_hourly_occupancy(booking_date: str) -> dict[str, int]:
    """Returns guests count per hour slot for a date."""
    from config import WORK_HOURS_START, WORK_HOURS_END
    result = {}
    if WORK_HOURS_END <= WORK_HOURS_START:
        hours = list(range(WORK_HOURS_START, 24)) + list(range(0, WORK_HOURS_END))
    else:
        hours = list(range(WORK_HOURS_START, WORK_HOURS_END))

    for h in hours:
        time_str = f"{h:02d}:00"
        count = await get_guests_at_time(booking_date, time_str)
        result[time_str] = count
    return result


async def get_revenue_by_day(days: int = 30) -> list[dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT booking_date, COUNT(*) as bookings,
                      SUM(total_price) as revenue, SUM(guests_count) as guests
               FROM bookings
               WHERE status = 'completed'
                 AND booking_date >= date('now', 'localtime', ? || ' days')
               GROUP BY booking_date ORDER BY booking_date DESC""",
            (f"-{days}",),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_users_with_birthday_soon(days_ahead: int = 7) -> list[dict]:
    db = await get_db()
    try:
        today = date.today()
        results = []
        cur = await db.execute(
            "SELECT * FROM users WHERE birthday IS NOT NULL AND is_blacklisted = 0"
        )
        rows = await cur.fetchall()
        for row in rows:
            user = dict(row)
            try:
                bday = datetime.strptime(user["birthday"], "%d.%m.%Y").date()
                this_year_bday = bday.replace(year=today.year)
                if this_year_bday < today:
                    this_year_bday = bday.replace(year=today.year + 1)
                diff = (this_year_bday - today).days
                if 0 <= diff <= days_ahead:
                    user["days_until_birthday"] = diff
                    results.append(user)
            except (ValueError, TypeError):
                continue
        return results
    finally:
        await db.close()


async def export_bookings_csv(days: int = 30) -> str:
    """Export bookings as CSV string."""
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT b.id, b.booking_date, b.start_time, b.end_time,
                      b.duration_hours, b.guests_count, b.total_price,
                      b.status, b.admin_note, u.full_name, u.phone
               FROM bookings b JOIN users u ON b.user_id = u.id
               WHERE b.booking_date >= date('now', 'localtime', ? || ' days')
               ORDER BY b.booking_date DESC, b.start_time DESC""",
            (f"-{days}",),
        )
        rows = await cur.fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "Дата", "Начало", "Конец", "Часы", "Гости",
            "Сумма", "Статус", "Заметка", "Клиент", "Телефон"
        ])
        for r in rows:
            writer.writerow([
                r["id"], r["booking_date"], r["start_time"], r["end_time"],
                r["duration_hours"], r["guests_count"], r["total_price"],
                r["status"], r["admin_note"] or "", r["full_name"], r["phone"] or ""
            ])
        return output.getvalue()
    finally:
        await db.close()


# ─── Promo codes ─────────────────────────────────────────

async def create_promo_code(code: str, discount_percent: int = 0, discount_amount: int = 0,
                            max_uses: int = 0, valid_to: str = "", created_by: int = 0) -> int:
    db = await get_db()
    try:
        cur = await db.execute(
            """INSERT INTO promo_codes (code, discount_percent, discount_amount, max_uses, valid_to, created_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (code.upper(), discount_percent, discount_amount, max_uses, valid_to, created_by),
        )
        await db.commit()
        return cur.lastrowid
    finally:
        await db.close()


async def get_promo_code(code: str) -> Optional[dict]:
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM promo_codes WHERE code = ?", (code.upper(),))
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_all_promo_codes() -> list[dict]:
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM promo_codes ORDER BY created_at DESC")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def use_promo_code(code: str) -> bool:
    db = await get_db()
    try:
        cur = await db.execute(
            """UPDATE promo_codes SET used_count = used_count + 1
               WHERE code = ? AND is_active = 1
               AND (max_uses = 0 OR used_count < max_uses)""",
            (code.upper(),),
        )
        await db.commit()
        return cur.rowcount > 0
    finally:
        await db.close()


async def delete_promo_code(code: str) -> bool:
    db = await get_db()
    try:
        cur = await db.execute("DELETE FROM promo_codes WHERE code = ?", (code.upper(),))
        await db.commit()
        return cur.rowcount > 0
    finally:
        await db.close()


async def validate_promo_code(code: str) -> Optional[dict]:
    promo = await get_promo_code(code)
    if not promo or not promo["is_active"]:
        return None
    if promo["max_uses"] > 0 and promo["used_count"] >= promo["max_uses"]:
        return None
    if promo["valid_to"]:
        from datetime import date as _d
        if promo["valid_to"] < _d.today().isoformat():
            return None
    return promo


# ─── Admin logs ──────────────────────────────────────────

async def add_admin_log(admin_tg_id: int, action: str, details: str = "") -> None:
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO admin_logs (admin_telegram_id, action, details) VALUES (?, ?, ?)",
            (admin_tg_id, action, details),
        )
        await db.commit()
    finally:
        await db.close()


async def get_admin_logs(limit: int = 50) -> list[dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT al.*, u.full_name
               FROM admin_logs al
               LEFT JOIN users u ON al.admin_telegram_id = u.telegram_id
               ORDER BY al.created_at DESC LIMIT ?""",
            (limit,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ─── User notes ──────────────────────────────────────────

async def add_user_note(user_id: int, admin_tg_id: int, note: str) -> int:
    db = await get_db()
    try:
        cur = await db.execute(
            "INSERT INTO user_notes (user_id, admin_telegram_id, note) VALUES (?, ?, ?)",
            (user_id, admin_tg_id, note),
        )
        await db.commit()
        return cur.lastrowid
    finally:
        await db.close()


async def get_user_notes(user_id: int, limit: int = 10) -> list[dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT un.*, u.full_name as admin_name
               FROM user_notes un
               LEFT JOIN users u ON un.admin_telegram_id = u.telegram_id
               WHERE un.user_id = ?
               ORDER BY un.created_at DESC LIMIT ?""",
            (user_id, limit),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ─── Consoles ────────────────────────────────────────────

async def get_consoles() -> list[dict]:
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM consoles ORDER BY name")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def update_console_status(name: str, status: str, note: str = "") -> None:
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO consoles (name, status, note, updated_at)
               VALUES (?, ?, ?, datetime('now', 'localtime'))
               ON CONFLICT(name) DO UPDATE SET status = ?, note = ?, updated_at = datetime('now', 'localtime')""",
            (name, status, note, status, note),
        )
        await db.commit()
    finally:
        await db.close()


async def init_consoles(console_names: list[str]) -> None:
    db = await get_db()
    try:
        for name in console_names:
            await db.execute("INSERT OR IGNORE INTO consoles (name) VALUES (?)", (name,))
        await db.commit()
    finally:
        await db.close()


# ─── Enhanced reporting ──────────────────────────────────

async def get_top_customers(limit: int = 10) -> list[dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT u.*, COUNT(b.id) as booking_count,
                      COALESCE(SUM(b.total_price), 0) as total_spent
               FROM users u
               LEFT JOIN bookings b ON u.id = b.user_id AND b.status = 'completed'
               WHERE u.is_blacklisted = 0
               GROUP BY u.id
               ORDER BY total_spent DESC LIMIT ?""",
            (limit,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_monthly_report(year: int, month: int) -> dict:
    db = await get_db()
    try:
        month_str = f"{year}-{month:02d}"
        report = {}

        cur = await db.execute(
            """SELECT COUNT(*) as c, COALESCE(SUM(total_price), 0) as rev,
                      COALESCE(SUM(guests_count), 0) as guests,
                      COALESCE(SUM(duration_hours), 0) as hours
               FROM bookings
               WHERE status = 'completed' AND booking_date LIKE ? || '%'""",
            (month_str,),
        )
        row = await cur.fetchone()
        report["bookings"] = row["c"]
        report["revenue"] = row["rev"]
        report["guests"] = row["guests"]
        report["hours"] = row["hours"]

        cur = await db.execute(
            "SELECT COUNT(*) as c FROM bookings WHERE status = 'cancelled' AND booking_date LIKE ? || '%'",
            (month_str,),
        )
        report["cancellations"] = (await cur.fetchone())["c"]

        cur = await db.execute(
            "SELECT COUNT(*) as c FROM bookings WHERE status = 'no_show' AND booking_date LIKE ? || '%'",
            (month_str,),
        )
        report["noshows"] = (await cur.fetchone())["c"]

        cur = await db.execute(
            "SELECT COUNT(*) as c FROM users WHERE created_at LIKE ? || '%'",
            (month_str,),
        )
        report["new_users"] = (await cur.fetchone())["c"]

        cur = await db.execute(
            "SELECT COALESCE(SUM(extras_price), 0) as e FROM bookings WHERE status = 'completed' AND booking_date LIKE ? || '%'",
            (month_str,),
        )
        report["extras_revenue"] = (await cur.fetchone())["e"]

        return report
    finally:
        await db.close()


async def get_inactive_users(days: int = 30) -> list[dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT u.* FROM users u
               WHERE u.is_blacklisted = 0
                 AND u.id NOT IN (
                     SELECT DISTINCT user_id FROM bookings
                     WHERE booking_date >= date('now', 'localtime', ? || ' days')
                       AND status IN ('confirmed', 'completed')
                 )
               ORDER BY u.created_at""",
            (f"-{days}",),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_vip_users(min_visits: int = 5) -> list[dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM users WHERE visits_count >= ? AND is_blacklisted = 0 ORDER BY visits_count DESC",
            (min_visits,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ─── Referrals & profile helpers ─────────────────────────

async def get_referrals(user_id: int) -> list[dict]:
    """Get users referred by this user (by internal id)."""
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM users WHERE referred_by = ? ORDER BY created_at DESC",
            (user_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_user_total_spent(telegram_id: int) -> int:
    """Total money spent by user on completed bookings."""
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT COALESCE(SUM(b.total_price), 0) as total
               FROM bookings b
               JOIN users u ON b.user_id = u.id
               WHERE u.telegram_id = ? AND b.status = 'completed'""",
            (telegram_id,),
        )
        row = await cur.fetchone()
        return row["total"] if row else 0
    finally:
        await db.close()
