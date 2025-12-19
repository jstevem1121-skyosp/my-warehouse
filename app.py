import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import re
from datetime import datetime
import time

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="품목별 통합 재고 관리", layout="wide")

# --- 2. 구글 시트 연결 및 캐싱 ---
@st.cache_resource
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = dict(st.secrets["gcp_service_account"])
    pk = creds_info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=2) # 데이터 확인을 위해 캐시 시간을 2초로 단축
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
        id_i = st.text_input("아이디(성함)").strip() # 공백 제거
        pw_i = st.text_input("비밀번호", type="password").strip()
        if st.form_submit_button("로그인"):
            # ID와 비밀번호 비교 시 문자열로 변환 및 공백 제거 후 비교
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
        # 모든 텍스트 데이터의 앞뒤 공백 제거 (필터링 오류 방지)
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
        cols = df.columns.tolist() # [소유자, 품목명, 규격, 수량]

        # --- 메뉴 1: 전체 품목 현황 ---
        if menu == "🏠 전체 품목 현황":
            st.subheader("📊 품목별 소유 현황 (누가 얼마나?)")
            items = df[df[cols[1]] != "신규 창고 개설"][cols[1]].unique()
            
            if len(items) == 0:
                st.info("등록된 품목이 없습니다.")
            else:
                for item in items:
                    item_df = df[df[cols[1]] == item]
                    total_q = item_df[cols[3]].sum()
                    with st.expander(f"📦 {item} (전체 합계: {total_q}개)"):
                        summary = item_df[[cols[0], cols[2], cols[3]]].rename(columns={cols[0]:"소유자", cols[2]:"규격", cols[3]:"수량"})
                        st.table(summary[summary["수량"] > 0])

        # --- 메뉴 2: 내 물품 관리 및 보내기 (보완됨) ---
        elif menu == "📥 내 물품 관리 및 보내기":
            st.subheader(f"📥 {user_id}님의 보관 물품")
            # 내 아이디와 일치하는 소유자 데이터만 정확히 필터링
            my_df = df[df[cols[0]] == user_id]
            
            # "신규 창고 개설" 행을 제외한 실제 물품만 필터링
            actual_items = my_df[my_df[cols[1]] != "신규 창고 개설"]

            if actual_items.empty:
                st.warning("현재 내 이름으로 등록된 물품이 없습니다. '새 품목 등록'에서 물건을 먼저 추가해주세요.")
            else:
                for idx, row in actual_items.iterrows():
                    with st.expander(f"🔹 {row[cols[1]]} [{row[cols[2]]}] - 현재 {row[cols[3]]}개"):
                        col1, col2 = st.columns(2)
                        actual_row_in_sheet = idx + 2 # 시트의 실제 행 번호

                        with col1:
                            st.write("🛠️ 입출고 관리")
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
                                else: st.error("재고가 부족합니다.")
                        
                        with col2:
                            st.write("🎁 다른 유저에게 보내기")
                            user_list = [str(u['ID']).strip() for u in user_data_list if str(u['ID']).strip() != user_id]
                            if not user_list:
                                st.info("보낼 수 있는 다른 유저가 없습니다.")
                            else:
                                target = st.selectbox("받는 사람", user_list, key=f"target_{idx}")
                                m_amt = st.number_input("보낼 수량", 1, int(row[cols[3]]) if int(row[cols[3]]) > 0 else 1, key=f"mamt_{idx}")
                                if st.button("🚀 보내기 실행", key=f"send_{idx}"):
                                    if row[cols[3]] < m_amt:
                                        st.error("보낼 수량이 부족합니다.")
                                    else:
                                        # 1. 내 수량 차감
                                        main_sheet.update_cell(actual_row_in_sheet, 4, int(row[cols[3]] - m_amt))
                                        # 2. 상대방 찾아서 추가 (품목명과 규격이 모두 같아야 함)
                                        target_idx = df[(df[cols[0]] == target) & (df[cols[1]] == row[cols[1]]) & (df[cols[2]] == row[cols[2]])].index
                                        if not target_idx.empty:
                                            current_target_q = df.loc[target_idx[0], cols[3]]
                                            main_sheet.update_cell(int(target_idx[0])+2, 4, int(current_target_q + m_amt))
                                        else:
                                            main_sheet.append_row([target, row[cols[1]], row[cols[2]], int(m_amt)])
                                        
                                        st.success(f"✅ {target}님에게 전달 완료!")
                                        st.cache_data.clear()
                                        time.sleep(1)
                                        st.rerun()

        # --- 메뉴 3: 새 품목 등록 ---
        elif menu == "🆕 새 품목 등록":
            st.subheader("🆕 내 창고에 새 품목 등록")
            st.info("여기에 등록하면 '내 물품 관리' 목록에 나타납니다.")
            with st.form("add_new"):
                n = st.text_input("품목명 (예: A자 사다리)").strip()
                s = st.text_input("규격 (예: 2.1m)").strip()
                q = st.number_input("초기 수량", 0)
                if st.form_submit_button("등록하기"):
                    if n:
                        main_sheet.append_row([user_id, n, s, q])
                        st.cache_data.clear()
                        st.success(f"'{n}' 등록이 완료되었습니다. '내 물품 관리'에서 확인하세요.")
                        time.sleep(1)
                        st.rerun()
                    else: st.warning("품목명을 입력해주세요.")

        # --- 메뉴 4: 계정 관리 ---
        elif menu == "👥 계정 관리" and role == "admin":
            st.subheader("👥 사용자 추가 (관리자 전용)")
            with st.form("u_create"):
                u = st.text_input("ID(이름)").strip()
                p = st.text_input("비밀번호").strip()
                r = st.selectbox("권한", ["user", "admin"])
                if st.form_submit_button("사용자 생성"):
                    if u and p:
                        user_sheet.append_row([u, p, r])
                        main_sheet.append_row([u, "신규 창고 개설", "-", 0])
                        st.cache_data.clear()
                        st.success(f"'{u}' 계정이 생성되었습니다.")
                    else: st.warning("ID와 비번을 입력하세요.")

except Exception as e:
    st.error(f"⚠️ 시스템 오류: {e}")