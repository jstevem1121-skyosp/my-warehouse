import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import google.auth.transport.requests
import requests
from datetime import datetime
import streamlit.components.v1 as components

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="창고 통합 관리 시스템 v5.1", layout="wide")

# --- 2. 구글 REST API 직접 통신 엔진 ---
def get_access_token():
    """라이브러리 에러 우회를 위해 직접 토큰 생성"""
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds_info = dict(st.secrets["gcp_service_account"])
    creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    auth_request = google.auth.transport.requests.Request()
    creds.refresh(auth_request)
    return creds.token

def google_api_request(method, range_name, values=None):
    """gspread 없이 API로 직접 데이터 읽기/쓰기"""
    token = get_access_token()
    sheet_id = "1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY"
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{range_name}"
    
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    params = {"valueInputOption": "USER_ENTERED"}
    
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers)
            return resp.json().get('values', [])
        elif method == "UPDATE":
            body = {"values": values}
            requests.put(url, headers=headers, params=params, json=body)
        elif method == "APPEND":
            body = {"values": values}
            requests.post(f"{url}:append", headers=headers, params=params, json=body)
        return True
    except Exception as e:
        st.error(f"API 통신 오류: {e}")
        return False

# --- 3. 데이터 로딩 (캐시 적용) ---
@st.cache_data(ttl=5)
def load_all_data():
    # 탭 이름이 '시트1'인지 'Sheet1'인지 확인 필수
    main_rows = google_api_request("GET", "시트1!A:D") 
    user_rows = google_api_request("GET", "사용자!A:C")
    
    df = pd.DataFrame(main_rows[1:], columns=main_rows[0]) if main_rows else pd.DataFrame()
    u_df = pd.DataFrame(user_rows[1:], columns=user_rows[0]) if user_rows else pd.DataFrame()
    return df, u_df

# --- 4. 로그인 시스템 ---
df, user_df = load_all_data()
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "user_id": "", "role": ""})

if not st.session_state["logged_in"]:
    st.title("🔐 창고 관리 시스템 v5.1")
    with st.form("login"):
        id_i = st.text_input("아이디")
        pw_i = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인"):
            u_row = user_df[(user_df['ID'] == id_i) & (user_df['비밀번호'] == pw_i)]
            if not u_row.empty:
                st.session_state.update({"logged_in": True, "user_id": id_i, "role": u_row.iloc[0]['권한']})
                st.rerun()
            else: st.error("계정 정보를 확인하세요.")
else:
    # --- 5. 메인 앱 화면 ---
    user_id = st.session_state["user_id"]
    st.sidebar.success(f"접속: {user_id} ({st.session_state['role']})")
    menu = st.sidebar.radio("메뉴", ["🏠 현황 및 회수", "📥 내 물품 관리", "📜 작업 이력", "📅 일정 달력", "🆕 신규 등록"])

    # [1] 현황 및 회수 (관리자용)
    if menu == "🏠 현황 및 회수":
        st.subheader("📊 실시간 전체 재고")
        if not df.empty:
            for item in df['품목명'].unique():
                if item == "신규 창고 개설": continue
                item_df = df[df['품목명'] == item]
                with st.expander(f"📦 {item} (총 {item_df['수량'].astype(int).sum()}개)"):
                    for i, row in item_df.iterrows():
                        if int(row['수량']) <= 0: continue
                        c1, c2, c3 = st.columns([2,1,2])
                        c1.write(f"👤 {row['사용자']}")
                        c2.write(f"🔢 {row['수량']}")
                        if st.session_state["role"] == "admin" and row['사용자'] != user_id:
                            r_amt = c3.number_input("회수량", 1, int(row['수량']), 1, key=f"r_{i}")
                            if c3.button("즉시 회수", key=f"rb_{i}"):
                                # 내 수량 업데이트 + 이력 남기기
                                google_api_request("UPDATE", f"시트1!D{i+2}", [[int(row['수량']) - r_amt]])
                                google_api_request("APPEND", "이력!A:F", [[datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id, "관리자회수", item, r_amt, row['사용자']]])
                                st.cache_data.clear(); st.rerun()

    # [2] 내 물품 관리 (핵심: 행 추가가 아닌 '값 수정')
    elif menu == "📥 내 물품 관리":
        st.subheader("📥 내 재고 관리 및 전송")
        my_df = df[df['사용자'] == user_id]
        if my_df.empty: st.info("보유 중인 품목이 없습니다.")
        for idx, row in my_df.iterrows():
            if row['품목명'] == "신규 창고 개설": continue
            with st.expander(f"🔹 {row['품목명']} | 규격: {row['규격']} | 현재: {row['수량']}개"):
                col1, col2 = st.columns(2)
                with col1:
                    adj = st.number_input("입/출고량", 1, 1000, 1, key=f"adj_{idx}")
                    if st.button("➕ 입고", key=f"in_{idx}"):
                        google_api_request("UPDATE", f"시트1!D{idx+2}", [[int(row['수량']) + adj]])
                        google_api_request("APPEND", "이력!A:F", [[datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id, "입고", row['품목명'], adj, "-"]])
                        st.cache_data.clear(); st.rerun()
                    if st.button("➖ 출고", key=f"out_{idx}"):
                        if int(row['수량']) >= adj:
                            google_api_request("UPDATE", f"시트1!D{idx+2}", [[int(row['수량']) - adj]])
                            google_api_request("APPEND", "이력!A:F", [[datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id, "출고", row['품목명'], adj, "-"]])
                            st.cache_data.clear(); st.rerun()
                with col2:
                    targets = [u for u in user_df['ID'] if u != user_id]
                    target = st.selectbox("전송 대상", targets, key=f"tg_{idx}")
                    s_amt = st.number_input("전송 수량", 1, int(row['수량']), 1, key=f"s_{idx}")
                    if st.button("🚀 전송하기", key=f"send_{idx}"):
                        # 1. 내 수량 차감
                        google_api_request("UPDATE", f"시트1!D{idx+2}", [[int(row['수량']) - s_amt]])
                        # 2. 상대방 행 추가
                        google_api_request("APPEND", "시트1!A:D", [[target, row['품목명'], row['규격'], s_amt]])
                        # 3. 이력 기록
                        google_api_request("APPEND", "이력!A:F", [[datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id, "전송", row['품목명'], s_amt, target]])
                        st.cache_data.clear(); st.rerun()

    # [3] 작업 이력
    elif menu == "📜 작업 이력":
        st.subheader("📜 최근 작업 내역")
        logs = google_api_request("GET", "이력!A:F")
        if logs:
            log_df = pd.DataFrame(logs[1:], columns=logs[0])
            st.dataframe(log_df.iloc[::-1].head(50), use_container_width=True)

    # [4] 달력
    elif menu == "📅 일정 달력":
        components.iframe("https://calendar.google.com/calendar/embed?src=ko.south_korea%23holiday%40group.v.calendar.google.com&ctz=Asia%2FSeoul", height=600)

    # [5] 신규 등록
    elif menu == "🆕 신규 등록":
        with st.form("new_reg"):
            n, s, q = st.text_input("품목명"), st.text_input("규격"), st.number_input("초기수량", 0)
            if st.form_submit_button("시트에 추가"):
                google_api_request("APPEND", "시트1!A:D", [[user_id, n, s, q]])
                google_api_request("APPEND", "이력!A:F", [[datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id, "신규등록", n, q, "-"]])
                st.cache_data.clear(); st.success("등록 완료"); st.rerun()