# db_utils.py
import pandas as pd
import os

DB_FILE = 'halal_database.csv'

def search_product(barcode):
    """
    バーコード番号でデータベースを検索する
    """
    if not os.path.exists(DB_FILE):
        return None
    
    df = pd.read_csv(DB_FILE)
    # バーコードが一致する行を探す
    result = df[df['barcode'] == str(barcode)]
    
    if not result.empty:
        return result.iloc[0].to_dict() # 辞書形式で返す
    return None

def save_product(barcode, status, ingredients_en):
    """
    新しい商品をデータベースに保存する
    """
    new_data = {
        'barcode': [str(barcode)],
        'status': [status],
        'ingredients_en': [ingredients_en],
        'verified_count': [1] # 最初は1人
    }
    df_new = pd.DataFrame(new_data)
    
    if os.path.exists(DB_FILE):
        df_old = pd.read_csv(DB_FILE)
        df_final = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_final = df_new
        
    df_final.to_csv(DB_FILE, index=False)