import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession # 명시적 로드
from datetime import datetime
import time
import streamlit.components.v1 as components

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="재고 관리 시스템 v3.5", layout="wide")

# --- 2. [최후의 수단] 인증 로직 전면 개편 ---
def get_gspread_client():
    """AuthorizedSession 이슈를 원천 차단하기 위한 하위 레벨 인증"""
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds_info = dict(st.secrets["gcp_service_account"])
        creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        
        # 1. Credentials 생성
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        
        # 2. gspread.authorize 대신 직접 클라이언트 생성 (핵심)
        # 만약 여기서도 에러가 나면 gspread 버전이 너무 낮거나 높은 것임
        client = gspread.Client(auth=creds)
        return client
    except Exception as e:
        st.error(f"🔑 인증 엔진 오류: {e}")
        return None

@st.cache_data(ttl=10) # 속도를 위해 캐시 시간 단축
def fetch_all_data(sheet_url):
    client = get_gspread_client()
    if not client: return None, None, None
    try:
        spreadsheet = client.open_by_url(sheet_url)
        main_sheet = spreadsheet.sheet1
        user_sheet = spreadsheet.worksheet("사용자")
        return main_sheet.get_all_records(), user_sheet.get_all_records(), spreadsheet
    except Exception as e:
        st.error(f"📊 로드 실패: {e}")
        return None, None, None

# --- 3. 데이터 업데이트 함수 (gspread 5.x 이상 버전 대응) ---
def target_update(spreadsheet, row_idx, col_letter, new_value, action, item, amount, target_user="-"):
    try:
        main_sheet = spreadsheet.sheet1
        cell_address = f"{col_letter}{row_idx + 2}"
        
        # .update() 대신 .update_acell() 혹은 하위 API 사용 고려
        # 가장 안정적인 update_acell 사용
        main_sheet.update_acell(cell_address, int(new_value))
        
        # 로그 기록
        try:
            log_sheet = spreadsheet.worksheet("이력")
        except:
            log_sheet = spreadsheet.add_worksheet(title="이력", rows="1000", cols="10")
            log_sheet.append_row(["일시", "사용자", "작업구분", "품목명", "수량", "상대방"])
            
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_sheet.insert_row([now, st.session_state["user_id"], action, item, int(amount), target_user], 2)
        
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"❌ 업데이트 실패 (중요): {e}")
        # 만약 여기서도 에러가 나면, 인증 라이브러리가 완전히 깨진 상태임
        return False

# --- 4. 로그인 시스템 ---
def check_login(user_df):
    if "logged_in" not in st.session_state:
        st.session_state.update({"logged_in": False, "user_id": "", "role": None})
    if st.session_state["logged_in"]: return True

    st.title("🔐 창고 통합 관리")
    with st.form("login"):
        id_i = st.text_input("아이디").strip()
        pw_i = st.text_input("비밀번호", type="password").strip()
        if st.form_submit_button("로그인"):
            user_row = user_df[(user_df['ID'].astype(str) == id_i) & (user_df['비밀번호'].astype(str) == pw_i)]
            if not user_row.empty:
                st.session_state.update({"logged_in": True, "user_id": id_i, "role": user_row.iloc[0]['권한']})
                st.rerun()
            else: st.error("❌ 정보 불일치")
    return False

# --- 5. 메인 앱 실행부 ---
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
            
            st.sidebar.success(f"로그인: {user_id}")
            menu = st.sidebar.radio("메뉴", ["🏠 현황", "📥 관리", "📜 이력", "📅 달력", "🆕 신규", "👥 계정"])

            if menu == "🏠 현황":
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
                                if c3.button("실행", key=f"bt_{i}"):
                                    target_update(spreadsheet, i, 'D', row[cols[3]] - t_amt, "회수", item, t_amt, row[cols[0]])
                                    st.rerun()

            elif menu == "📥 관리":
                my_df = df[(df[cols[0]] == user_id) & (df[cols[1]] != "신규 창고 개설")]
                for idx, row in my_df.iterrows():
                    with st.expander(f"🔹 {row[cols[1]]} ({row[cols[3]]}개)"):
                        c1, c2 = st.columns(2)
                        with c1:
                            adj = st.number_input("조정", 1, 1000, 1, key=f"adj_{idx}")
                            if st.button("➕ 입고", key=f"in_{idx}"):
                                target_update(spreadsheet, idx, 'D', row[cols[3]] + adj, "입고", row[cols[1]], adj)
                                st.rerun()
                            if st.button("➖ 출고", key=f"out_{idx}"):
                                if row[cols[3]] >= adj:
                                    target_update(spreadsheet, idx, 'D', row[cols[3]] - adj, "출고", row[cols[1]], adj)
                                    st.rerun()
                        with c2:
                            targets = [u for u in user_df['ID'] if str(u) != user_id]
                            target = st.selectbox("전송", targets, key=f"tg_{idx}")
                            m_amt = st.number_input("전송량", 1, int(row[cols[3]]) if int(row[cols[3]]) > 0 else 1, key=f"m_{idx}")
                            if st.button("🚀 보내기", key=f"s_{idx}"):
                                if row[cols[3]] >= m_amt:
                                    target_update(spreadsheet, idx, 'D', row[cols[3]] - m_amt, "전송", row[cols[1]], m_amt, target)
                                    spreadsheet.sheet1.append_row([target, row[cols[1]], row[cols[2]], int(m_amt)])
                                    st.rerun()

            elif menu == "📜 이력":
                try:
                    log_data = spreadsheet.worksheet("이력").get_all_records()
                    st.dataframe(pd.DataFrame(log_data).iloc[::-1].head(50), use_container_width=True)
                except: st.info("이력 없음")

            elif menu == "📅 달력":
                components.iframe("https://calendar.google.com/calendar/embed?src=ko.south_korea%23holiday%40group.v.calendar.google.com&ctz=Asia%2FSeoul", height=600)

            elif menu == "🆕 신규":
                with st.form("n"):
                    n, s, q = st.text_input("품목명"), st.text_input("규격"), st.number_input("수량", 0)
                    if st.form_submit_button("추가"):
                        spreadsheet.sheet1.append_row([user_id, n, s, q])
                        st.cache_data.clear(); st.rerun()

            elif menu == "👥 계정" and role == "admin":
                with st.form("u"):
                    u, p, r = st.text_input("ID"), st.text_input("PW"), st.selectbox("권한", ["user", "admin"])
                    if st.form_submit_button("생성"):
                        spreadsheet.worksheet("사용자").append_row([u, p, r])
                        spreadsheet.sheet1.append_row([u, "신규 창고 개설", "-", 0])
                        st.cache_data.clear(); st.rerun()

except Exception as e:
    st.error(f"⚠️ 시스템 오류: {e}")