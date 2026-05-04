# constants.py

# 翻訳対応表（日本語: 英語）
TRANSLATION_MAP = {
    # HARAM_KEYWORDS
    "豚": "Pork",
    "ポーク": "Pork",
    "ラード": "Lard",
    "ゼラチン": "Gelatin",
    "酒": "Sake / Alcohol",
    "みりん": "Mirin (Sweet Cooking Rice Wine)",
    "酒精": "Ethyl Alcohol",
    "アルコール": "Alcohol",
    "牛": "Beef",
    "ビーフ": "Beef",
    "羊": "Mutton / Lamb",
    "ラム": "Lamb",
    "鶏": "Chicken",
    "チキン": "Chicken",
    
    # DOUBTFUL_KEYWORDS
    "アミノ酸": "Amino Acids (Possible animal origin)",
    "ショートニング": "Shortening (Possible animal origin)",
    "マーガリン": "Margarine (Possible animal origin)",
    "乳化剤": "Emulsifier (Possible animal origin)"
}

# 判定用キーワードリスト
HARAM_KEYWORDS = ["豚", "ポーク", "ラード", "ゼラチン", "酒", "みりん", "酒精", "アルコール", "牛", "羊", "鶏", "チキン", "ビーフ", "ラム"]
DOUBTFUL_KEYWORDS = ["アミノ酸", "ショートニング", "マーガリン", "乳化剤"]

# 英語メッセージ
MSG_SAFE = "✅ No restricted ingredients detected."
MSG_HARAM_TITLE = "⚠️ HARAM Ingredients Found!"
MSG_DOUBTFUL_TITLE = "❓ DOUBTFUL Ingredients Found (Mushbooh)"
MSG_DOUBTFUL_NOTE = "Note: These ingredients may be plant-based or animal-based. Please check for a Halal certificate."