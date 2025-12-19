import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import re
from datetime import datetime
import time

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="품목별 통합 재고 관리 시스템", layout="wide")

# --- 2. 구글 시트 연결 및 캐싱 ---
@st.cache_resource
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = dict(st.secrets["gcp_service_account"])
    pk = creds_info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=2)
def fetch_sheet_data(sheet_url, worksheet_name):
    client = get_gspread_client()
    spreadsheet = client.open_by_url(sheet_url)
    return spreadsheet.worksheet(worksheet_name).get_all_records()

# --- 3. 로그인 로직 ---
def check_login(user_sheet_data):
    if "logged_in" not in st.session_state:
        st.session_state.update({"logged_in": False, "user_id": "", "role": None})
    if st.session_state["logged_in"]: return True

    st.title("🔐 창고 시스템 로그인")
    user_df = pd.DataFrame(user_sheet_data)
    with st.form("login"):
        id_i = st.text_input("아이디(성함)").strip()
        pw_i = st.text_input("비밀번호", type="password").strip()
        if st.form_submit_button("로그인"):
            user_row = user_df[(user_df['ID'].astype(str).str.strip() == id_i) & 
                               (user_df['비밀번호'].astype(str).str.strip() == pw_i)]
            if not user_row.empty:
                st.session_state.update({"logged_in": True, "user_id": id_i, "role": user_row.iloc[0]['권한']})
                st.rerun()
            else: st.error("❌ 아이디 또는 비밀번호가 틀렸습니다.")
    return False

