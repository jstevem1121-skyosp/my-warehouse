import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import re
from datetime import datetime

# 구글 시트 URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"

@st.cache_resource
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = dict(st.secrets["gcp_service_account"])
    pk = creds_info["private_key"]
    if "-----BEGIN PRIVATE KEY-----" in pk:
        content = pk.replace("-----BEGIN PRIVATE KEY-----", "").replace("-----END PRIVATE KEY-----", "")
        clean_content = re.sub(r"\s+", "", content) 
        lines = [clean_content[i:i+64] for i in range(0, len(clean_content), 64)]
        pk = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END PRIVATE KEY-----\n"
    creds_info["private_key"] = pk
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(creds)

# 데이터 업데이트 및 로그 기록 함수
def update_item_info(main_sheet, log_sheet, row_idx, item_name, col_name, new_value, df_columns):
    try:
        col_idx = list(df_columns).index(col_name) + 1
        main_sheet.update_cell(row_idx + 2, col_idx, new_value)
        
        # 로그 기록
        if log_sheet:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_sheet.append_row([now, item_name, f"{col_name} 변경", str(new_value)])
        
        st.toast(f"✅ {item_name}의 {col_name}이(가) 변경되었습니다!")
        st.rerun()
    except Exception as e:
        st.error(f"오류 발생: {e}")

# 수량 증감 함수
def update_stock(main_sheet, log_sheet, row_idx, item_name, current_qty, change, qty_col_idx):
    new_qty = current_qty + change
    if new_qty < 0:
        st.error("재고는 0보다 작을 수 없습니다!")
        return
    try:
        main_sheet.update_cell(row_idx + 2, qty_col_idx + 1, int(new_qty))
        if log_sheet:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            change_text = f"+{change}" if change > 0 else str(change)
            log_sheet.append_row([now, item_name, change_text, int(new_qty)])
        st.toast(f"✅ 수량 변경 완료!")
        st.rerun()
    except Exception as e:
        st.error(f"오류 발생: {e}")

st.set_page_config(page_title="온라인 창고 관리", layout="wide")
st.title("🌐 온라인 창고 관리 시스템")

try:
    client = get_gspread_client()
    spreadsheet = client.open_by_url(SHEET_URL)
    main_sheet = spreadsheet.sheet1
    try:
        log_sheet = spreadsheet.worksheet("로그")
    except:
        log_sheet = None

    data = main_sheet.get_all_records()
    
    if data:
        df = pd.DataFrame(data)
        # 컬럼 이름 자동 감지
        name_col = next((c for c in df.columns if '품목' in str(c) or '이름' in str(c)), df.columns[0])
        spec_col = df.columns[1] if len(df.columns) > 1 else None
        qty_col = next((c for c in df.columns if '수량' in str(c)), df.columns[2] if len(df.columns) > 2 else None)
        
        if qty_col:
            df[qty_col] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0).astype(int)
            qty_col_idx = list(df.columns).index(qty_col)

        st.sidebar.title("📦 메뉴")
        menu = st.sidebar.radio("이동", ["재고 현황", "간편 입출고", "품목 정보 수정", "신규 품목 등록", "활동 로그"])

        # --- 1. 재고 현황 ---
        if menu == "재고 현황":
            st.subheader("📊 현재 재고 리스트")
            st.dataframe(df, use_container_width=True, hide_index=True)

        # --- 2. 간편 입출고 (수량만 조절) ---
        elif menu == "간편 입출고":
            st.subheader("🛠️ 수량 증감")
            edit_search = st.text_input("품목 검색")
            display_df = df[df.astype(str).apply(lambda x: x.str.contains(edit_search, case=False)).any(axis=1)] if edit_search else df
            for idx, row in display_df.iterrows():
                with st.expander(f"📦 {row[name_col]} (현재: {row[qty_col]}개)"):
                    c1, c2 = st.columns(2)
                    with c1:
                        val = st.number_input("입고량", min_value=1, value=1, key=f"p_{idx}")
                        if st.button("입고 확인", key=f"bp_{idx}"):
                            update_stock(main_sheet, log_sheet, idx, row[name_col], row[qty_col], val, qty_col_idx)
                    with c2:
                        val_m = st.number_input("출고량", min_value=1, value=1, key=f"m_{idx}")
                        if st.button("출고 확인", key=f"bm_{idx}"):
                            update_stock(main_sheet, log_sheet, idx, row[name_col], row[qty_col], -val_m, qty_col_idx)

        # --- 3. 품목 정보 수정 (이름, 규격 변경) ---
        elif menu == "품목 정보 수정":
            st.subheader("📝 품목 기본 정보 변경")
            mod_search = st.text_input("수정할 품목 검색")
            mod_df = df[df.astype(str).apply(lambda x: x.str.contains(mod_search, case=False)).any(axis=1)] if mod_search else df
            for idx, row in mod_df.iterrows():
                with st.expander(f"✏️ {row[name_col]} 정보 수정"):
                    new_name = st.text_input("품목명 변경", value=row[name_col], key=f"en_{idx}")
                    new_spec = st.text_input("규격 변경", value=row.get(spec_col, ""), key=f"es_{idx}")
                    if st.button("정보 저장", key=f"eb_{idx}"):
                        if new_name != row[name_col]:
                            update_item_info(main_sheet, log_sheet, idx, row[name_col], name_col, new_name, df.columns)
                        if spec_col and new_spec != row[spec_col]:
                            update_item_info(main_sheet, log_sheet, idx, row[name_col], spec_col, new_spec, df.columns)

        # --- 4. 신규 품목 등록 ---
        elif menu == "신규 품목 등록":
            st.subheader("🆕 신규 품목 추가")
            with st.form("new_item"):
                name_in = st.text_input("품목명 (필수)")
                spec_in = st.text_input("규격 (선택)")
                qty_in = st.number_input("초기 수량", min_value=0, value=0)
                if st.form_submit_button("시트에 등록"):
                    if name_in:
                        main_sheet.append_row([name_in, spec_in, int(qty_in)])
                        if log_sheet:
                            log_sheet.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), name_in, "신규등록", int(qty_in)])
                        st.success("새 품목이 등록되었습니다!")
                        st.rerun()
                    else: st.error("품목명은 필수입니다.")

        # --- 5. 활동 로그 ---
        elif menu == "활동 로그":
            st.subheader("📜 히스토리")
            if log_sheet:
                log_data = log_sheet.get_all_values()
                if len(log_data) > 1:
                    st.dataframe(pd.DataFrame(log_data[1:], columns=log_data[0]).iloc[::-1], use_container_width=True)

except Exception as e:
    st.error(f"❌ 오류 발생: {e}")