import sqlite3

def insert_test_data(user_id):
    conn = sqlite3.connect('game_history.db')
    c = conn.cursor()
    
    # テーブルの作成
    c.execute('''
    CREATE TABLE IF NOT EXISTS game_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        game_name TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        duration INTEGER
    )
    ''')
    
    # テストデータ
    test_data = [
        # 月曜日の23:30から火曜日の1:30まで
        (user_id, 'Minecraft', '2025-02-03T23:30:00.000000', '2025-02-04T01:30:00.000000', 7200),
    ]
    
    # データの挿入
    c.executemany('''
    INSERT INTO game_sessions (user_id, game_name, start_time, end_time, duration)
    VALUES (?, ?, ?, ?, ?)
    ''', test_data)
    
    conn.commit()
    conn.close()
    
    print("テストデータを挿入しました。")

if __name__ == "__main__":
    # あなたのユーザーIDを指定して実行
    insert_test_data("your_user_id")