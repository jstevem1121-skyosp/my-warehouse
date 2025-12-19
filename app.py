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

@st.cache_data(ttl=5)
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
        id_i = st.text_input("아이디(성함)")
        pw_i = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인"):
            user_row = user_df[(user_df['ID'].astype(str) == id_i) & (user_df['비밀번호'].astype(str) == pw_i)]
            if not user_row.empty:
                st.session_state.update({"logged_in": True, "user_id": id_i, "role": user_row.iloc[0]['권한']})
                st.rerun()
            else: st.error("❌ 정보 불일치")
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
        try: log_sheet = spreadsheet.worksheet("로그")
        except: log_sheet = None

        user_id = st.session_state["user_id"]
        role = st.session_state["role"]
        
        st.sidebar.info(f"👤 {user_id}님 접속 중")
        if st.sidebar.button("로그아웃"):
            st.session_state.clear()
            st.cache_data.clear()
            st.rerun()

        menu = st.sidebar.radio("메뉴", ["🏠 전체 품목 현황", "📥 내 창고 관리/이동", "🆕 품목 등록", "👥 계정 관리"])

        # 데이터 로드
        raw_data = main_sheet.get_all_records()
        df = pd.DataFrame(raw_data)
        # 소유자, 품목명, 규격, 수량 컬럼 가정
        cols = df.columns.tolist()

        # --- 메뉴 1: 전체 품목 현황 (누가 몇 개 가지고 있는지 요약) ---
        if menu == "🏠 전체 품목 현황":
            st.subheader("📊 품목별 소유 현황")
            
            # 품목명 목록 추출 (신규 창고 개설 제외)
            items = df[df[cols[1]] != "신규 창고 개설"][cols[1]].unique()
            
            if len(items) == 0:
                st.info("등록된 품목이 없습니다.")
            else:
                for item in items:
                    item_df = df[df[cols[1]] == item]
                    total_q = item_df[cols[3]].sum()
                    with st.expander(f"📦 {item} (총계: {total_q}개)"):
                        # 해당 품목을 가진 사람 리스트업
                        summary = item_df[[cols[0], cols[3]]].rename(columns={cols[0]:"소유자", cols[3]:"수량"})
                        st.table(summary[summary["수량"] > 0]) # 수량이 있는 사람만 표시

        # --- 메뉴 2: 내 창고 관리 및 이동 ---
        elif menu == "📥 내 창고 관리/이동":
            st.subheader("📥 내 물품 관리 및 보내기")
            my_df = df[df[cols[0]] == user_id]
            
            if my_df.empty:
                st.warning("내 창고에 물품이 없습니다.")
            else:
                for idx, row in my_df.iterrows():
                    if row[cols[1]] == "신규 창고 개설": continue
                    
                    with st.expander(f"🔹 {row[cols[1]]} (현재: {row[cols[3]]}개)"):
                        col1, col2 = st.columns(2)
                        with col1:
                            amt = st.number_input("수량", 1, 1000, 1, key=f"a_{idx}")
                            if st.button("입고", key=f"i_{idx}"):
                                main_sheet.update_cell(idx+2, 4, int(row[cols[3]] + amt))
                                st.cache_data.clear()
                                st.rerun()
                            if st.button("출고", key=f"o_{idx}"):
                                if row[cols[3]] >= amt:
                                    main_sheet.update_cell(idx+2, 4, int(row[cols[3]] - amt))
                                    st.cache_data.clear()
                                    st.rerun()
                                else: st.error("재고 부족")
                        
                        with col2:
                            st.write("🎁 다른 사람에게 보내기")
                            user_list = [str(u['ID']) for u in user_data_list if str(u['ID']) != user_id]
                            target = st.selectbox("받는 사람", user_list, key=f"t_{idx}")
                            m_amt = st.number_input("보낼 수량", 1, int(row[cols[3]]), key=f"m_{idx}")
                            if st.button("보내기 실행", key=f"b_{idx}"):
                                # 1. 내 수량 차감
                                main_sheet.update_cell(idx+2, 4, int(row[cols[3]] - m_amt))
                                # 2. 상대방 수량 증가 (기존 행 찾기)
                                target_idx = df[(df[cols[0]] == target) & (df[cols[1]] == row[cols[1]])].index
                                if not target_idx.empty:
                                    # 이미 해당 품목 행이 있으면 수량 업데이트
                                    current_target_q = df.loc[target_idx[0], cols[3]]
                                    main_sheet.update_cell(int(target_idx[0])+2, 4, int(current_target_q + m_amt))
                                else:
                                    # 없으면 새 행 추가
                                    main_sheet.append_row([target, row[cols[1]], row[cols[2]], int(m_amt)])
                                
                                st.success(f"{target}님에게 전달 완료!")
                                st.cache_data.clear()
                                time.sleep(1)
                                st.rerun()

        # --- 메뉴 3: 신규 품목 등록 ---
        elif menu == "🆕 품목 등록":
            st.subheader("🆕 내 창고에 새 품목 추가")
            with st.form("add"):
                n = st.text_input("품목명")
                s = st.text_input("규격")
                q = st.number_input("초기 수량", 0)
                if st.form_submit_button("등록"):
                    main_sheet.append_row([user_id, n, s, q])
                    st.cache_data.clear()
                    st.rerun()

        # --- 메뉴 4: 계정 관리 ---
        elif menu == "👥 계정 관리" and role == "admin":
            st.subheader("👥 사용자 추가")
            with st.form("u_gen"):
                u, p = st.text_input("ID"), st.text_input("PW")
                r = st.selectbox("권한", ["user", "admin"])
                if st.form_submit_button("생성"):
                    user_sheet.append_row([u, p, r])
                    st.cache_data.clear()
                    st.rerun()

except Exception as e:
    st.error(f"오류: {e}")