import streamlit as st
import easyocr
import numpy as np
import pandas as pd 
from PIL import Image
from PIL import ImageOps
import constant as const
import barcode_utils as b_util
import db_utils as d_util
import text_utils as t_util
from streamlit_cropper import st_cropper

def main():

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
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False
    if "rotation_angle" not in st.session_state:
        st.session_state.rotation_angle = 0
    if "uploaded_file_key" not in st.session_state:
        st.session_state.uploaded_file_key = None

    st.set_page_config(
        page_title="Halal Checker", 
        page_icon="Halal.png"  # 👈 ここに用意した画像ファイル名を書くだけ！
    )

    st.title("🌙 Halal Checker")
    st.write("بِسْمِ ٱللّٰهِ ٱلرَّحْمٰنِ ٱلرَّحِيمِ")

    tab1, tab2, tab3 = st.tabs(["Ingredient Label Analysis", "Barcode Verification", "⚙️ Admin"]) # タブの追加: 原材料分析・バーコード検証・運営用の手直し

    # 【改善①】OCRモデルの読み込みを「関数定義」だけに留め、ここではまだ呼び出さない。
    # こうすることでタブの描画（画面表示）がブロックされなくなる。
    # 実際の読み込みは「Analyzeボタンが押された瞬間」まで遅延させる。
    @st.cache_resource(show_spinner="🔍 Preparing OCR engine (first time only, please wait)...")
    def load_ocr():
        return easyocr.Reader(['ja', 'en'], gpu=False) # 日本語と英語をサポート

    with tab1: # タブ1: 原材料分析
        # カメラまたはファイルアップロード

        # img_file = st.camera_input("原材料ラベルを撮影")

        img_file = st.file_uploader("Take a photo or select from folder", key = "text", type=['jpg', 'png', 'jpeg'])



        # 画像が入力されたら処理開始

        if img_file:

            img = Image.open(img_file)

            # 【修正！】スマホ写真の回転情報を補正（文字化け対策に必須）
            img = ImageOps.exif_transpose(img)
            
            # 【改善】OCR用に、元画像の解像度をなるべく保った「高解像度版」を別途用意する。
            # img_full はクロップ操作の見た目には使わず、最終的な文字認識にだけ使う。
            img_full = img.copy()
            img_full.thumbnail((1600, 1600))
    
            # こちらの img は「画面表示・クロップ操作専用」。
            # スマホの画面幅を確実に超えないよう、控えめなサイズに抑える。
            img.thumbnail((500, 500))

            # 【新機能】新しい画像がアップロードされたら、回転角度を0度にリセットする。
            # img_file.name + img_file.size を「その画像を識別するキー」として使い、
            # 前回アップロードした画像と違うファイルなら「新しい画像だ」と判断する。
            current_file_key = f"{img_file.name}_{img_file.size}"
            if st.session_state.uploaded_file_key != current_file_key:
                st.session_state.uploaded_file_key = current_file_key
                st.session_state.rotation_angle = 0

            # 保存されている角度ぶん、実際に画像を回転させる(表示用・OCR用の両方に同じ角度をかける)。
            # expand=True は「回転後にはみ出た部分を切り取らず、画像全体のサイズを広げて収める」設定。
            if st.session_state.rotation_angle != 0:
                img = img.rotate(st.session_state.rotation_angle, expand=True)
                img_full = img_full.rotate(st.session_state.rotation_angle, expand=True)

            # ✨【さらに追加！】小さくした画像を、スマホの画面幅にぴったりフィットさせて表示する
            st.image(img, caption="Uploaded Image", use_container_width=True)

            # --- 手動トリミング機能 ---
            st.subheader("✂️ Step 1: Crop Ingredients Area")
            st.info("Please specify the range so that the ""Ingredients"" (原材料名)section fits within it.")

            # 【改善】ここで使う img は表示・操作専用の小さい画像(最大500px)。
            # return_type='both' にすることで、「見た目用に切り抜かれた画像」に加えて
            # 「枠の座標(left, top, width, height)」も受け取れるようにする。
            cropped_img_preview, box = st_cropper(
                img,
                realtime_update=True,
                box_color='#00FF00',
                aspect_ratio=None,
                should_resize_image=True,
                return_type='both'
            )

             # 【新機能】手動回転ボタン
            st.write("Please rotate the image if needed:")
            rot_col1, rot_col2, rot_col3 = st.columns(3)
            with rot_col1:
                if st.button("⟲ turn left 90°"):
                    st.session_state.rotation_angle = (st.session_state.rotation_angle + 90) % 360
                    st.rerun()
            with rot_col2:
                if st.button("⟳ turn right 90°"):
                    st.session_state.rotation_angle = (st.session_state.rotation_angle - 90) % 360
                    st.rerun()
            with rot_col3:
                if st.button("↺ Reset"):
                    st.session_state.rotation_angle = 0
                    st.rerun()

            # 【改善】表示用画像(img)と高解像度画像(img_full)の縮小率の違いを計算し、
            # 枠の座標を高解像度画像用の座標に変換する。
            scale_x = img_full.width / img.width
            scale_y = img_full.height / img.height
            crop_left = int(box['left'] * scale_x)
            crop_top = int(box['top'] * scale_y)
            crop_right = crop_left + int(box['width'] * scale_x)
            crop_bottom = crop_top + int(box['height'] * scale_y)

            # 高解像度画像から、変換後の座標で切り抜く。これがOCRに渡される。
            cropped_img = img_full.crop((crop_left, crop_top, crop_right, crop_bottom))

            st.write("Target area:")
            st.image(cropped_img, width=300)

            if st.button("🔍 Analyze This Area"):
                with st.spinner('Analyzing...'):
                    # 【改善①つづき】ここで初めてOCRモデルを取得。
                    # 2回目以降はcache_resourceにより一瞬でロードされる。
                    reader = load_ocr()
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
                        
                    # 【修正ポイント】フォームを使って、ボタンを押したときに写真データが消えるのを防ぎます
                    with st.form(key="register_form"):
                        st.write("Click the button below to complete the registration.")
                        submit_button = st.form_submit_button(label=f"Register as Barcode {detected_code}")

                        # 保存実行
                        if submit_button:
                            d_util.save_product(
                                barcode = detected_code,
                                status = st.session_state.temp_status, # 前のステップで保存した判定結果
                                ingredients_en = st.session_state.temp_ingredients, # 解析した原材料
                                matched_keywords = st.session_state.found_haram + st.session_state.found_doubtful
                            )
                            st.success("Registration Complete!")
                            st.balloons() # お祝いの演出
                else:
                    st.error("Could not find a barcode. Please try again or clear the photo.")


    with tab2: # タブ2: バーコード検証

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

                    if product['is_verified']:
                        st.success(f"✅ Verified by the operating team ({product['verified_at']})")
                    else:
                        st.caption("ℹ️ This result is based on community submissions and has not been verified by the operating team yet.")

                    st.write(f"Judgment Result: {product['display_status']}")
                    st.write(f"Ingredients: {product['display_ingredients_en']}")
                else:
                    st.warning("This product is not yet registered. Please analyze it in the Ingredient Label Analysis tab.")
            else:
                st.error("Failed to detect barcode. Please take a photo in a well-lit area.")

    with tab3: # タブ3: 運営による疑義判定の手直し
        st.subheader("⚙️ Admin: Review & Correct Doubtful Products")

        # --- 認証パート ---
        # st.secrets["ADMIN_PASSWORD"] は Streamlit CloudのSecrets設定画面で登録する。
        # コードにもリポジトリにもパスワードそのものは書き込まれない。
        if not st.session_state.is_admin:
            st.info("This section is for the operating team only.")
            input_pw = st.text_input("Admin Password", type="password")
            if st.button("Login"):
                correct_pw = st.secrets.get("ADMIN_PASSWORD", None)
                if correct_pw and input_pw == correct_pw:
                    st.session_state.is_admin = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")
        else:
            col_a, col_b = st.columns([5, 1])
            with col_a:
                st.success("✅ Logged in as Admin")
            with col_b:
                if st.button("Logout"):
                    st.session_state.is_admin = False
                    st.rerun()

            st.divider()

            # --- データベース全体の一覧表示 ---
            st.write("### 🗂️ Full Product Database")
            all_products = d_util.get_all_products()

            if all_products:
                # 判定結果でフィルタできるようにする
                filter_choice = st.selectbox(
                    "Filter by judgment",
                    ["All", "SAFE", "DOUBTFUL", "HARAM"],
                    key="admin_db_filter"
                )
                if filter_choice != "All":
                    filtered = [p for p in all_products if p['display_status'] == filter_choice]
                else:
                    filtered = all_products

                st.caption(f"{len(filtered)} of {len(all_products)} products shown.")

                # 表形式で見やすく表示するため、pandasのDataFrameに変換する
                table_rows = [
                    {
                        "Barcode": p['barcode'],
                        "Judgment": p['display_status'],
                        "Verified": "✅" if p['is_verified'] else "—",
                        "Community Votes (S/D/H)": f"{p['safe_count']}/{p['doubtful_count']}/{p['haram_count']}",
                        "Verified At": p['verified_at'] or "",
                        "Ingredients": p['ingredients_en']
                    }
                    for p in filtered
                ]
                df = pd.DataFrame(table_rows)
                st.dataframe(df, use_container_width=True, hide_index=True, column_config={"Ingredients": st.column_config.TextColumn(width="large")})
            else:
                st.write("No products registered yet.")

            st.divider()

            # --- 確認待ちの一覧表示 ---
            st.write("### 📋 Products Needing Review (DOUBTFUL)")
            doubtful_list = d_util.get_doubtful_products()
            if doubtful_list:
                st.caption("Click a product to load it into the correction form below.")
                for item in doubtful_list:
                    preview = item['ingredients_en'][:60] + ("..." if len(item['ingredients_en']) > 60 else "")
                    # ボタンを押すと、そのバーコードをsession_stateに保存 → 下の検索欄に自動反映される
                    if st.button(f"🔍 {item['barcode']} : {preview}", key=f"select_{item['barcode']}"):
                        st.session_state.admin_barcode_input = item['barcode']
                        st.rerun()
            else:
                st.write("No doubtful products pending review. 🎉")

            st.divider()

            # --- 個別バーコードの手直しフォーム ---
            st.write("### 🔧 Correct a Product's Judgment")
            target_barcode = st.text_input("Enter barcode to correct", key="admin_barcode_input")

            if target_barcode:
                product = d_util.search_product(target_barcode)
                if product:
                    st.write(f"📥 Community-reported judgment: **{product['status']}**")
                    if product['is_verified']:
                        st.write(f"✅ Already verified by admin on {product['verified_at']}: **{product['admin_status']}**")
                    else:
                        st.write("🕗 Not yet verified by admin.")

                    status_options = ["SAFE", "DOUBTFUL", "HARAM"]
                    # フォームの初期値は、運営確認済みならその値、なければユーザー投稿の値を使う
                    prefill_status = product['display_status']
                    prefill_ingredients = product['display_ingredients_en']
                    current_index = status_options.index(prefill_status) if prefill_status in status_options else 0

                    with st.form(key="admin_correction_form"):
                        new_status = st.selectbox("Verified Judgment", status_options, index=current_index)
                        new_ingredients = st.text_area("Verified Ingredients Text", value=prefill_ingredients)
                        save_correction = st.form_submit_button("💾 Save Verification")

                        if save_correction:
                            d_util.update_product(target_barcode, new_status, new_ingredients)
                            st.success("Verification saved successfully!")
                            st.rerun()
                else:
                    st.warning("No product found with this barcode.")

if __name__ == "__main__":
    main()