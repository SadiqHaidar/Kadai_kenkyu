# db_utils.py
import sqlite3
import os
import base64
import json
import urllib.request
import urllib.error
import streamlit as st
from datetime import datetime

DB_NAME = "halal_database.db"

@st.cache_resource(show_spinner=False)
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

    # 【新規追加】運営による確認結果を、ユーザー投稿(status/ingredients_en)とは
    # 別のカラムで管理する。既に運用中で作られているDBファイルにも安全に
    # カラムを追加できるよう、無ければ追加する形にしている(データは消えない)。
    cursor.execute("PRAGMA table_info(products)")
    existing_columns = [row[1] for row in cursor.fetchall()]

    new_columns = {
        "admin_status": "TEXT",
        "admin_ingredients_en": "TEXT",
        "verified_at": "TEXT",
        "match_keywords": "TEXT"
    }
    for col_name, col_type in new_columns.items():
        if col_name not in existing_columns:
            cursor.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_type}")
            
    conn.commit()
    conn.close()

def push_to_github():
    """新しくなったデータベースファイルを自動でGitHubのkadai_kenkyuブランチに送信(バックアップ)する"""
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["GITHUB_REPO"]
        
        # 1. データベースファイルをバイナリ（Base64）に変換
        with open(DB_NAME, "rb") as f:
            encoded_content = base64.b64encode(f.read()).decode("utf-8")
            
        # ★【修正ポイント】?ref= の後ろを「kadai_kenkyu」に変更
        url = f"https://api.github.com/repos/{repo}/contents/{DB_NAME}?ref=kadai_kenkyu"
        
        # 2. 現在GitHubのkadai_kenkyuブランチ側にある古いファイルの「sha（識別子）」を取得する
        sha = None
        req_get = urllib.request.Request(url)
        req_get.add_header("Authorization", f"token {token}")
        req_get.add_header("Accept", "application/vnd.github.v3+json")
        try:
            with urllib.request.urlopen(req_get) as response:
                data = json.loads(response.read().decode())
                sha = data["sha"]
        except urllib.error.HTTPError as e:
            # 初回など、まだファイルがない場合はshaなしで進む
            if e.code != 404:
                raise e

        # 3. GitHubへ上書きアップロードを実行
        # ★【修正ポイント】"branch" の指定を「kadai_kenkyu」に変更
        payload = {
            "message": "🔄 Auto-updated database from Halal Checker App",
            "content": encoded_content,
            "branch": "kadai_kenkyu"  
        }
        if sha:
            payload["sha"] = sha
            
        upload_url = f"https://api.github.com/repos/{repo}/contents/{DB_NAME}"
        req_put = urllib.request.Request(upload_url, data=json.dumps(payload).encode("utf-8"), method="PUT")
        req_put.add_header("Authorization", f"token {token}")
        req_put.add_header("Content-Type", "application/json")
        
        with urllib.request.urlopen(req_put) as response:
            pass # 成功
            
    except Exception as e:
        st.warning(f"⚠️ Cloud Backup Notice: {e}")

def _calculate_majority_status(safe_count, haram_count, doubtful_count):
    """
    3種類の投稿数(safe_count, haram_count, doubtful_count)から、
    最も票数の多い判定を「多数決の結果」として算出する。

    同数で並んだ場合は、安全側を優先する(HARAM > DOUBTFUL > SAFE の順)。
    これは、判定に迷うくらいなら「食べても大丈夫」と誤って伝えるよりも、
    「注意が必要」と伝える方がリスクが小さい、という考え方に基づく。
    """
    counts = {"HARAM": haram_count, "DOUBTFUL": doubtful_count, "SAFE": safe_count}
    max_count = max(counts.values())
    for candidate in ["HARAM", "DOUBTFUL", "SAFE"]:
        if counts[candidate] == max_count:
            return candidate

