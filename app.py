import streamlit as st
import easyocr
import numpy as np
from PIL import Image
from PIL import ImageOps
import constant as const
import barcode_utils as b_util
import db_utils as d_util
import text_utils as t_util

# ページの設定

st.set_page_config(page_title="Halal Checker", page_icon="🌙")

st.title("🌙 Halal Checker")
st.write("بِسْمِ ٱللّٰهِ ٱلرَّحْمٰنِ ٱلرَّحِيمِ")

tab1, tab2 = st.tabs(["Ingredient Label Analysis", "Barcode Verification"]) # タブの追加: 原材料分析とバーコード検証

# OCRモデルの読み込み（キャッシュして高速化）
@st.cache_resource

def load_ocr():

    return easyocr.Reader(['ja', 'en'], gpu=False) # 日本語と英語をサポート

reader = load_ocr()

with tab1:
    # カメラまたはファイルアップロード

    # img_file = st.camera_input("原材料ラベルを撮影")

    img_file = st.file_uploader("Take a photo or select from folder", key = "text", type=['jpg', 'png', 'jpeg'])



    # 画像が入力されたら処理開始

    if img_file:

        img = Image.open(img_file)

        # 【修正！】スマホ写真の回転情報を補正（文字化け対策に必須）
        img = ImageOps.exif_transpose(img)
        
        # 画面に表示
        st.image(img, caption="Target Image for Analysis", width=400)

        img_array = np.array(img)



        with st.spinner('Analyzing...'):
            # OCR実行
            results = reader.readtext(img_array, detail=0)
            raw_text = "".join(results)

            # 1. まず誤字を直し、原材料セクションを抽出、さらに「牛乳/生乳」を「MILK」に置換
            # text_utils側で一括処理されます
            corrected_text = t_util.clean_text(raw_text)
            full_text = t_util.extract_ingredients(corrected_text)

        st.subheader("🔍 Analysis Results")

        # 2. 判定ロジック
        # すでに full_text 内の「牛乳」は「MILK」になっているため、
        # HARAM_KEYWORDS にある「牛」にはヒットしなくなります
        found_haram_items = [k for k in const.HARAM_KEYWORDS if k in full_text]
        found_doubtful_items = [k for k in const.DOUBTFUL_KEYWORDS if k in full_text]

        st.divider()
        st.subheader("Analysis Results")

        if not found_haram_items and not found_doubtful_items:
            st.success(const.MSG_SAFE)
        else:
            # ハラーム成分の表示
            if found_haram_items:
                st.error(const.MSG_HARAM_TITLE)
                for item in found_haram_items:
                    eng = const.TRANSLATION_MAP.get(item, "Unknown")
                    st.write(f"❌ **{item}** : {eng}")

            # 疑義成分の表示
            if found_doubtful_items:
                st.warning(const.MSG_DOUBTFUL_TITLE)
                for item in found_doubtful_items:
                    eng = const.TRANSLATION_MAP.get(item, "Unknown")
                    st.write(f"⚠️ **{item}** : {eng}")
                st.info(const.MSG_DOUBTFUL_NOTE)

        with st.expander("Check the Full OCR Text"):

            st.write(full_text)



        st.caption("※This judgment is for reference only. Please prioritize checking with the manufacturer or looking for Halal certification marks.")


with tab2:

    barcode_file = st.file_uploader("Take a photo or select from folder", key = "bar", type=['jpg', 'png', 'jpeg'])

    # 読み込まれたらバーコード判定する

    if barcode_file:
        img = Image.open(barcode_file)
        st.image(img, width=300)
        
        # 1. 画像から数字を読み取る
        code_number = b_util.get_barcode_from_image(img)
        
        if code_number:

            st.session_state.last_barcode = code_number
            st.success(f"Barcode Detected: {code_number}")
            
            # 2. データベース(CSV)を検索
            product = d_util.search_product(code_number)
            
            if product:

                st.balloons() # 登録済みならお祝い！

                # すでに登録がある場合
                st.info("Product is registered in the database!")
                st.write(f"Judgment Result: {product['status']}")
                st.write(f"Ingredients: {product['ingredients_en']}")
            else:
                st.warning("This product is not yet registered. Please analyze it in the Ingredient Label Analysis tab.")
        else:
            st.error("Failed to detect barcode. Please take a photo in a well-lit area.")