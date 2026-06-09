import streamlit as st
import easyocr
import numpy as np
from PIL import Image
from PIL import ImageOps
import constant as const
import barcode_utils as b_util
import db_utils as d_util
import text_utils as t_util
from streamlit_cropper import st_cropper


# --- 1. Session Stateの初期化 (エラー回避のために必須) ---
# アプリ起動時に「箱」を空の状態で用意しておきます
if "temp_status" not in st.session_state:
    st.session_state.temp_status = None
if "temp_ingredients" not in st.session_state:
    st.session_state.temp_ingredients = ""
if "found_haram" not in st.session_state:
    st.session_state.found_haram = []
if "found_doubtful" not in st.session_state:
    st.session_state.found_doubtful = []

st.set_page_config(
    page_title="Halal Checker", 
    page_icon="Halal.png"  # 👈 ここに用意した画像ファイル名を書くだけ！
)

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
        
        # --- 手動トリミング機能 ---
        st.subheader("✂️ Step 1: Crop Ingredients Area")
        st.info("原材料名の枠が収まるように、マウスで範囲を指定してください。")
        
        # 自由な比率で切り抜き
        cropped_img = st_cropper(img, realtime_update=True, box_color='#00FF00', aspect_ratio=None)
        
        st.write("Target area:")
        st.image(cropped_img, width=300)

        img_array = np.array(cropped_img)

        if st.button("🔍 Analyze This Area"):
            with st.spinner('Analyzing...'):
                img_array = np.array(cropped_img)
                results = reader.readtext(img_array, detail=0)
                raw_text = " ".join(results) # 文字がくっつかないようスペース結合

                # テキストの修正と抽出
                corrected_text = t_util.clean_text(raw_text)
                full_text = t_util.extract_ingredients(corrected_text)

                # 判定ロジック (text_utilsで牛乳・生乳はすでに「MILK」に置換済)
                found_haram = [k for k in const.HARAM_KEYWORDS if k in full_text]
                found_doubtful = [k for k in const.DOUBTFUL_KEYWORDS if k in full_text]

                # 【重要】結果をセッションに代入（これでリロードされても消えません）
                st.session_state.temp_ingredients = full_text
                st.session_state.found_haram = found_haram
                st.session_state.found_doubtful = found_doubtful
                
                if found_haram:
                    st.session_state.temp_status = "HARAM"
                elif found_doubtful:
                    st.session_state.temp_status = "DOUBTFUL"
                else:
                    st.session_state.temp_status = "SAFE"

        # --- 判定結果の表示エリア (セッションにデータがあれば常に表示) ---
        if st.session_state.temp_status is not None:
            st.divider()
            st.subheader("🔍 Analysis Results")

            if st.session_state.temp_status == "SAFE":
                st.success(const.MSG_SAFE)
            else:
                if st.session_state.found_haram:
                    st.error(const.MSG_HARAM_TITLE)
                    for item in st.session_state.found_haram:
                        eng = const.TRANSLATION_MAP.get(item, "Unknown")
                        st.write(f"❌ **{item}** : {eng}")

                if st.session_state.found_doubtful:
                    st.warning(const.MSG_DOUBTFUL_TITLE)
                    for item in st.session_state.found_doubtful:
                        eng = const.TRANSLATION_MAP.get(item, "Unknown")
                        st.write(f"⚠️ **{item}** : {eng}")
                    st.info(const.MSG_DOUBTFUL_NOTE)

            with st.expander("Check the Full OCR Text"):
                st.write(st.session_state.temp_ingredients)

        st.caption("※This judgment is for reference only. Please prioritize checking with the manufacturer or looking for Halal certification marks.")

        st.divider()
        st.subheader("💾 Save to Database")
        st.write("To help other users, please take a photo of the product's barcode.")
            
        # 保存用にバーコード写真をアップロード（またはカメラ起動）
        save_barcode_file = st.file_uploader("Take a photo of the Barcode", key="save_bar", type=['jpg', 'png', 'jpeg'])

        if save_barcode_file:
            bar_img = Image.open(save_barcode_file)
            st.image(bar_img, caption="Scanning barcode...", width=200)
            
            # 画像からJANコードを自動取得
            detected_code = b_util.get_barcode_from_image(bar_img)
                
            if detected_code:
                st.success(f"Barcode Detected: {detected_code}")
                    
                # 保存実行
                if st.button(f"Register as Barcode {detected_code}"):
                    d_util.save_product(
                        barcode=detected_code,
                        status=st.session_state.temp_status, # 前のステップで保存した判定結果
                        ingredients_en=st.session_state.temp_ingredients # 解析した原材料
                    )
                    st.success("Registration Complete!")
                    st.balloons()
            else:
                st.error("Could not find a barcode. Please try again or clear the photo.")


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

                # すでに登録がある場合
                st.info("Product is registered in the database!")
                st.write(f"Judgment Result: {product['status']}")
                st.write(f"Ingredients: {product['ingredients_en']}")
            else:
                st.warning("This product is not yet registered. Please analyze it in the Ingredient Label Analysis tab.")
        else:
            st.error("Failed to detect barcode. Please take a photo in a well-lit area.")