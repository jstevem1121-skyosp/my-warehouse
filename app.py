import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time
import streamlit.components.v1 as components

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="고속 창고 관리 시스템 v3.2", layout="wide")

# --- 2. 구글 시트 연결 및 인증 최적화 ---
@st.cache_resource
def get_gspread_client():
    """인증 에러 및 세션 만료 방지를 위한 최적화된 클라이언트 생성"""
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_info = dict(st.secrets["gcp_service_account"])
        creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"🔑 구글 인증 실패: {e}")
        return None

@st.cache_data(ttl=60)
def fetch_all_data(sheet_url):
    """데이터 로딩 속도 향상을 위한 캐싱 및 통합 호출"""
    client = get_gspread_client()
    if not client: return None, None, None
    try:
        spreadsheet = client.open_by_url(sheet_url)
        main_sheet = spreadsheet.sheet1
        user_sheet = spreadsheet.worksheet("사용자")
        
        main_data = main_sheet.get_all_records()
        user_data = user_sheet.get_all_records()
        return main_data, user_data, spreadsheet
    except Exception as e:
        st.error(f"📊 데이터 불러오기 실패: {e}")
        return None, None, None

# --- 3. 핵심 기능: 고속 업데이트 및 로그 기록 ---
def safe_log(spreadsheet, action, item, amount, target_user="-"):
    """이력 시트 자동 생성 및 안전한 기록"""
    try:
        worksheets = [s.title for s in spreadsheet.worksheets()]
        if "이력" not in worksheets:
            log_sheet = spreadsheet.add_worksheet(title="이력", rows="1000", cols="10")
            log_sheet.append_row(["일시", "사용자", "작업구분", "품목명", "수량", "상대방"])
        else:
            log_sheet = spreadsheet.worksheet("이력")
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_sheet.insert_row([now, st.session_state["user_id"], action, item, int(amount), target_user], 2)
        return True
    except Exception as e:
        st.warning(f"⚠️ 로그 기록 지연: {e}")
        return False

def target_update(spreadsheet, row_idx, col_letter, new_value, action, item, amount, target_user="-"):
    """전체 쓰기 대신 특정 셀만 타겟팅하여 버벅임 방지"""
    try:
        main_sheet = spreadsheet.sheet1
        cell_address = f"{col_letter}{row_idx + 2}" # 헤더 포함 인덱스 보정
        main_sheet.update(cell_address, [[int(new_value)]])
        
        # 로그 기록 (비동기 느낌으로 처리)
        safe_log(spreadsheet, action, item, amount, target_user)
        
        st.cache_data.clear() # 수정 후 다음 로드 시 최신 데이터 보장
        return True
    except Exception as e:
        st.error(f"❌ 업데이트 실패: {e}")
        return False

# --- 4. 로그인 시스템 ---
def check_login(user_df):
    if "logged_in" not in st.session_state:
        st.session_state.update({"logged_in": False, "user_id": "", "role": None})
    if st.session_state["logged_in"]: return True

    st.title("🔐 재고 관리 시스템 로그인")
    with st.form("login_form"):
        id_i = st.text_input("아이디").strip()
        pw_i = st.text_input("비밀번호", type="password").strip()
        if st.form_submit_button("로그인"):
            user_row = user_df[(user_df['ID'].astype(str) == id_i) & (user_df['비밀번호'].astype(str) == pw_i)]
            if not user_row.empty:
                st.session_state.update({"logged_in": True, "user_id": id_i, "role": user_row.iloc[0]['권한']})
                st.rerun()
            else: st.error("아이디 또는 비밀번호가 틀렸습니다.")
    return False

