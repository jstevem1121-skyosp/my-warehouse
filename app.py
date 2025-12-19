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

# 수량 변경 함수
def update_stock(main_sheet, log_sheet, row_idx, item_name, current_qty, change, qty_col_idx):
    new_qty = current_qty + change
    if new_qty < 0:
        st.error(f"❌ {item_name}: 재고가 부족합니다! (현재: {current_qty})")
        return
    
    try:
        main_sheet.update_cell(row_idx + 2, qty_col_idx + 1, int(new_qty))
        
        # 로그 기록
        if change != 0:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            change_text = f"+{change}" if change > 0 else str(change)
            if log_sheet:
                log_sheet.append_row([now, item_name, change_text, int(new_qty)])
        
        st.toast(f"✅ {item_name} {change}개 처리 완료! (현재: {new_qty})")
        st.rerun()
    except Exception as e:
        st.error(f"업데이트 중 오류 발생: {e}")

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
        # 컬럼 유연하게 찾기
        qty_col = next((c for c in df.columns if '수량' in str(c)), df.columns[2] if len(df.columns) > 2 else None)
        name_col = next((c for c in df.columns if '품목' in str(c) or '이름' in str(c)), df.columns[0])
        
        if qty_col:
            df[qty_col] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0).astype(int)
            qty_col_idx = list(df.columns).index(qty_col)

        st.sidebar.title("📦 메뉴")
        menu = st.sidebar.radio("이동", ["재고 현황", "간편 입출고", "활동 로그"])

        if menu == "재고 현황":
            st.success("전체 재고 리스트")
            st.dataframe(df, use_container_width=True, hide_index=True)

        elif menu == "간편 입출고":
            st.subheader("🛠️ 수량 증감 조정")
            edit_search = st.text_input("품목 검색", placeholder="이름을 입력하세요")
            display_df = df[df.astype(str).apply(lambda x: x.str.contains(edit_search, case=False)).any(axis=1)] if edit_search else df

            for idx, row in display_df.iterrows():
                item_name = row[name_col]
                curr_qty = row[qty_col]
                
                with st.expander(f"📦 {item_name} (현재: {curr_qty}개)", expanded=True):
                    c1, c2, c3 = st.columns([1, 2, 2])
                    
                    with c1:
                        st.write("**기본 조정**")
                        if st.button(f"➕ 1개", key=f"p1_{idx}"):
                            update_stock(main_sheet, log_sheet, idx, item_name, curr_qty, 1, qty_col_idx)
                        if st.button(f"➖ 1개", key=f"m1_{idx}"):
                            update_stock(main_sheet, log_sheet, idx, item_name, curr_qty, -1, qty_col_idx)

                    with c2:
                        st.write("**직접 더하기**")
                        plus_val = st.number_input("입고 수량", min_value=1, value=10, key=f"plus_{idx}", step=1)
                        if st.button(f"확인: +{plus_val}개", key=f"btn_p_{idx}"):
                            update_stock(main_sheet, log_sheet, idx, item_name, curr_qty, plus_val, qty_col_idx)

                    with c3:
                        st.write("**직접 빼기**")
                        minus_val = st.number_input("출고 수량", min_value=1, value=10, key=f"minus_{idx}", step=1)
                        if st.button(f"확인: -{minus_val}개", key=f"btn_m_{idx}"):
                            update_stock(main_sheet, log_sheet, idx, item_name, curr_qty, -minus_val, qty_col_idx)

        elif menu == "활동 로그":
            st.subheader("📜 최근 활동 내역")
            if log_sheet:
                log_data = log_sheet.get_all_values()
                if len(log_data) > 1:
                    log_df = pd.DataFrame(log_data[1:], columns=log_data[0])
                    st.dataframe(log_df.iloc[::-1].head(30), use_container_width=True)
                else: st.info("기록이 없습니다.")
except Exception as e:
    st.error(f"❌ 오류 발생: {e}")