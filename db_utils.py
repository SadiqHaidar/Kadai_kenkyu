# db_utils.py
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# 【重要】作成したGoogleスプレッドシートのURLをここに貼り付けてください
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/18d_X1luGRnyGf2Ga9Cnhj5dtdSx0ne1HFqeqDvUQqms/edit?gid=0#gid=0"

def get_connection():
    """Streamlitの機能を使ってGoogle Sheetsへの接続を確立する"""
    return st.connection("gsheets", type=GSheetsConnection)

def search_product(barcode):
    """
    バーコード番号でGoogleスプレッドシートを検索する
    """
    try:
        conn = get_connection()
        # スプレッドシートのデータを読み込み（キャッシュを0にして常に最新データを取得）
        df = conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
        
        if df.empty or 'barcode' not in df.columns:
            return None

        # バーコード列をすべて「文字列型」に変換して比較しやすくする
        df['barcode'] = df['barcode'].astype(str)
        
        # バーコードが一致する行を探す
        result = df[df['barcode'] == str(barcode)]
        
        if not result.empty:
            return result.iloc[0].to_dict() # 辞書形式で返す
        return None
    except Exception as e:
        st.error(f"Database Search Error: {e}")
        return None

def save_product(barcode, status, ingredients_en):
    """
    新しい商品をGoogleスプレッドシートに保存する
    """
    try:
        conn = get_connection()
        # 現在のスプレッドシートの内容を取得
        df_old = conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
        
        # 新しいデータの作成
        new_data = {
            'barcode': [str(barcode)],
            'status': [status],
            'ingredients_en': [ingredients_en],
            'verified_count': [1]
        }
        df_new = pd.DataFrame(new_data)
        
        # 既存データがある場合は結合、ない場合は新規作成
        if not df_old.empty:
            # 既存のバーコード列も文字列にしておく
            df_old['barcode'] = df_old['barcode'].astype(str)
            df_final = pd.concat([df_old, df_new], ignore_index=True)
        else:
            df_final = df_new
            
        # Googleスプレッドシートを上書き更新
        conn.update(spreadsheet=SPREADSHEET_URL, data=df_final)
        
    except Exception as e:
        st.error(f"Database Save Error: {e}")