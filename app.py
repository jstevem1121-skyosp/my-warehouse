import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time
import streamlit.components.v1 as components

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="통합 창고 및 비주얼 캘린더", layout="wide")

# --- 2. 구글 시트 연결 설정 ---
@st.cache_resource
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = dict(st.secrets["gcp_service_account"])
    pk = creds_info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(creds)

# --- 3. 로그인 체크 ---
def check_login(user_sheet):
    if "logged_in" not in st.session_state:
        st.session_state.update({"logged_in": False, "user_id": "", "role": None})
    if st.session_state["logged_in"]: return True

    st.title("🔐 시스템 로그인")
    user_data = user_sheet.get_all_records()
    user_df = pd.DataFrame(user_data)
    with st.form("login"):
        id_i = st.text_input("아이디(성함)").strip()
        pw_i = st.text_input("비밀번호", type="password").strip()
        if st.form_submit_button("로그인"):
            user_row = user_df[(user_df['ID'].astype(str) == id_i) & (user_df['비밀번호'].astype(str) == pw_i)]
            if not user_row.empty:
                st.session_state.update({"logged_in": True, "user_id": id_i, "role": user_row.iloc[0]['권한']})
                st.rerun()
            else: st.error("❌ 정보를 확인해주세요.")
    return False

# --- 메인 코드 시작 ---
try:
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"
    client = get_gspread_client()
    spreadsheet = client.open_by_url(SHEET_URL)
    main_sheet = spreadsheet.sheet1
    user_sheet = spreadsheet.worksheet("사용자")
    
    if check_login(user_sheet):
        user_id = st.session_state["user_id"]
        role = st.session_state["role"]
        
        st.sidebar.info(f"👤 {user_id}님 접속 중")
        menu = st.sidebar.radio("메뉴", ["🏠 전체 품목 현황", "📥 내 물품 관리", "📅 비주얼 캘린더", "🆕 새 품목 등록", "👥 계정 관리"])

        # 데이터 로드
        df = pd.DataFrame(main_sheet.get_all_records())
        cols = df.columns.tolist()

        # --- 메뉴: 📅 비주얼 캘린더 ---
        if menu == "📅 비주얼 캘린더":
            st.subheader("🗓️ 창고 일정 및 납품 달력")
            
            # 1. 일정 등록 (구글 시트에 저장)
            with st.expander("➕ 새 일정 등록"):
                try:
                    event_sheet = spreadsheet.worksheet("일정")
                    with st.form("event_form"):
                        e_date = st.date_input("날짜")
                        e_title = st.text_input("일정명")
                        e_memo = st.text_area("내용")
                        if st.form_submit_button("일정 저장"):
                            event_sheet.append_row([str(e_date), e_title, user_id, e_memo])
                            st.success("일정이 시트에 기록되었습니다.")
                except:
                    st.error("'일정' 탭을 시트에 만들어주세요.")

            st.divider()

            # 2. 달력 시각화 (Google Calendar Embed)
            # 여기의 URL을 본인의 구글 캘린더 공개 주소로 바꾸면 실제 달력이 나타납니다.
            # 아래는 예시용 공용 달력 주소입니다.
            calendar_url = "https://calendar.google.com/calendar/embed?src=ko.south_korea%23holiday%40group.v.calendar.google.com&ctz=Asia%2FSeoul"
            
            components.iframe(calendar_url, height=600, scrolling=True)
            
            st.info("💡 위 달력은 구글 캘린더와 실시간 연동이 가능합니다. (설정에서 공개된 캘린더 URL을 입력하세요)")

        # --- 메뉴: 🏠 전체 품목 현황 (나머지 로직은 이전과 동일) ---
        elif menu == "🏠 전체 품목 현황":
            st.subheader("📊 전체 재고 현황")
            items = df[df[cols[1]] != "신규 창고 개설"][cols[1]].unique()
            for item in items:
                item_df = df[df[cols[1]] == item]
                with st.expander(f"📦 {item} (총 {item_df[cols[3]].sum()}개)"):
                    st.table(item_df[[cols[0], cols[3]]].rename(columns={cols[0]:"소유자", cols[3]:"수량"}))

        # (나머지 내 물품 관리, 등록, 계정 관리 로직은 이전 코드와 동일하게 유지됩니다...)
        # ... [중략] ...

except Exception as e:
    st.error(f"오류: {e}")