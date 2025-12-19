import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import re
from datetime import datetime
import time

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="통합 개인 창고 관리 시스템", layout="wide")

# --- 2. 구글 시트 연결 함수 (캐싱 적용) ---
@st.cache_resource
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = dict(st.secrets["gcp_service_account"])
    pk = creds_info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(creds)

# 데이터 읽기 함수 (10초 동안 캐시 유지하여 API 호출 절약)
@st.cache_data(ttl=10)
def fetch_sheet_data(sheet_url, worksheet_name):
    client = get_gspread_client()
    spreadsheet = client.open_by_url(sheet_url)
    return spreadsheet.worksheet(worksheet_name).get_all_records()

# --- 3. 로그인 체크 로직 ---
def check_login(user_sheet_data):
    if "logged_in" not in st.session_state:
        st.session_state.update({"logged_in": False, "user_id": "", "role": None})

    if st.session_state["logged_in"]:
        return True

    st.title("🔐 창고 시스템 로그인")
    user_df = pd.DataFrame(user_sheet_data)

    with st.form("login_form"):
        id_input = st.text_input("아이디(성함)")
        pwd_input = st.text_input("비밀번호", type="password")
        submit = st.form_submit_button("로그인")

        if submit:
            user_row = user_df[(user_df['ID'].astype(str) == id_input) & (user_df['비밀번호'].astype(str) == pwd_input)]
            if not user_row.empty:
                st.session_state.update({
                    "logged_in": True,
                    "user_id": id_input,
                    "role": user_row.iloc[0]['권한']
                })
                st.rerun()
            else:
                st.error("❌ 아이디 또는 비밀번호가 일치하지 않습니다.")
    return False

