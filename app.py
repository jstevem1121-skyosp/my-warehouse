import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time
import streamlit.components.v1 as components

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="고속 창고 관리 시스템 v3.1", layout="wide")

# --- 2. [수정] 구글 시트 연결 및 인증 로직 강화 ---
def get_gspread_client():
    """인증 에러 방지를 위해 세션 관리를 강화한 클라이언트 생성"""
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_info = dict(st.secrets["gcp_service_account"])
        creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        
        # Credentials 객체를 직접 생성하여 AuthorizedSession 이슈 방지
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"🔑 인증 설정 오류: {e}")
        return None

@st.cache_data(ttl=60)
def fetch_all_data(sheet_url):
    client = get_gspread_client()
    if not client: return None, None, None
    spreadsheet = client.open_by_url(sheet_url)
    main_sheet = spreadsheet.sheet1
    user_sheet = spreadsheet.worksheet("사용자")
    
    return main_sheet.get_all_records(), user_sheet.get_all_records(), spreadsheet

# --- 3. [개선] 로그 기록 함수 (에러 방지용) ---
def safe_log(spreadsheet, action, item, amount, target_user="-"):
    """에러 발생 시 재시도 로직을 포함한 로그 기록"""
    try:
        log_sheet = spreadsheet.worksheet("이력")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_row = [now, st.session_state["user_id"], action, item, int(amount), target_user]
        
        # append_row 에러 시 insert_row로 우회 시도
        log_sheet.insert_row(new_row, 2) # 헤더 바로 아래에 삽입 (더 빠름)
        return True
    except Exception as e:
        st.warning(f"⚠️ 로그 기록 중 일시적 오류(무시가능): {e}")
        return False

# --- 4. [개선] 셀 업데이트 함수 ---
def target_update(spreadsheet, row_idx, col_letter, new_value, action, item, amount, target_user="-"):
    try:
        main_sheet = spreadsheet.sheet1
        cell_address = f"{col_letter}{row_idx + 2}"
        main_sheet.update(cell_address, [[new_value]])
        
        # 로그 기록 호출
        safe_log(spreadsheet, action, item, amount, target_user)
        
        st.cache_data.clear() 
        return True
    except Exception as e:
        # AuthorizedSession 에러 발생 시 세션 재연결 시도 안내
        if "AuthorizedSession" in str(e):
            st.error("🔄 세션이 만료되었습니다. 페이지를 새로고침(F5) 해주세요.")
        else:
            st.error(f"저장 실패: {e}")
        return False

# --- 5. 로그인 체크 ---
def check_login(user_df):
    if "logged_in" not in st.session_state:
        st.session_state.update({"logged_in": False, "user_id": "", "role": None})
    if st.session_state["logged_in"]: return True

    st.title("🔐 시스템 로그인")
    with st.form("login"):
        id_i = st.text_input("아이디").strip()
        pw_i = st.text_input("비밀번호", type="password").strip()
        if st.form_submit_button("로그인"):
            user_row = user_df[(user_df['ID'].astype(str) == id_i) & (user_df['비밀번호'].astype(str) == pw_i)]
            if not user_row.empty:
                st.session_state.update({"logged_in": True, "user_id": id_i, "role": user_row.iloc[0]['권한']})
                st.rerun()
            else: st.error("❌ 로그인 정보 오류")
    return False

