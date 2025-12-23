import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time
import streamlit.components.v1 as components

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="고속 창고 관리 시스템 v3.3", layout="wide")

# --- 2. 구글 시트 연결 (에러 방지용 신규 인증 방식) ---
def get_client():
    """AuthorizedSession 에러를 방지하는 안정적인 클라이언트 생성"""
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_info = dict(st.secrets["gcp_service_account"])
        creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        
        # gspread 최신 방식: 직접 dict를 전달하여 세션 이슈 방지
        client = gspread.service_account_from_dict(creds_info)
        return client
    except Exception as e:
        st.error(f"🔑 인증 실패: {e}")
        return None

@st.cache_data(ttl=60)
def fetch_all_data(sheet_url):
    client = get_client()
    if not client: return None, None, None
    try:
        spreadsheet = client.open_by_url(sheet_url)
        main_sheet = spreadsheet.sheet1
        user_sheet = spreadsheet.worksheet("사용자")
        return main_sheet.get_all_records(), user_sheet.get_all_records(), spreadsheet
    except Exception as e:
        st.error(f"📊 로드 실패: {e}")
        return None, None, None

# --- 3. 고속 업데이트 및 로그 함수 ---
def target_update(spreadsheet, row_idx, col_letter, new_value, action, item, amount, target_user="-"):
    """특정 셀만 타겟 업데이트 (에러 발생 시 즉시 재연결)"""
    try:
        main_sheet = spreadsheet.sheet1
        cell_address = f"{col_letter}{row_idx + 2}"
        # values는 반드시 2차원 리스트 형태여야 함
        main_sheet.update(range_name=cell_address, values=[[int(new_value)]])
        
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
        # 에러 발생 시 사용자에게 명확한 가이드 제공
        st.error(f"❌ 업데이트 실패: {e}")
        st.info("💡 일시적인 네트워크 오류일 수 있습니다. 페이지를 새로고침(F5) 후 다시 시도해 주세요.")
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
            else: st.error("❌ 정보 오류")
    return False

# --- 5. 메인 로직 ---
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
            
            st.sidebar.info(f"👤 {user_id}님 ({role})")
            menu = st.sidebar.radio("메뉴", ["🏠 재고 현황", "📥 내 물품 관리", "📜 작업 이력", "📅 일정", "🆕 품목 등록", "👥 계정 관리"])

            if menu == "🏠 재고 현황":
                st.subheader("📊 전체 재고")
                items = df[df[cols[1]] != "신규 창고 개설"][cols[1]].unique()
                for item in items:
                    item_df = df[df[cols[1]] == item]
                    with st.expander(f"📦 {item} (총 {item_df[cols[3]].sum()}개)"):
                        for i, row in item_df[item_df[cols[3]] > 0].iterrows():
                            c1, c2, c3 = st.columns([2, 1, 2])
                            c1.write(f"👤 {row[cols[0]]}")
                            c2.write(f"🔢 {row[cols[3]]}")
                            if role == "admin" and row[cols[0]] != user_id:
                                t_amt = c3.number_input("회수", 1, int(row[cols[3]]), 1, key=f"t_{i}")
                                if c3.button("즉시 회수", key=f"bt_{i}"):
                                    target_update(spreadsheet, i, 'D', row[cols[3]] - t_amt, "관리자 회수", item, t_amt, row[cols[0]])
                                    st.rerun()

            elif menu == "📥 내 물품 관리":
                my_df = df[(df[cols[0]] == user_id) & (df[cols[1]] != "신규 창고 개설")]
                for idx, row in my_df.iterrows():
                    with st.expander(f"🔹 {row[cols[1]]} ({row[cols[3]]}개)"):
                        col1, col2 = st.columns(2)
                        with col1:
                            adj = st.number_input("조정량", 1, 1000, 1, key=f"adj_{idx}")
                            if st.button("➕ 입고", key=f"in_{idx}"):
                                target_update(spreadsheet, idx, 'D', row[cols[3]] + adj, "입고", row[cols[1]], adj)
                                st.rerun()
                            if st.button("➖ 출고", key=f"out_{idx}"):
                                if row[cols[3]] >= adj:
                                    target_update(spreadsheet, idx, 'D', row[cols[3]] - adj, "출고", row[cols[1]], adj)
                                    st.rerun()
                                else: st.error("재고 부족")
                        with col2:
                            target = st.selectbox("전송 대상", [u for u in user_df['ID'] if str(u) != user_id], key=f"tg_{idx}")
                            m_amt = st.number_input("전송 수량", 1, int(row[cols[3]]) if int(row[cols[3]]) > 0 else 1, key=f"m_{idx}")
                            if st.button("🚀 전송", key=f"send_{idx}"):
                                if row[cols[3]] >= m_amt:
                                    target_update(spreadsheet, idx, 'D', row[cols[3]] - m_amt, "전송", row[cols[1]], m_amt, target)
                                    spreadsheet.sheet1.append_row([target, row[cols[1]], row[cols[2]], int(m_amt)])
                                    st.rerun()

            elif menu == "📜 작업 이력":
                st.subheader("📜 최근 작업 기록")
                try:
                    log_data = spreadsheet.worksheet("이력").get_all_records()
                    st.dataframe(pd.DataFrame(log_data).iloc[::-1].head(50), use_container_width=True)
                except: st.info("아직 이력이 없습니다.")

            elif menu == "📅 일정":
                components.iframe("https://calendar.google.com/calendar/embed?src=ko.south_korea%23holiday%40group.v.calendar.google.com&ctz=Asia%2FSeoul", height=600)

            elif menu == "🆕 품목 등록":
                with st.form("new"):
                    n, s, q = st.text_input("품목명"), st.text_input("규격"), st.number_input("수량", 0)
                    if st.form_submit_button("등록"):
                        spreadsheet.sheet1.append_row([user_id, n, s, q])
                        st.cache_data.clear(); st.success("등록 완료"); st.rerun()

            elif menu == "👥 계정 관리" and role == "admin":
                with st.form("u_new"):
                    u, p, r = st.text_input("ID"), st.text_input("PW"), st.selectbox("권한", ["user", "admin"])
                    if st.form_submit_button("생성"):
                        spreadsheet.worksheet("사용자").append_row([u, p, r])
                        spreadsheet.sheet1.append_row([u, "신규 창고 개설", "-", 0])
                        st.cache_data.clear(); st.success("완료"); st.rerun()

except Exception as e:
    st.error(f"⚠️ 예상치 못한 오류: {e}")