"""
テスト用DBシードスクリプト
使い方: python3 scripts/seed_test_data.py
"""
import sqlite3
from datetime import datetime, timedelta
import random

DB_PATH = 'game_history.db'

# テスト用ユーザーID（実際のDiscordユーザーIDに変更してください）
# Developer Modeを有効にして、ユーザーを右クリック→「IDをコピー」
TEST_USERS = {
    'user_a': 'YOUR_USER_ID_HERE',        # 自分のID
    'user_b': 'FRIEND_USER_ID_HERE',       # テスト用の別アカウントのID
}

GAMES = ['Apex Legends', 'Valorant', 'Minecraft', 'osu!', 'League of Legends']

def init_db(conn):
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT, user_name TEXT, game_name TEXT,
            start_time TEXT, end_time TEXT, duration INTEGER, details TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS voice_co_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id_a TEXT, user_id_b TEXT, channel_id TEXT, channel_name TEXT,
            game_name_a TEXT, game_name_b TEXT,
            start_time TEXT, end_time TEXT, duration INTEGER
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS party_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            party_id TEXT, user_id TEXT, game_name TEXT,
            party_size_current INTEGER, party_size_max INTEGER,
            joined_at TEXT, left_at TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS mention_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user_id TEXT, to_user_id TEXT, channel_id TEXT, timestamp TEXT
        )
    ''')
    conn.commit()

def seed_game_sessions(conn):
    """過去14日間のゲームセッションをランダム生成"""
    c = conn.cursor()
    now = datetime.now()
    records = []

    for user_key, user_id in TEST_USERS.items():
        if 'YOUR' in user_id or 'FRIEND' in user_id:
            continue
        for i in range(20):  # 各ユーザー20セッション
            game = random.choice(GAMES)
            # 過去14日のランダムな時刻
            start = now - timedelta(
                days=random.randint(0, 13),
                hours=random.randint(18, 23),
                minutes=random.randint(0, 59)
            )
            dur_min = random.randint(30, 180)  # 30〜180分
            end = start + timedelta(minutes=dur_min)
            records.append((
                user_id, user_key, game,
                start.isoformat(), end.isoformat(),
                dur_min * 60, None
            ))

    c.executemany('''
        INSERT INTO game_sessions
        (user_id, user_name, game_name, start_time, end_time, duration, details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', records)
    conn.commit()
    print(f"✅ game_sessions: {len(records)}件のテストデータを挿入しました")

def seed_vc_sessions(conn):
    """VCの共同参加テストデータ"""
    ids = list(TEST_USERS.values())
    if any('YOUR' in i or 'FRIEND' in i for i in ids):
        print("⚠️ USER IDが設定されていないためVC共同セッションをスキップします")
        return
    c = conn.cursor()
    now = datetime.now()
    for i in range(5):
        start = now - timedelta(days=i+1, hours=2)
        dur = random.randint(1800, 7200)  # 30〜120分
        end = start + timedelta(seconds=dur)
        c.execute('''
            INSERT INTO voice_co_sessions
            (user_id_a, user_id_b, channel_id, channel_name,
             game_name_a, game_name_b, start_time, end_time, duration)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            min(ids), max(ids),
            '000000000000000001', 'テストVC',
            random.choice(GAMES), random.choice(GAMES),
            start.isoformat(), end.isoformat(), dur
        ))
    conn.commit()
    print("✅ voice_co_sessions: 5件のテストデータを挿入しました")

if __name__ == '__main__':
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    seed_game_sessions(conn)
    seed_vc_sessions(conn)
    conn.close()
    print("\n🎮 テストデータの準備完了！")
    print("次のステップ: python3 main.py でBotを起動してください")
