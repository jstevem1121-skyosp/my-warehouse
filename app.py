import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import re
from datetime import datetime

# --- 페이지 설정 ---
st.set_page_config(page_title="개인별 창고 관리", layout="wide")

# --- 1. 로그인 로직 (이전과 동일) ---
def check_login():
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
        st.session_state["user_id"] = ""
        st.session_state["role"] = None

    if st.session_state["logged_in"]:
        return True

    st.title("🔒 창고 관리 시스템")
    user_id_input = st.text_input("사용자 성함(ID) 입력", placeholder="본인 이름을 적으세요")
    pwd_input = st.text_input("비밀번호", type="password")
    
    if st.button("내 창고 접속"):
        if not user_id_input:
            st.error("성함을 입력해야 합니다.")
        elif pwd_input == str(st.secrets["app_password"]): # 관리자 (모든 창고 조회 가능)
            st.session_state.update({"logged_in": True, "user_id": user_id_input, "role": "admin"})
            st.rerun()
        elif pwd_input == str(st.secrets["user_password"]): # 일반 (본인 창고만)
            st.session_state.update({"logged_in": True, "user_id": user_id_input, "role": "user"})
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    return False

@st.cache_resource
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = dict(st.secrets["gcp_service_account"])
    pk = creds_info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(creds)

# --- 메인 실행 ---
if check_login():
    user_id = st.session_state["user_id"]
    role = st.session_state["role"]
    
    st.sidebar.info(f"👤 {user_id}님의 창고")
    if st.sidebar.button("로그아웃"):
        st.session_state.clear()
        st.rerun()

    SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"
    
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_url(SHEET_URL)
        main_sheet = spreadsheet.sheet1
        try: log_sheet = spreadsheet.worksheet("로그")
        except: log_sheet = None

        # 데이터 로딩 및 필터링
        raw_data = main_sheet.get_all_records()
        full_df = pd.DataFrame(raw_data)
        
        # 컬럼 감지
        owner_col = next((c for c in full_df.columns if '소유' in str(c) or 'ID' in str(c)), full_df.columns[0])
        name_col = next((c for c in full_df.columns if '품목' in str(c)), full_df.columns[1])
        qty_col = next((c for c in full_df.columns if '수량' in str(c)), full_df.columns[3])

        # ⭐ 핵심: 사용자에 따라 데이터 필터링
        if role == "admin":
            df = full_df # 관리자는 전체 데이터 확인
            st.sidebar.warning("🛠️ 관리자 모드 (전체 조회)")
        else:
            df = full_df[full_df[owner_col] == user_id] # 일반 유저는 본인 이름 데이터만!

        menu = st.sidebar.radio("메뉴", ["내 재고 현황", "입출고 관리", "신규 품목 등록"])

        if menu == "내 재고 현황":
            st.subheader(f"📦 {user_id}님의 창고 리스트")
            st.dataframe(df, use_container_width=True, hide_index=True)

        elif menu == "입출고 관리":
            st.subheader("📥 물품 입출고")
            if df.empty:
                st.warning("등록된 물품이 없습니다. 먼저 신규 등록을 해주세요.")
            else:
                for idx, row in df.iterrows():
                    with st.expander(f"{row[name_col]} (현재: {row[qty_col]})"):
                        c1, c2 = st.columns(2)
                        with c1:
                            amt = st.number_input("수량", 1, 100, 1, key=f"n{idx}")
                            if st.button("입고", key=f"in{idx}"):
                                new_q = int(row[qty_col] + amt)
                                main_sheet.update_cell(idx+2, list(full_df.columns).index(qty_col)+1, new_q)
                                if log_sheet: log_sheet.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id, row[name_col], f"+{amt}", new_q])
                                st.rerun()
                        with c2:
                            if st.button("출고", key=f"out{idx}"):
                                new_q = int(row[qty_col] - amt)
                                if new_q < 0: st.error("재고 부족")
                                else:
                                    main_sheet.update_cell(idx+2, list(full_df.columns).index(qty_col)+1, new_q)
                                    if log_sheet: log_sheet.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id, row[name_col], f"-{amt}", new_q])
                                    st.rerun()

        elif menu == "신규 품목 등록":
            st.subheader("🆕 내 창고에 물품 추가")
            with st.form("add_form"):
                new_n = st.text_input("품목명")
                new_s = st.text_input("규격")
                new_q = st.number_input("초기 수량", 0)
                if st.form_submit_button("등록"):
                    # ⭐ 저장할 때 현재 로그인한 user_id를 '소유자' 칸에 함께 저장!
                    main_sheet.append_row([user_id, new_n, new_s, new_q])
                    if log_sheet: log_sheet.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id, new_n, "신규등록", new_q])
                    st.success("등록되었습니다!")
                    st.rerun()

    except Exception as e:
        st.error(f"오류: {e}")