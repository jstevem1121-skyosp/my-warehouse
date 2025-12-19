import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import re
from datetime import datetime

# --- 페이지 설정 ---
st.set_page_config(page_title="통합 창고 관리 시스템", layout="wide")

@st.cache_resource
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = dict(st.secrets["gcp_service_account"])
    pk = creds_info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(creds)

# --- 1. 로그인 로직 ---
def check_login(user_sheet):
    if "logged_in" not in st.session_state:
        st.session_state.update({"logged_in": False, "user_id": "", "role": None})

    if st.session_state["logged_in"]:
        return True

    st.title("🔐 창고 시스템 로그인")
    
    user_data = user_sheet.get_all_records()
    user_df = pd.DataFrame(user_data)

    with st.form("login_form"):
        id_input = st.text_input("아이디(성함)")
        pwd_input = st.text_input("비밀번호", type="password")
        submit = st.form_submit_button("로그인")

        if submit:
            # 시트의 'ID'와 '비밀번호' 컬럼 확인
            user_row = user_df[(user_df['ID'].astype(str) == id_input) & (user_df['비밀번호'].astype(str) == pwd_input)]
            
            if not user_row.empty:
                st.session_state["logged_in"] = True
                st.session_state["user_id"] = id_input
                st.session_state["role"] = user_row.iloc[0]['권한']
                st.rerun()
            else:
                st.error("❌ 아이디 또는 비밀번호가 일치하지 않습니다.")
    return False

# --- 메인 실행 ---
try:
    client = get_gspread_client()
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"
    spreadsheet = client.open_by_url(SHEET_URL)
    
    # 시트 연결
    main_sheet = spreadsheet.sheet1
    user_sheet = spreadsheet.worksheet("사용자")
    try: log_sheet = spreadsheet.worksheet("로그")
    except: log_sheet = None

    if check_login(user_sheet):
        user_id = st.session_state["user_id"]
        role = st.session_state["role"]
        
        st.sidebar.info(f"👤 접속: {user_id} ({role})")
        if st.sidebar.button("로그아웃"):
            st.session_state.clear()
            st.rerun()

        # 메뉴 구성
        menu_options = ["내 재고 현황", "입출고 및 이동", "신규 품목 등록"]
        if role == "admin":
            menu_options += ["👥 계정 관리", "📜 전체 로그"]
        
        menu = st.sidebar.radio("메뉴 선택", menu_options)

        # --- [관리자 전용] 👥 계정 관리 메뉴 ---
        if menu == "👥 계정 관리" and role == "admin":
            st.subheader("👥 신규 사용자 계정 생성")
            with st.form("new_user_form", clear_on_submit=True):
                new_id = st.text_input("생성할 아이디(성함)")
                new_pwd = st.text_input("설정할 비밀번호")
                new_role = st.selectbox("권한 설정", ["user", "admin"])
                
                if st.form_submit_button("계정 생성하기"):
                    if new_id and new_pwd:
                        # 중복 체크
                        existing_users = user_sheet.col_values(1)
                        if new_id in existing_users:
                            st.error("이미 존재하는 아이디입니다.")
                        else:
                            user_sheet.append_row([new_id, new_pwd, new_role])
                            st.success(f"✅ '{new_id}' 계정이 성공적으로 생성되었습니다.")
                    else:
                        st.warning("아이디와 비밀번호를 모두 입력하세요.")
            
            st.divider()
            st.subheader("현재 등록된 사용자 목록")
            st.dataframe(pd.DataFrame(user_sheet.get_all_records()), use_container_width=True)

        # --- 내 재고 현황 ---
        elif menu == "내 재고 현황":
            raw_data = main_sheet.get_all_records()
            full_df = pd.DataFrame(raw_data)
            df = full_df if role == "admin" else full_df[full_df['소유자'] == user_id]
            st.subheader(f"📊 {user_id}님의 재고 현황")
            st.dataframe(df, use_container_width=True, hide_index=True)

        # --- 입출고 및 이동 (기존 로직 유지) ---
        elif menu == "입출고 및 이동":
            st.subheader("📥 물품 관리 및 이동")
            # ... (이전 코드의 입출고/이동 로직 삽입) ...
            st.info("이동 및 입출고 기능을 실행하세요.")

        # --- 신규 품목 등록 ---
        elif menu == "신규 품목 등록":
            st.subheader("🆕 내 창고 품목 추가")
            with st.form("add_item"):
                item_n = st.text_input("품목명")
                item_s = st.text_input("규격")
                item_q = st.number_input("초기 수량", 0)
                if st.form_submit_button("등록"):
                    main_sheet.append_row([user_id, item_n, item_s, item_q])
                    st.success("등록 완료!")
                    st.rerun()

        # --- [관리자 전용] 📜 전체 로그 ---
        elif menu == "📜 전체 로그" and role == "admin":
            st.subheader("📜 시스템 전체 활동 내역")
            if log_sheet:
                logs = log_sheet.get_all_values()
                st.dataframe(pd.DataFrame(logs[1:], columns=logs[0]).iloc[::-1], use_container_width=True)

except Exception as e:
    st.error(f"오류: {e}")