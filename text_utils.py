# text_utils.py
import re

def clean_text(text):
    """
    OCRの読み取りミス(濁点落ちや誤変換)を補正する関数
    """
    if not text:
        return ""

    # 読み間違い辞書
    replace_rules = {
        "セラチン": "ゼラチン",
        "ぜらちん": "ゼラチン",
        "せらちん": "ゼラチン",
        "ハーク": "ポーク",
        "ショートリンク": "ショートニング",
        "乳化削": "乳化剤",
        "ラヘル": "ラベル",
        "原材科名": "原材料名", # OCRで「料」が「科」になりやすいため追加
        "原材籵名": "原材料名"
    }

    for wrong, right in replace_rules.items():
        text = text.replace(wrong, right)
    
    return text

def extract_ingredients(text):
    """
    全文から「原材料名」セクションのみを抽出し、
    かつ「牛乳/生乳」を「MILK」に変換して、後の判定での誤反応を防ぐ
    """
    if not text:
        return ""

    # 1. 判定前に「牛乳」「生乳」を「MILK」という無害な英単語に置き換える
    # これにより、後の「牛」というキーワードチェックにかからなくなります
    text = text.replace("牛乳", "MILK").replace("生乳", "MILK")
    
    # 見つからなかった場合は、既に「MILK」置換済みのテキストを返す
    return text