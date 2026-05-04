# barcode_utils.py
from pyzbar.pyzbar import decode
import numpy as np

def get_barcode_from_image(image):
    """
    画像からバーコード番号を抽出する関数
    """
    # Streamlitの画像(PIL)をNumPy配列に変換
    image_np = np.array(image)
    
    # バーコードをデコード
    detected_objects = decode(image_np)
    
    if detected_objects:
        # 最初に見つかったバーコードの数字を返す
        return detected_objects[0].data.decode('utf-8')
    
    return None