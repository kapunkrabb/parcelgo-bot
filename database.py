"""
database.py — SQLite хранилище для ParcelGo Bot
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "parcelgold.db")


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        cur = self.conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY,
                name        TEXT,
                username    TEXT,
                rating      REAL    DEFAULT 5.0,
                trips_count INTEGER DEFAULT 0,
                created_at  TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS trips (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                from_city   TEXT    NOT NULL,
                to_city     TEXT    NOT NULL,
                date        TEXT    NOT NULL,
                weight      TEXT    NOT NULL,
                price       TEXT    NOT NULL,
                phone       TEXT,
                status      TEXT    DEFAULT 'active',
                created_at  TEXT    DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS requests (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                from_city   TEXT    NOT NULL,
                to_city     TEXT    NOT NULL,
                weight      TEXT    NOT NULL,
                desc        TEXT,
                budget      TEXT    NOT NULL,
                status      TEXT    DEFAULT 'pending',
                trip_id     INTEGER,
                created_at  TEXT    DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (trip_id) REFERENCES trips(id)
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user   INTEGER NOT NULL,
                to_user     INTEGER NOT NULL,
                req_id      INTEGER NOT NULL,
                stars       INTEGER NOT NULL,
                created_at  TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS blacklist (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                reason      TEXT    NOT NULL,
                is_public   INTEGER DEFAULT 1,
                banned_at   TEXT    DEFAULT (datetime('now'))
            );
        """)
        self.conn.commit()

    # ── USERS ──────────────────────────────────────────────────────────────
    def upsert_user(self, uid: int, name: str, username: str = None):
        self.conn.execute(
            "INSERT OR IGNORE INTO users (id, name, username) VALUES (?,?,?)",
            (uid, name, username)
        )
        # Обновляем username если изменился
        self.conn.execute(
            "UPDATE users SET name=?, username=? WHERE id=?",
            (name, username, uid)
        )
        self.conn.commit()

    def get_user(self, uid: int) -> dict:
        row = self.conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        return dict(row) if row else None

    # ── TRIPS ──────────────────────────────────────────────────────────────
    def add_trip(self, user_id, from_city, to_city, date, weight, price, phone) -> int:
        cur = self.conn.execute(
            "INSERT INTO trips (user_id,from_city,to_city,date,weight,price,phone) VALUES (?,?,?,?,?,?,?)",
            (user_id, from_city, to_city, date, weight, price, phone)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_trip(self, trip_id: int) -> dict:
        row = self.conn.execute("""
            SELECT t.*, u.name, u.username, u.rating
            FROM trips t JOIN users u ON t.user_id = u.id
            WHERE t.id=?
        """, (trip_id,)).fetchone()
        return dict(row) if row else None

    def get_user_trips(self, uid: int) -> list:
        rows = self.conn.execute(
            "SELECT * FROM trips WHERE user_id=? AND status='active' ORDER BY created_at DESC",
            (uid,)
        ).fetchall()
        return [dict(r) for r in rows]

    def find_travelers(self, from_city: str, to_city: str) -> list:
        """Попутчики по маршруту (для уведомления отправителя)"""
        rows = self.conn.execute("""
            SELECT t.*, u.name, u.username, u.rating, u.trips_count
            FROM trips t JOIN users u ON t.user_id = u.id
            WHERE t.status = 'active'
              AND LOWER(t.from_city) LIKE LOWER(?)
              AND LOWER(t.to_city)   LIKE LOWER(?)
            ORDER BY u.rating DESC, t.created_at DESC
            LIMIT 5
        """, (f"%{from_city}%", f"%{to_city}%")).fetchall()
        return [dict(r) for r in rows]

    # ── REQUESTS ───────────────────────────────────────────────────────────
    def add_request(self, user_id, from_city, to_city, weight, desc, budget) -> int:
        cur = self.conn.execute(
            "INSERT INTO requests (user_id,from_city,to_city,weight,desc,budget) VALUES (?,?,?,?,?,?)",
            (user_id, from_city, to_city, weight, desc, budget)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_request(self, req_id: int) -> dict:
        row = self.conn.execute("""
            SELECT r.*, u.username, u.name as sender_name
            FROM requests r JOIN users u ON r.user_id = u.id
            WHERE r.id=?
        """, (req_id,)).fetchone()
        return dict(row) if row else None

    def get_user_requests(self, uid: int) -> list:
        rows = self.conn.execute(
            "SELECT * FROM requests WHERE user_id=? ORDER BY created_at DESC LIMIT 10",
            (uid,)
        ).fetchall()
        return [dict(r) for r in rows]

    def find_matches_for_trip(self, from_city: str, to_city: str) -> list:
        """Заявки отправителей по маршруту (для уведомления попутчика)"""
        rows = self.conn.execute("""
            SELECT r.*, u.username, u.name as sender_name
            FROM requests r JOIN users u ON r.user_id = u.id
            WHERE r.status = 'pending'
              AND LOWER(r.from_city) LIKE LOWER(?)
              AND LOWER(r.to_city)   LIKE LOWER(?)
            ORDER BY r.created_at DESC
            LIMIT 5
        """, (f"%{from_city}%", f"%{to_city}%")).fetchall()
        return [dict(r) for r in rows]

    def update_request_status(self, req_id: int, status: str, trip_id: int = None):
        if trip_id is not None:
            self.conn.execute(
                "UPDATE requests SET status=?, trip_id=? WHERE id=?",
                (status, trip_id, req_id)
            )
        else:
            self.conn.execute("UPDATE requests SET status=? WHERE id=?", (status, req_id))
        self.conn.commit()

    # ── REVIEWS ────────────────────────────────────────────────────────────
    def add_review(self, from_user: int, to_user: int, req_id: int, stars: int):
        self.conn.execute(
            "INSERT INTO reviews (from_user,to_user,req_id,stars) VALUES (?,?,?,?)",
            (from_user, to_user, req_id, stars)
        )
        avg = self.conn.execute(
            "SELECT AVG(stars) FROM reviews WHERE to_user=?", (to_user,)
        ).fetchone()[0]
        count = self.conn.execute(
            "SELECT COUNT(*) FROM reviews WHERE to_user=?", (to_user,)
        ).fetchone()[0]
        self.conn.execute(
            "UPDATE users SET rating=?, trips_count=? WHERE id=?",
            (round(avg, 2), count, to_user)
        )
        self.conn.commit()


# Глобальный синглтон
db = Database()
