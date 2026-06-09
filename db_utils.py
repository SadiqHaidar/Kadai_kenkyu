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

    # 【ここを追加！】CSVから読み込んだバーコード列をすべて「文字列型」に一括変換
    df['barcode'] = df['barcode'].astype(str)

    # バーコードが一致する行を探す
    result = df[df['barcode'] == str(barcode)]
    
    if not result.empty:
        return result.iloc[0].to_dict() # 辞書形式で返す
    return None

def save_product(barcode, status, ingredients_en):
    """
    多数決システムによる商品データの保存・更新（重複防止と信頼度ロジック）
    """
    barcode_str = str(barcode)
    
    # 新規登録用の初期投票数を準備
    s_count = 1 if status == "SAFE" else 0
    h_count = 1 if status == "HARAM" else 0
    d_count = 1 if status == "DOUBTFUL" else 0

    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        df['barcode'] = df['barcode'].astype(str)
        
        # すでに同じバーコードが存在する場合（投票・更新処理）
        if barcode_str in df['barcode'].values:
            idx = df[df['barcode'] == barcode_str].index[0]
            
            # 【古いデータ対策】既存の票数を安全に取得（無ければ前バージョンのverified_countから引き継ぐ）
            current_safe = int(df.at[idx, 'safe_count']) if 'safe_count' in df.columns else (int(df.at[idx, 'verified_count']) if 'verified_count' in df.columns and df.at[idx, 'status'] == "SAFE" else 0)
            current_haram = int(df.at[idx, 'haram_count']) if 'haram_count' in df.columns else (int(df.at[idx, 'verified_count']) if 'verified_count' in df.columns and df.at[idx, 'status'] == "HARAM" else 0)
            current_doubt = int(df.at[idx, 'doubtful_count']) if 'doubtful_count' in df.columns else (int(df.at[idx, 'verified_count']) if 'verified_count' in df.columns and df.at[idx, 'status'] == "DOUBTFUL" else 0)
            
            # 今回送られてきた判定に応じて、対応する投票箱を +1 する
            if status == "SAFE":
                current_safe += 1
            elif status == "HARAM":
                current_haram += 1
                df.at[idx, 'ingredients_en'] = ingredients_en # 最新の判定根拠（原材料）に更新
            elif status == "DOUBTFUL":
                current_doubt += 1
                df.at[idx, 'ingredients_en'] = ingredients_en # 最新の判定根拠（原材料）に更新
            
            # 更新した票数をデータフレームに反映
            df.at[idx, 'safe_count'] = current_safe
            df.at[idx, 'haram_count'] = current_haram
            df.at[idx, 'doubtful_count'] = current_doubt
            
            # 【重要】多数決ロジック：一番票数が多いステータスを最終決定にする
            counts_dict = {"SAFE": current_safe, "HARAM": current_haram, "DOUBTFUL": current_doubt}
            final_status = max(counts_dict, key=counts_dict.get)
            
            df.at[idx, 'status'] = final_status
            df_final = df
        else:
            # 完全新規のバーコードなら末尾に行を追加
            new_data = {
                'barcode': [barcode_str],
                'status': [status],
                'ingredients_en': [ingredients_en],
                'safe_count': [s_count],
                'haram_count': [h_count],
                'doubtful_count': [d_count]
            }
            df_new = pd.DataFrame(new_data)
            df_final = pd.concat([df, df_new], ignore_index=True)
    else:
        # CSVファイル自体が存在しない場合は新規作成
        new_data = {
            'barcode': [barcode_str],
            'status': [status],
            'ingredients_en': [ingredients_en],
            'safe_count': [s_count],
            'haram_count': [h_count],
            'doubtful_count': [d_count]
        }
        df_final = pd.DataFrame(new_data)
        
    # 古い列（verified_count）が残っていれば自動削除してCSVを綺麗に保つ
    if 'verified_count' in df_final.columns:
        df_final = df_final.drop(columns=['verified_count'])
        
    df_final.to_csv(DB_FILE, index=False)