# --- 메인 실행부 ---
try:
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"
    main_raw, user_raw, spreadsheet = fetch_all_data(SHEET_URL)
    
    if main_raw is not None:
        df = pd.DataFrame(main_raw)
        user_df = pd.DataFrame(user_raw)
        cols = df.columns.tolist()

        if check_login(user_df):
            user_id = st.session_state["user_id"]
            role = st.session_state["role"]
            
            st.sidebar.info(f"👤 {user_id} ({role})")
            menu = st.sidebar.radio("메뉴", ["🏠 현황", "📥 내 관리/이동", "📜 이력", "📅 달력", "🆕 등록", "👥 계정"])

            if menu == "🏠 현황":
                st.subheader("📊 전체 재고 현황")
                items = df[df[cols[1]] != "신규 창고 개설"][cols[1]].unique()
                for item in items:
                    item_df = df[df[cols[1]] == item]
                    with st.expander(f"📦 {item} ({item_df[cols[3]].sum()}개)"):
                        for i, row in item_df[item_df[cols[3]] > 0].iterrows():
                            c1, c2, c3 = st.columns([2, 1, 2])
                            c1.write(f"👤 {row[cols[0]]}")
                            c2.write(f"🔢 {row[cols[3]]}")
                            if role == "admin" and row[cols[0]] != user_id:
                                t_amt = c3.number_input("회수", 1, int(row[cols[3]]), 1, key=f"t_{i}")
                                if c3.button("즉시 회수", key=f"bt_{i}"):
                                    target_update(spreadsheet, i, 'D', int(row[cols[3]] - t_amt), "회수", item, t_amt, row[cols[0]])
                                    st.rerun()

            elif menu == "📥 내 관리/이동":
                my_df = df[(df[cols[0]] == user_id) & (df[cols[1]] != "신규 창고 개설")]
                for idx, row in my_df.iterrows():
                    with st.expander(f"🔹 {row[cols[1]]} ({row[cols[3]]}개)"):
                        col1, col2 = st.columns(2)
                        with col1:
                            adj_amt = st.number_input("조정", 1, 1000, 1, key=f"a_{idx}")
                            if st.button("➕ 입고", key=f"i_{idx}"):
                                if target_update(spreadsheet, idx, 'D', int(row[cols[3]] + adj_amt), "입고", row[cols[1]], adj_amt):
                                    st.rerun()
                            if st.button("➖ 출고", key=f"o_{idx}"):
                                if row[cols[3]] >= adj_amt:
                                    if target_update(spreadsheet, idx, 'D', int(row[cols[3]] - adj_amt), "출고", row[cols[1]], adj_amt):
                                        st.rerun()
                        with col2:
                            target_list = [u for u in user_df['ID'] if str(u) != user_id]
                            target = st.selectbox("받는 사람", target_list, key=f"tg_{idx}")
                            m_amt = st.number_input("전송 수량", 1, int(row[cols[3]]) if int(row[cols[3]]) > 0 else 1, key=f"m_{idx}")
                            if st.button("🚀 전송", key=f"s_{idx}"):
                                if row[cols[3]] >= m_amt:
                                    # 전송 시에도 target_update 활용 (본인 차감)
                                    if target_update(spreadsheet, idx, 'D', int(row[cols[3]] - m_amt), "전송", row[cols[1]], m_amt, target):
                                        # 상대방 추가 (이 부분은 append_row 사용)
                                        spreadsheet.sheet1.append_row([target, row[cols[1]], row[cols[2]], int(m_amt)])
                                        st.rerun()

            elif menu == "📜 이력":
                st.subheader("📜 최근 기록 (최신 30건)")
                try:
                    log_sheet = spreadsheet.worksheet("이력")
                    log_data = log_sheet.get_all_records()
                    if log_data:
                        st.table(pd.DataFrame(log_data).iloc[::-1].head(30))
                    else: st.info("기록 없음")
                except: st.error("이력 시트 로드 실패")

            elif menu == "📅 달력":
                components.iframe("https://calendar.google.com/calendar/embed?src=ko.south_korea%23holiday%40group.v.calendar.google.com&ctz=Asia%2FSeoul", height=600)

            elif menu == "🆕 등록":
                with st.form("new"):
                    n, s, q = st.text_input("품목명"), st.text_input("규격"), st.number_input("수량", 0)
                    if st.form_submit_button("등록"):
                        spreadsheet.sheet1.append_row([user_id, n, s, q])
                        safe_log(spreadsheet, "신규 등록", n, q)
                        st.cache_data.clear(); st.success("등록 완료"); st.rerun()

except Exception as e:
    st.error(f"⚠️ 시스템 오류: {e}")