# --- 메인 실행 ---
try:
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"
    user_data_list = fetch_sheet_data(SHEET_URL, "사용자")
    
    if check_login(user_data_list):
        client = get_gspread_client()
        spreadsheet = client.open_by_url(SHEET_URL)
        main_sheet = spreadsheet.sheet1
        user_sheet = spreadsheet.worksheet("사용자")
        
        user_id = st.session_state["user_id"]
        role = st.session_state["role"]
        
        st.sidebar.info(f"👤 {user_id}님 접속 중 ({role})")
        if st.sidebar.button("로그아웃"):
            st.session_state.clear()
            st.cache_data.clear()
            st.rerun()

        menu = st.sidebar.radio("메뉴", ["🏠 전체 품목 현황", "📥 내 물품 관리 및 보내기", "🆕 새 품목 등록", "👥 계정 관리"])

        # 데이터 로드 및 전처리
        raw_data = main_sheet.get_all_records()
        df = pd.DataFrame(raw_data)
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
        cols = df.columns.tolist()

        # --- 메뉴 1: 전체 품목 현황 (관리자 가져오기 기능 포함) ---
        if menu == "🏠 전체 품목 현황":
            st.subheader("📊 전체 품목 소유 현황")
            items = df[df[cols[1]] != "신규 창고 개설"][cols[1]].unique()
            
            if len(items) == 0:
                st.info("등록된 품목이 없습니다.")
            else:
                for item in items:
                    item_df = df[df[cols[1]] == item]
                    total_q = item_df[cols[3]].sum()
                    with st.expander(f"📦 {item} (전체 합계: {total_q}개)"):
                        # 수량이 있는 데이터만 표시
                        display_df = item_df[item_df[cols[3]] > 0]
                        
                        if display_df.empty:
                            st.write("현재 재고를 가진 유저가 없습니다.")
                        else:
                            for i, row in display_df.iterrows():
                                c1, c2, c3 = st.columns([2, 1, 2])
                                c1.write(f"👤 소유자: **{row[cols[0]]}**")
                                c2.write(f"🔢 수량: {row[cols[3]]}")
                                
                                # 관리자이고, 소유자가 본인이 아닐 때만 '가져오기' 버튼 표시
                                if role == "admin" and row[cols[0]] != user_id:
                                    take_amt = c3.number_input(f"가져올 수량", 1, int(row[cols[3]]), 1, key=f"take_amt_{i}")
                                    if c3.button(f"내 창고로 가져오기", key=f"take_btn_{i}"):
                                        # 1. 상대방 수량 차감
                                        main_sheet.update_cell(i+2, 4, int(row[cols[3]] - take_amt))
                                        
                                        # 2. 내 창고에 추가 (내 행 찾기)
                                        my_row_idx = df[(df[cols[0]] == user_id) & (df[cols[1]] == row[cols[1]]) & (df[cols[2]] == row[cols[2]])].index
                                        if not my_row_idx.empty:
                                            my_curr_q = df.loc[my_row_idx[0], cols[3]]
                                            main_sheet.update_cell(int(my_row_idx[0])+2, 4, int(my_curr_q + take_amt))
                                        else:
                                            main_sheet.append_row([user_id, row[cols[1]], row[cols[2]], int(take_amt)])
                                        
                                        st.success(f"✅ {row[cols[0]]}님으로부터 {row[cols[1]]} {take_amt}개를 가져왔습니다.")
                                        st.cache_data.clear()
                                        time.sleep(1)
                                        st.rerun()
                                st.divider()

        # --- 메뉴 2: 내 물품 관리 및 보내기 ---
        elif menu == "📥 내 물품 관리 및 보내기":
            st.subheader(f"📥 {user_id}님의 보관 물품")
            my_df = df[(df[cols[0]] == user_id) & (df[cols[1]] != "신규 창고 개설")]

            if my_df.empty:
                st.warning("보관 중인 물품이 없습니다.")
            else:
                for idx, row in my_df.iterrows():
                    with st.expander(f"🔹 {row[cols[1]]} [{row[cols[2]]}] - 현재 {row[cols[3]]}개"):
                        col1, col2 = st.columns(2)
                        actual_row_in_sheet = idx + 2

                        with col1:
                            st.write("🛠️ 입출고")
                            amt = st.number_input("수량", 1, 10000, 1, key=f"amt_{idx}")
                            if st.button("➕ 입고", key=f"in_{idx}"):
                                main_sheet.update_cell(actual_row_in_sheet, 4, int(row[cols[3]] + amt))
                                st.cache_data.clear()
                                st.rerun()
                            if st.button("➖ 출고", key=f"out_{idx}"):
                                if row[cols[3]] >= amt:
                                    main_sheet.update_cell(actual_row_in_sheet, 4, int(row[cols[3]] - amt))
                                    st.cache_data.clear()
                                    st.rerun()
                                else: st.error("재고 부족")
                        
                        with col2:
                            st.write("🎁 보내기")
                            user_list = [str(u['ID']).strip() for u in user_data_list if str(u['ID']).strip() != user_id]
                            if user_list:
                                target = st.selectbox("받는 사람", user_list, key=f"target_{idx}")
                                m_amt = st.number_input("보낼 수량", 1, int(row[cols[3]]) if int(row[cols[3]]) > 0 else 1, key=f"mamt_{idx}")
                                if st.button("🚀 보내기 실행", key=f"send_{idx}"):
                                    main_sheet.update_cell(actual_row_in_sheet, 4, int(row[cols[3]] - m_amt))
                                    target_idx = df[(df[cols[0]] == target) & (df[cols[1]] == row[cols[1]]) & (df[cols[2]] == row[cols[2]])].index
                                    if not target_idx.empty:
                                        main_sheet.update_cell(int(target_idx[0])+2, 4, int(df.loc[target_idx[0], cols[3]] + m_amt))
                                    else:
                                        main_sheet.append_row([target, row[cols[1]], row[cols[2]], int(m_amt)])
                                    st.success("전달 완료!")
                                    st.cache_data.clear()
                                    time.sleep(1)
                                    st.rerun()

        # --- 메뉴 3: 새 품목 등록 ---
        elif menu == "🆕 새 품목 등록":
            st.subheader("🆕 내 창고에 새 품목 등록")
            with st.form("add_new"):
                n = st.text_input("품목명").strip()
                s = st.text_input("규격").strip()
                q = st.number_input("초기 수량", 0)
                if st.form_submit_button("등록하기"):
                    if n:
                        main_sheet.append_row([user_id, n, s, q])
                        st.cache_data.clear()
                        st.success(f"'{n}' 등록 완료")
                        st.rerun()

        # --- 메뉴 4: 계정 관리 ---
        elif menu == "👥 계정 관리" and role == "admin":
            st.subheader("👥 사용자 계정 관리")
            with st.form("u_create"):
                u = st.text_input("ID(이름)").strip()
                p = st.text_input("비밀번호").strip()
                r = st.selectbox("권한", ["user", "admin"])
                if st.form_submit_button("생성"):
                    user_sheet.append_row([u, p, r])
                    main_sheet.append_row([u, "신규 창고 개설", "-", 0])
                    st.cache_data.clear()
                    st.success(f"'{u}' 계정 생성 완료")
                    st.rerun()

except Exception as e:
    st.error(f"⚠️ 시스템 오류: {e}")