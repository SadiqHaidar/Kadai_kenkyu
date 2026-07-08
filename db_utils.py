# db_utils.py
import sqlite3
import os
import base64
import json
import urllib.request
import urllib.error
import streamlit as st

DB_NAME = "halal_database.db"

def init_db():
    """データベースファイルとテーブルを自動で作成する"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            barcode TEXT PRIMARY KEY,
            status TEXT,
            ingredients_en TEXT,
            safe_count INTEGER DEFAULT 0,
            haram_count INTEGER DEFAULT 0,
            doubtful_count INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def push_to_github():
    """新しくなったデータベースファイルを自動でGitHubに送信（バックアップ）する"""
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["GITHUB_REPO"]
        
        # 1. データベースファイルをバイナリ（Base64）に変換
        with open(DB_NAME, "rb") as f:
            encoded_content = base64.b64encode(f.read()).decode("utf-8")
            
        url = f"https://api.github.com/repos/{repo}/contents/{DB_NAME}"
        
        # 2. 現在GitHub側にある古いファイルの「sha（識別子）」を取得する（上書きに必須）
        sha = None
        req_get = urllib.request.Request(url)
        req_get.add_header("Authorization", f"token {token}")
        req_get.add_header("Accept", "application/vnd.github.v3+json")
        try:
            with urllib.request.urlopen(req_get) as response:
                data = json.loads(response.read().decode())
                sha = data["sha"]
        except urllib.error.HTTPError as e:
            # 初回など、GitHub側にまだファイルがない場合はshaなしで進む
            if e.code != 404:
                raise e

        # 3. GitHubへ上書きアップロードを実行
        payload = {
            "message": "🔄 Auto-updated database from Halal Checker App",
            "content": encoded_content
        }
        if sha:
            payload["sha"] = sha
            
        req_put = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="PUT")
        req_put.add_header("Authorization", f"token {token}")
        req_put.add_header("Content-Type", "application/json")
        
        with urllib.request.urlopen(req_put) as response:
            pass # 成功
            
    except Exception as e:
        st.warning(f"⚠️ Cloud Backup Notice: {e}")

def search_product(barcode):
    """バーコード番号でデータベースを検索する"""
    init_db()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT barcode, status, ingredients_en, safe_count, haram_count, doubtful_count FROM products WHERE barcode = ?", (str(barcode),))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'barcode': row[0], 'status': row[1], 'ingredients_en': row[2],
            'safe_count': row[3], 'haram_count': row[4], 'doubtful_count': row[5]
        }
    return None

def save_product(barcode, status, ingredients_en):
    """新しい商品をデータベースに保存、または既存なら多数決のカウントを増やす"""
    init_db()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    existing = search_product(barcode)
    
    if existing:
        if status == "SAFE":
            cursor.execute("UPDATE products SET safe_count = safe_count + 1 WHERE barcode = ?", (str(barcode),))
        elif status == "HARAM":
            cursor.execute("UPDATE products SET haram_count = haram_count + 1 WHERE barcode = ?", (str(barcode),))
        else:
            cursor.execute("UPDATE products SET doubtful_count = doubtful_count + 1 WHERE barcode = ?", (str(barcode),))
    else:
        s_vote = 1 if status == "SAFE" else 0
        h_vote = 1 if status == "HARAM" else 0
        d_vote = 1 if status == "DOUBTFUL" else 0
        cursor.execute("""
            INSERT INTO products (barcode, status, ingredients_en, safe_count, haram_count, doubtful_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (str(barcode), status, ingredients_en, s_vote, h_vote, d_vote))
        
    conn.commit()
    conn.close()
    
    # 【★ここが最大のポイント】保存が終わったらすぐにGitHubへ送信！
    push_to_github()