# --- 메인 실행부 ---
try:
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"
    
    # 캐시된 데이터 가져오기 (API 호출 횟수 감소)
    user_data_list = fetch_sheet_data(SHEET_URL, "사용자")
    
    if check_login(user_data_list):
        client = get_gspread_client()
        spreadsheet = client.open_by_url(SHEET_URL)
        main_sheet = spreadsheet.sheet1
        user_sheet = spreadsheet.worksheet("사용자")
        try: log_sheet = spreadsheet.worksheet("로그")
        except: log_sheet = None

        user_id = st.session_state["user_id"]
        role = st.session_state["role"]
        
        st.sidebar.info(f"👤 접속: {user_id}\n\n🎖️ 권한: {role}")
        if st.sidebar.button("로그아웃"):
            st.session_state.clear()
            st.cache_data.clear() # 로그아웃 시 캐시 삭제
            st.rerun()

        menu_options = ["🏠 내 창고 현황", "📥 입출고 및 이동", "🆕 신규 품목 등록"]
        if role == "admin":
            menu_options += ["👥 계정 관리", "📜 전체 활동 로그"]
        
        menu = st.sidebar.radio("메뉴 선택", menu_options)

        # 재고 데이터 로딩
        raw_data = main_sheet.get_all_records()
        full_df = pd.DataFrame(raw_data)
        cols = list(full_df.columns)

        if menu == "🏠 내 창고 현황":
            st.subheader(f"📊 {user_id}님의 실시간 재고")
            df = full_df if role == "admin" else full_df[full_df[cols[0]] == user_id]
            st.dataframe(df, use_container_width=True, hide_index=True)

        elif menu == "📥 입출고 및 이동":
            st.subheader("📥 물품 관리 및 창고 간 이동")
            my_df = full_df if role == "admin" else full_df[full_df[cols[0]] == user_id]

            if my_df.empty:
                st.warning("내 창고에 물품이 없습니다.")
            else:
                for idx, row in my_df.iterrows():
                    actual_row = idx + 2
                    with st.expander(f"📦 {row[cols[1]]} (현재: {row[cols[3]]}개)"):
                        t1, t2 = st.tabs(["➕ 일반 입출고", "🎁 타 유저에게 보내기"])
                        
                        with t1:
                            amt = st.number_input("수량 설정", 1, 1000, 1, key=f"amt_{idx}")
                            c1, c2 = st.columns(2)
                            if c1.button("입고 확인", key=f"in_{idx}"):
                                main_sheet.update_cell(actual_row, 4, int(row[cols[3]] + amt))
                                if log_sheet: log_sheet.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id, row[cols[1]], f"+{amt} (입고)", int(row[cols[3]] + amt)])
                                st.cache_data.clear() # 데이터 변경 시 캐시 갱신
                                st.rerun()
                            if c2.button("출고 확인", key=f"out_{idx}"):
                                if row[cols[3]] < amt: st.error("재고 부족")
                                else:
                                    main_sheet.update_cell(actual_row, 4, int(row[cols[3]] - amt))
                                    if log_sheet: log_sheet.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id, row[cols[1]], f"-{amt} (출고)", int(row[cols[3]] - amt)])
                                    st.cache_data.clear()
                                    st.rerun()

                        with t2:
                            user_list = [str(u['ID']) for u in user_data_list if str(u['ID']) != user_id]
                            if not user_list: st.info("보낼 대상이 없습니다.")
                            else:
                                target = st.selectbox("받는 사람 선택", user_list, key=f"tg_{idx}")
                                m_amt = st.number_input("이동 수량", 1, int(row[cols[3]]) if int(row[cols[3]]) > 0 else 1, key=f"ma_{idx}")
                                if st.button(f"{target}님에게 보내기", key=f"mv_{idx}"):
                                    # 이동 처리 전 짧은 대기 (API 과부하 방지)
                                    time.sleep(0.5)
                                    main_sheet.update_cell(actual_row, 4, int(row[cols[3]] - m_amt))
                                    target_row = full_df[(full_df[cols[0]] == target) & (full_df[cols[1]] == row[cols[1]])]
                                    if not target_row.empty:
                                        main_sheet.update_cell(target_row.index[0]+2, 4, int(target_row.iloc[0][cols[3]] + m_amt))
                                    else:
                                        main_sheet.append_row([target, row[cols[1]], row[cols[2]], int(m_amt)])
                                    if log_sheet:
                                        log_sheet.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id, row[cols[1]], f"{target}에게 이동", int(row[cols[3]] - m_amt)])
                                    st.cache_data.clear()
                                    st.success("이동 완료!")
                                    st.rerun()

        # (나머지 메뉴 동일...)
        elif menu == "🆕 신규 품목 등록":
            st.subheader("🆕 내 창고 신규 품목 등록")
            with st.form("add_form", clear_on_submit=True):
                n, s, q = st.text_input("품목명"), st.text_input("규격"), st.number_input("초기 수량", 0)
                if st.form_submit_button("등록"):
                    if n:
                        main_sheet.append_row([user_id, n, s, q])
                        if log_sheet: log_sheet.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id, n, "신규등록", q])
                        st.cache_data.clear()
                        st.success(f"'{n}' 등록 완료!")
                        st.rerun()

        elif menu == "👥 계정 관리" and role == "admin":
            st.subheader("👥 사용자 계정 관리")
            with st.form("user_gen", clear_on_submit=True):
                new_id, new_pw = st.text_input("새 아이디"), st.text_input("새 비밀번호")
                new_role = st.selectbox("권한", ["user", "admin"])
                if st.form_submit_button("계정 생성"):
                    user_sheet.append_row([new_id, new_pw, new_role])
                    main_sheet.append_row([new_id, "신규 창고 개설", "-", 0])
                    st.cache_data.clear()
                    st.success(f"{new_id} 계정 생성 완료")
                    st.rerun()
            st.dataframe(pd.DataFrame(user_data_list), use_container_width=True)

except Exception as e:
    if "429" in str(e):
        st.error("⚠️ 구글 시트 API 사용량이 초과되었습니다. 1분만 기다렸다가 다시 시도해 주세요.")
    else:
        st.error(f"⚠️ 오류 발생: {e}")