def search_product(barcode):
    """バーコード番号でデータベースを検索する"""
    init_db()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT barcode, status, ingredients_en, safe_count, haram_count, doubtful_count,
               admin_status, admin_ingredients_en, verified_at, match_keywords
        FROM products WHERE barcode = ?
    """, (str(barcode),))    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None

    is_verified = row[6] is not None  # admin_statusが入っていれば運営確認済み

    return {
        'barcode': row[0],
        'status': row[1],                     # ユーザー投稿の多数決による判定
        'ingredients_en': row[2],              # ユーザー投稿の原材料テキスト
        'safe_count': row[3], 'haram_count': row[4], 'doubtful_count': row[5],
        'admin_status': row[6],                # 運営確認済みの判定(未確認ならNone)
        'admin_ingredients_en': row[7],        # 運営確認済みの原材料テキスト
        'verified_at': row[8],
        'is_verified': is_verified,
        # 【新規】判定の根拠になった単語(カンマ区切りで保存されているのでリストに変換)
        'matched_keywords': row[9].split(",") if row[9] else [],
        # 【最終的に画面に出すべき値】運営確認済みならそちらを優先し、なければ従来の多数決結果を使う
        'display_status': row[6] if is_verified else row[1],
        'display_ingredients_en': row[7] if is_verified else row[2],
    }

def save_product(barcode, status, ingredients_en, matched_keywords=None):
    """新しい商品をデータベースに保存、または既存なら投稿数を増やし、多数決で最終判定を更新する"""
    init_db()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if matched_keywords is None:
        matched_keywords = []
    
    existing = search_product(barcode)
    
    if existing:
        # 既存の投稿数に、今回の1票を足した「更新後の投稿数」を先に計算する
        new_safe = existing['safe_count'] + (1 if status == "SAFE" else 0)
        new_haram = existing['haram_count'] + (1 if status == "HARAM" else 0)
        new_doubtful = existing['doubtful_count'] + (1 if status == "DOUBTFUL" else 0)

        # 【新規】更新後の投稿数から、多数決で最終的なstatusを算出する
        majority_status = _calculate_majority_status(new_safe, new_haram, new_doubtful)

        combined_keywords = sorted(set(existing['matched_keywords']) | set(matched_keywords))
        keywords_text = ",".join(combined_keywords)

        cursor.execute("""
            UPDATE products
            SET safe_count = ?, haram_count = ?, doubtful_count = ?, status = ?, match_keywords = ?
            WHERE barcode = ?
        """, (new_safe, new_haram, new_doubtful, majority_status, keywords_text, str(barcode)))
    else:
        s_vote = 1 if status == "SAFE" else 0
        h_vote = 1 if status == "HARAM" else 0
        d_vote = 1 if status == "DOUBTFUL" else 0
        keywords_text = ",".join(sorted(set(matched_keywords)))
        # 初回投稿の場合、多数決の結果は「その1票そのもの」になる
        cursor.execute("""
            INSERT INTO products (barcode, status, ingredients_en, safe_count, haram_count, doubtful_count, match_keywords)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (str(barcode), status, ingredients_en, s_vote, h_vote, d_vote, keywords_text))

    conn.commit()
    conn.close()
    
    # 【★ここが最大のポイント】保存が終わったらすぐにGitHubへ送信！
    push_to_github()

def get_doubtful_products():
    """
    運営が確認すべき「DOUBTFUL(疑義あり)かつ、まだ運営未確認」の商品を一覧取得する。
    admin_statusが既に入っている(=確認済み)ものは、再度一覧に出さない。
    """
    init_db()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT barcode, status, ingredients_en, match_keywords
        FROM products
        WHERE status = 'DOUBTFUL' AND admin_status IS NULL
        ORDER BY barcode
    """)
    rows = cursor.fetchall()
    conn.close()

    return [
        {'barcode': r[0], 'status': r[1], 'ingredients_en': r[2], 'matched_keywords': r[3].split(",") if r[3] else []}
        for r in rows
    ]

def get_all_products():
    """
    登録されている全商品を一覧取得する（運営がデータベース全体を確認するための関数）。
    search_product()と同様に、display_status(画面に出すべき最終判定)も計算して返す。
    """
    init_db()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT barcode, status, ingredients_en, safe_count, haram_count, doubtful_count,
               admin_status, admin_ingredients_en, verified_at, match_keywords
        FROM products
        ORDER BY barcode
    """)
    rows = cursor.fetchall()
    conn.close()

    products = []
    for row in rows:
        is_verified = row[6] is not None
        products.append({
            'barcode': row[0],
            'status': row[1],
            'ingredients_en': row[2],
            'safe_count': row[3], 'haram_count': row[4], 'doubtful_count': row[5],
            'admin_status': row[6],
            'admin_ingredients_en': row[7], # 運営が確認した成分情報
            'verified_at': row[8],
            'is_verified': is_verified,
            'display_status': row[6] if is_verified else row[1],
            'display_ingredients_en': row[7] if is_verified else row[2],
            'matched_keywords': row[9].split(",") if row[9] else [],
        })
    return products

def update_product(barcode, status, ingredients_en):
    """
    【運営による手直し用】admin_status / admin_ingredients_en という
    "別のセル"に運営の確認結果を書き込む。
    ユーザー投稿による status / ingredients_en(多数決の記録)は上書きせず、そのまま残す。

    save_product()との違い:
      - save_product()  : ユーザーからの投稿を「多数決の1票」として status/ingredients_en に積み増す
      - update_product(): 運営が調査した結果を admin_status/admin_ingredients_en に別途記録する
    """
    init_db()

    existing = search_product(barcode)
    if not existing:
        # 存在しないバーコードを更新しようとした場合は何もしない
        return False

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE products
        SET admin_status = ?, admin_ingredients_en = ?, verified_at = ?
        WHERE barcode = ?
    """, (status, ingredients_en, datetime.now().strftime("%Y-%m-%d %H:%M"), str(barcode)))
    conn.commit()
    conn.close()

    # 手直し結果もGitHubへ自動バックアップする（既存の仕組みをそのまま利用）
    push_to_github()
    return True