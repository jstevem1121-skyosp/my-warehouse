import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time
import streamlit.components.v1 as components

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="고속 창고 관리 시스템 v3", layout="wide")

# --- 2. 구글 시트 연결 및 캐싱 ---
@st.cache_resource
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = dict(st.secrets["gcp_service_account"])
    creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=60) # 캐시 시간을 늘려 불필요한 호출 방지
def fetch_all_data(sheet_url):
    client = get_gspread_client()
    spreadsheet = client.open_by_url(sheet_url)
    main_sheet = spreadsheet.sheet1
    user_sheet = spreadsheet.worksheet("사용자")
    
    main_data = main_sheet.get_all_records()
    user_data = user_sheet.get_all_records()
    return main_data, user_data, spreadsheet

# --- 3. [초고속] 타겟 업데이트 함수 ---
def target_update(spreadsheet, row_idx, col_letter, new_value, action, item, amount, target_user="-"):
    """전체 덮어쓰기 대신 특정 셀만 수정하여 속도 극대화"""
    try:
        main_sheet = spreadsheet.sheet1
        # 구글 시트는 1부터 시작, 헤더 포함이므로 idx+2
        cell_address = f"{col_letter}{row_idx + 2}"
        main_sheet.update(cell_address, [[new_value]])
        
        # 로그 기록 (속도 영향 최소화 위해 간결하게)
        log_sheet = spreadsheet.worksheet("이력")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_sheet.append_row([now, st.session_state["user_id"], action, item, int(amount), target_user])
        
        st.cache_data.clear() # 다음 로드 시 최신 데이터 보장
        return True
    except Exception as e:
        st.error(f"저장 실패: {e}")
        return False

# --- 4. 로그인 체크 ---
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
    
    df = pd.DataFrame(main_raw)
    user_df = pd.DataFrame(user_raw)
    cols = df.columns.tolist()

    if check_login(user_df):
        user_id = st.session_state["user_id"]
        role = st.session_state["role"]
        
        st.sidebar.info(f"👤 {user_id} ({role})")
        menu = st.sidebar.radio("메뉴", ["🏠 현황", "📥 내 관리/이동", "📜 이력", "📅 달력", "🆕 등록", "👥 계정"])

        # --- [1] 현황 메뉴 ---
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
                                with st.spinner("처리 중..."):
                                    # 관리자 회수는 두 명의 수량을 바꿔야 하므로 예외적으로 append_row나 배치 사용
                                    # 여기서는 안정성을 위해 기존 로직을 고속화함
                                    target_update(spreadsheet, i, 'D', int(row[cols[3]] - t_amt), "회수", item, t_amt, row[cols[0]])
                                    st.rerun()

        # --- [2] 내 관리 및 이동 (속도 핵심) ---
        elif menu == "📥 내 관리/이동":
            my_df = df[(df[cols[0]] == user_id) & (df[cols[1]] != "신규 창고 개설")]
            for idx, row in my_df.iterrows():
                with st.expander(f"🔹 {row[cols[1]]} ({row[cols[3]]}개)"):
                    col1, col2 = st.columns(2)
                    with col1:
                        adj_amt = st.number_input("조정", 1, 1000, 1, key=f"a_{idx}")
                        if st.button("➕ 입고", key=f"i_{idx}"):
                            with st.spinner("입고 중..."):
                                if target_update(spreadsheet, idx, 'D', int(row[cols[3]] + adj_amt), "입고", row[cols[1]], adj_amt):
                                    st.rerun()
                        if st.button("➖ 출고", key=f"o_{idx}"):
                            if row[cols[3]] >= adj_amt:
                                with st.spinner("출고 중..."):
                                    if target_update(spreadsheet, idx, 'D', int(row[cols[3]] - adj_amt), "출고", row[cols[1]], adj_amt):
                                        st.rerun()
                            else: st.error("재고 부족")
                    with col2:
                        target = st.selectbox("받는 사람", [u for u in user_df['ID'] if u != user_id], key=f"tg_{idx}")
                        m_amt = st.number_input("전송 수량", 1, int(row[cols[3]]) if int(row[cols[3]]) > 0 else 1, key=f"m_{idx}")
                        if st.button("🚀 전송", key=f"s_{idx}"):
                            with st.spinner("전송 중..."):
                                # 전송은 복잡하므로 append_row 활용 (가장 안전)
                                spreadsheet.sheet1.update_cell(idx+2, 4, int(row[cols[3]] - m_amt))
                                spreadsheet.sheet1.append_row([target, row[cols[1]], row[cols[2]], int(m_amt)])
                                target_update(spreadsheet, idx, 'D', int(row[cols[3]] - m_amt), "전송", row[cols[1]], m_amt, target)
                                st.rerun()

        # --- [3] 이력 조회 ---
        elif menu == "📜 이력":
            st.subheader("📜 최근 기록 (최신 30건)")
            log_sheet = spreadsheet.worksheet("이력")
            log_data = log_sheet.get_all_records()
            st.table(pd.DataFrame(log_data).iloc[::-1].head(30))

        # --- [4] 달력 ---
        elif menu == "📅 달력":
            components.iframe("https://calendar.google.com/calendar/embed?src=ko.south_korea%23holiday%40group.v.calendar.google.com&ctz=Asia%2FSeoul", height=600)

        # --- [5] 등록 ---
        elif menu == "🆕 등록":
            with st.form("new"):
                n, s, q = st.text_input("품목명"), st.text_input("규격"), st.number_input("수량", 0)
                if st.form_submit_button("등록"):
                    spreadsheet.sheet1.append_row([user_id, n, s, q])
                    st.cache_data.clear()
                    st.success("등록 완료"); st.rerun()

        # --- [6] 계정 ---
        elif menu == "👥 계정" and role == "admin":
            with st.form("user"):
                u, p, r = st.text_input("ID"), st.text_input("PW"), st.selectbox("권한", ["user", "admin"])
                if st.form_submit_button("계정 생성"):
                    spreadsheet.worksheet("사용자").append_row([u, p, r])
                    spreadsheet.sheet1.append_row([u, "신규 창고 개설", "-", 0])
                    st.cache_data.clear()
                    st.success("생성 완료"); st.rerun()

except Exception as e:
    st.error(f"⚠️ 시스템 오류: {e}")