# --- 5. 메인 애플리케이션 로직 ---
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
            
            # 사이드바 메뉴
            st.sidebar.success(f"접속 중: {user_id} [{role}]")
            menu = st.sidebar.radio("메뉴 이동", ["🏠 재고 현황", "📥 내 물품 관리", "📜 작업 이력", "📅 일정", "🆕 품목 등록", "👥 관리자 전용"])

            # [1] 재고 현황
            if menu == "🏠 재고 현황":
                st.subheader("📊 실시간 전체 재고")
                items = df[df[cols[1]] != "신규 창고 개설"][cols[1]].unique()
                for item in items:
                    item_df = df[df[cols[1]] == item]
                    with st.expander(f"📦 {item} (총 {item_df[cols[3]].sum()}개)"):
                        for i, row in item_df[item_df[cols[3]] > 0].iterrows():
                            c1, c2, c3 = st.columns([2, 1, 2])
                            c1.write(f"👤 {row[cols[0]]}")
                            c2.write(f"🔢 {row[cols[3]]}개")
                            if role == "admin" and row[cols[0]] != user_id:
                                t_amt = c3.number_input("회수량", 1, int(row[cols[3]]), 1, key=f"t_{i}")
                                if c3.button("즉시 회수", key=f"bt_{i}"):
                                    with st.spinner("회수 중..."):
                                        target_update(spreadsheet, i, 'D', row[cols[3]] - t_amt, "관리자 회수", item, t_amt, row[cols[0]])
                                        st.rerun()

            # [2] 내 물품 관리 (가장 많이 사용)
            elif menu == "📥 내 물품 관리":
                st.subheader("📥 나의 재고 및 이동")
                my_df = df[(df[cols[0]] == user_id) & (df[cols[1]] != "신규 창고 개설")]
                if my_df.empty: st.info("보유 중인 품목이 없습니다.")
                for idx, row in my_df.iterrows():
                    with st.expander(f"🔹 {row[cols[1]]} | 규격: {row[cols[2]]} | 수량: {row[cols[3]]}"):
                        c1, c2 = st.columns(2)
                        with c1:
                            adj = st.number_input("수량 조정", 1, 1000, 1, key=f"adj_{idx}")
                            if st.button("➕ 입고", key=f"in_{idx}"):
                                target_update(spreadsheet, idx, 'D', row[cols[3]] + adj, "입고", row[cols[1]], adj)
                                st.rerun()
                            if st.button("➖ 출고", key=f"out_{idx}"):
                                if row[cols[3]] >= adj:
                                    target_update(spreadsheet, idx, 'D', row[cols[3]] - adj, "출고", row[cols[1]], adj)
                                    st.rerun()
                                else: st.error("재고 부족")
                        with c2:
                            target_users = [u for u in user_df['ID'] if str(u) != user_id]
                            target = st.selectbox("전송 대상", target_users, key=f"tg_{idx}")
                            m_amt = st.number_input("전송 수량", 1, int(row[cols[3]]) if int(row[cols[3]]) > 0 else 1, key=f"m_{idx}")
                            if st.button("🚀 물품 전송", key=f"send_{idx}"):
                                if row[cols[3]] >= m_amt:
                                    with st.spinner("전송 중..."):
                                        # 내 재고 차감
                                        target_update(spreadsheet, idx, 'D', row[cols[3]] - m_amt, "전송", row[cols[1]], m_amt, target)
                                        # 상대방에게 추가 (새 행 생성)
                                        spreadsheet.sheet1.append_row([target, row[cols[1]], row[cols[2]], int(m_amt)])
                                        st.rerun()

            # [3] 작업 이력
            elif menu == "📜 작업 이력":
                st.subheader("📜 최근 작업 기록")
                try:
                    log_data = spreadsheet.worksheet("이력").get_all_records()
                    if log_data:
                        st.dataframe(pd.DataFrame(log_data).iloc[::-1].head(50), use_container_width=True)
                    else: st.info("기록이 없습니다.")
                except: st.warning("이력 시트를 불러올 수 없습니다. 작업을 진행하여 시트를 생성하세요.")

            # [4] 달력
            elif menu == "📅 일정":
                components.iframe("https://calendar.google.com/calendar/embed?src=ko.south_korea%23holiday%40group.v.calendar.google.com&ctz=Asia%2FSeoul", height=600)

            # [5] 신규 등록
            elif menu == "🆕 품목 등록":
                with st.form("new_item"):
                    n, s, q = st.text_input("품목명"), st.text_input("규격"), st.number_input("초기 수량", 0)
                    if st.form_submit_button("시트에 추가"):
                        spreadsheet.sheet1.append_row([user_id, n, s, q])
                        safe_log(spreadsheet, "신규 등록", n, q)
                        st.cache_data.clear(); st.success("등록 완료"); st.rerun()

            # [6] 관리자 전용
            elif menu == "👥 관리자 전용" and role == "admin":
                st.subheader("👥 사용자 계정 관리")
                with st.form("new_user"):
                    u, p, r = st.text_input("새 아이디"), st.text_input("새 비밀번호"), st.selectbox("권한", ["user", "admin"])
                    if st.form_submit_button("계정 생성"):
                        spreadsheet.worksheet("사용자").append_row([u, p, r])
                        spreadsheet.sheet1.append_row([u, "신규 창고 개설", "-", 0])
                        st.cache_data.clear(); st.success(f"{u} 계정 생성 완료"); st.rerun()

except Exception as e:
    st.error(f"⚠️ 시스템 오류가 발생했습니다: {e}")