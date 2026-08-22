import sqlite3
from config import DB_NAME
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS meetings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        place TEXT NOT NULL,
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS invites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_id INTEGER NOT NULL,
        inviter_id INTEGER NOT NULL,
        invitee_id INTEGER NOT NULL,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT,
        username TEXT,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_admin INTEGER DEFAULT 0
    )""")
    cur.execute("PRAGMA table_info(users)")
    columns = [info[1] for info in cur.fetchall()]
    if 'is_admin' not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
    if 'city' not in columns:   # отдельная проверка для city
        cur.execute("ALTER TABLE users ADD COLUMN city TEXT DEFAULT '0'")
    conn.commit()
    conn.close()

def save_meeting(chat_id, user_id, date, time, place, comment):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO meetings (chat_id, user_id, date, time, place, comment)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (chat_id, user_id, date, time, place, comment))
    conn.commit()
    meeting_id = cur.lastrowid
    conn.close()
    return meeting_id

def get_all_meetings(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT meeting_id FROM invites WHERE invitee_id=?", (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_meeting_info(meeting_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT id,date,time,place,comment,created_at FROM meetings WHERE id=? ORDER BY created_at DESC",
        (meeting_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def AddInvite(meeting_id, inviter_id, invitee_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO invites(meeting_id, inviter_id, invitee_id) VALUES (?, ?, ?)",
        (meeting_id, inviter_id, invitee_id)
    )
    conn.commit()
    conn.close()

def get_status(meeting_id, user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT status FROM invites WHERE meeting_id=? AND invitee_id=?", (meeting_id, user_id))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def update_status(meeting_id, user_id, status):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "UPDATE invites SET status=? WHERE meeting_id = ? AND invitee_id = ?",
        (status, meeting_id, user_id)
    )
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT first_name, username, user_id FROM users")
    rows = cur.fetchall()
    conn.close()
    return rows

def get_all_status(meeting_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT invitee_id FROM invites WHERE meeting_id = ? and status='accepted'", (meeting_id,))
    accept = cur.fetchall()
    cur.execute("SELECT invitee_id FROM invites WHERE meeting_id = ? and status='pending'", (meeting_id,))
    pend = cur.fetchall()
    cur.execute("SELECT invitee_id FROM invites WHERE meeting_id = ? and status='declined'", (meeting_id,))
    decline = cur.fetchall()
    conn.close()
    return [accept, pend, decline]

def get_name_from_user_id(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT first_name, username FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return row[0], row[1]
    return None, None

def get_inviter_from_invitee(user_id, meeting_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT inviter_id FROM invites WHERE invitee_id = ? and meeting_id = ?",
        (user_id, meeting_id)
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def delete_meeting(meeting_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
    conn.commit()
    conn.close()

def delete_invite(meeting_id, invitee_id):
    """Удаляет приглашение пользователя на встречу"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM invites WHERE meeting_id = ? AND invitee_id = ?",
        (meeting_id, invitee_id)
    )
    conn.commit()
    conn.close()

def change_mind(user_id, meeting_id, status):
    """Меняет статус пользователя на противоположный"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if status == "accepted":
        cur.execute(
            "UPDATE invites SET status=? WHERE meeting_id = ? AND invitee_id = ?",
            ("declined", meeting_id, user_id)
        )
    elif status == "declined":
        cur.execute(
            "UPDATE invites SET status=? WHERE meeting_id = ? AND invitee_id = ?",
            ("accepted", meeting_id, user_id)
        )
    conn.commit()
    conn.close()

def check_admin(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT is_admin FROM users WHERE user_id=?", (user_id,))
    answ = cur.fetchone()
    conn.close()
    if answ is None:
        return False
    return answ[0] == 1

def give_or_revoke_admin(user_id, status):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_admin=? WHERE user_id=?", (status, user_id))
    conn.commit()
    conn.close()

def admin_list():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE is_admin=1")
    rows = cur.fetchall()
    conn.close()
    return rows

def user_exists(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None

def delete_user(user_id):
    """
    Удаляет пользователя из таблицы users,
    а также удаляет все его приглашения из invites.
    """
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM invites WHERE invitee_id = ?", (user_id,))
    cur.execute("DELETE FROM invites WHERE inviter_id = ?", (user_id,))
    cur.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_city(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT city FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def update_city(user_id, city):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE users SET city=? WHERE user_id=?", (city, user_id))
    conn.commit()   # исправлено: добавлены скобки
    conn.close()
