import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import google.auth.transport.requests
import requests
from datetime import datetime
import streamlit.components.v1 as components

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="재고 관리 시스템 v5.0", layout="wide")

# --- 2. [완전 해결] API 직접 호출 엔진 ---
def get_access_token():
    """구글 라이브러리 에러를 우회하여 직접 토큰만 가져옴"""
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds_info = dict(st.secrets["gcp_service_account"])
    creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    auth_request = google.auth.transport.requests.Request()
    creds.refresh(auth_request)
    return creds.token

def google_api_request(method, range_name, values=None):
    """gspread를 쓰지 않고 REST API로 직접 시트 수정"""
    token = get_access_token()
    sheet_id = "1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY" # 제공해주신 시트 ID
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{range_name}"
    
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    params = {"valueInputOption": "USER_ENTERED"}
    
    if method == "GET":
        resp = requests.get(url, headers=headers)
        return resp.json().get('values', [])
    elif method == "UPDATE":
        body = {"values": values}
        requests.put(url, headers=headers, params=params, json=body)
    elif method == "APPEND":
        body = {"values": values}
        requests.post(f"{url}:append", headers=headers, params=params, json=body)

# --- 3. 데이터 로드 및 처리 ---
@st.cache_data(ttl=5)
def load_all_data():
    try:
        main_data = google_api_request("GET", "시트1!A:D") # 시트 이름 확인 필요 (기본: 시트1)
        user_data = google_api_request("GET", "사용자!A:C")
        
        df = pd.DataFrame(main_data[1:], columns=main_data[0]) if main_data else pd.DataFrame()
        u_df = pd.DataFrame(user_data[1:], columns=user_data[0]) if user_data else pd.DataFrame()
        return df, u_df
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return pd.DataFrame(), pd.DataFrame()

# --- 4. 핵심 기능: 전송 및 이력 기록 ---
def execute_transfer(row_idx, item_name, spec, current_qty, send_qty, target_user):
    """행 추가가 아닌 '값 수정' + '이력 기록' 일괄 처리"""
    try:
        # 1. 내 수량 차감 (D열은 4번째 열)
        new_my_qty = int(current_qty) - int(send_qty)
        google_api_request("UPDATE", f"시트1!D{row_idx + 2}", [[new_my_qty]])
        
        # 2. 상대방 행 찾아서 합산 또는 추가
        # (간소화를 위해 일단 기존처럼 전송 시에는 상대방 행을 새로 추가하되, 
        #  관리가 필요하면 이 부분을 수정 가능합니다.)
        google_api_request("APPEND", "시트1!A:D", [[target_user, item_name, spec, send_qty]])
        
        # 3. 이력 기록 (반드시 실행)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        google_api_request("APPEND", "이력!A:F", [[now, st.session_state["user_id"], "전송", item_name, send_qty, target_user]])
        
        st.cache_data.clear()
        st.success(f"✅ {target_user}님에게 {send_qty}개 전송 완료!")
        return True
    except Exception as e:
        st.error(f"작업 오류: {e}")
        return False

# --- 5. UI 메인 로직 ---
df, user_df = load_all_data()

if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "user_id": "", "role": ""})

if not st.session_state["logged_in"]:
    st.title("🔐 재고 관리 시스템")
    with st.form("login"):
        id_i = st.text_input("아이디")
        pw_i = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인"):
            row = user_df[(user_df['ID'] == id_i) & (user_df['비밀번호'] == pw_i)]
            if not row.empty:
                st.session_state.update({"logged_in": True, "user_id": id_i, "role": row.iloc[0]['권한']})
                st.rerun()
            else: st.error("로그인 실패")
else:
    user_id = st.session_state["user_id"]
    st.sidebar.info(f"접속: {user_id}")
    menu = st.sidebar.radio("메뉴", ["🏠 현황/회수", "📥 내 관리/전송", "📜 이력조회"])

    if menu == "🏠 현황/회수":
        st.subheader("📊 실시간 창고 현황")
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
                                execute_transfer(i, item, row['규격'], row['수량'], r_amt, user_id)
                                st.rerun()

    elif menu == "📥 내 관리/전송":
        my_df = df[df['사용자'] == user_id]
        for idx, row in my_df.iterrows():
            if row['품목명'] == "신규 창고 개설": continue
            with st.expander(f"🔹 {row['품목명']} ({row['수량']}개)"):
                c1, c2 = st.columns(2)
                with c1:
                    adj = st.number_input("조정", 1, 100, 1, key=f"a_{idx}")
                    if st.button("➕ 입고", key=f"i_{idx}"):
                        google_api_request("UPDATE", f"시트1!D{idx + 2}", [[int(row['수량']) + adj]])
                        st.cache_data.clear(); st.rerun()
                with c2:
                    targets = [u for u in user_df['ID'] if u != user_id]
                    target = st.selectbox("전송 대상", targets, key=f"t_{idx}")
                    s_amt = st.number_input("수량", 1, int(row['수량']), 1, key=f"s_{idx}")
                    if st.button("🚀 보내기", key=f"sb_{idx}"):
                        execute_transfer(idx, row['품목명'], row['규격'], row['수량'], s_amt, target)
                        st.rerun()

    elif menu == "📜 이력조회":
        st.subheader("📜 작업 기록")
        logs = google_api_request("GET", "이력!A:F")
        if logs:
            st.table(pd.DataFrame(logs[1:], columns=logs[0]).iloc[::-1].head(30))