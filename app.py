import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import google.auth.transport.requests
import requests
from datetime import datetime
import streamlit.components.v1 as components

# --- 1. 페이지 설정 및 디자인 ---
st.set_page_config(page_title="정밀 재고 관리 v6.2", layout="wide")

# --- 2. 구글 API 통신 엔진 ---
def get_access_token():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds_info = dict(st.secrets["gcp_service_account"])
    creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    auth_request = google.auth.transport.requests.Request()
    creds.refresh(auth_request)
    return creds.token

def google_api_request(method, range_name, values=None):
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
    except: return None

@st.cache_data(ttl=2)
def load_data():
    main_rows = google_api_request("GET", "inventory_data!A:E")
    user_rows = google_api_request("GET", "사용자!A:C")
    
    # 데이터 로드 및 "신규 창고 개설" 필터링
    df = pd.DataFrame(main_rows[1:], columns=main_rows[0]) if main_rows else pd.DataFrame()
    if not df.empty:
        df = df[df.iloc[:, 1] != "신규 창고 개설"] # 품목명 기준 필터링
        df.iloc[:, 3] = pd.to_numeric(df.iloc[:, 3], errors='coerce').fillna(0).astype(int) # 수량 숫자화
        
    u_df = pd.DataFrame(user_rows[1:], columns=user_rows[0]) if user_rows else pd.DataFrame()
    return df, u_df

# --- 3. 실행 로직 ---
df, user_df = load_data()

if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "user_id": "", "role": ""})

if not st.session_state["logged_in"]:
    st.title("🏬 스마트 창고 로그인")
    with st.form("login"):
        id_i = st.text_input("아이디")
        pw_i = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인"):
            if not user_df.empty:
                u_row = user_df[(user_df.iloc[:, 0] == id_i) & (user_df.iloc[:, 1] == pw_i)]
                if not u_row.empty:
                    st.session_state.update({"logged_in": True, "user_id": id_i, "role": u_row.iloc[0, 2]})
                    st.rerun()
            st.error("계정 정보를 확인하세요.")
else:
    # 상단 메뉴
    tab1, tab2, tab3, tab4 = st.tabs(["🏠 통합 재고 현황", "📦 내 물품 관리", "📅 일정 달력", "⚙️ 설정/이력"])

    # --- 탭 1: 통합 재고 현황 (중복 제거 로직) ---
    with tab1:
        st.subheader("📊 실시간 통합 재고 (중복 합산)")
        if not df.empty:
            # 사용자+품목명+규격 기준으로 수량 합산
            summary_df = df.groupby([df.columns[0], df.columns[1], df.columns[2]])[df.columns[3]].sum().reset_index()
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
        else:
            st.info("표시할 재고 데이터가 없습니다.")

    # --- 탭 2: 내 물품 관리 (행별 입고/전송) ---
    with tab2:
        st.subheader("📥 내 재고 관리")
        my_df = df[df.iloc[:, 0] == st.session_state["user_id"]]
        
        for idx, row in my_df.iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 1, 2, 2])
                c1.write(f"**{row.iloc[1]}** ({row.iloc[2]})")
                c2.write(f"현재: {row.iloc[3]}개")
                
                with c3: # 입고 (기존 행 수정)
                    adj = st.number_input("입고량", 1, 500, 1, key=f"in_{idx}")
                    if st.button("➕ 입고", key=f"btn_in_{idx}"):
                        google_api_request("UPDATE", f"inventory_data!D{idx+2}", [[int(row.iloc[3]) + adj]])
                        google_api_request("APPEND", "이력!A:F", [[datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state['user_id'], "입고", row.iloc[1], adj, "-"]])
                        st.cache_data.clear(); st.rerun()
                
                with c4: # 전송 (내 재고 차감 + 상대방 행 추가/수정)
                    targets = [u for u in user_df.iloc[:, 0] if u != st.session_state['user_id']]
                    target = st.selectbox("전송 대상", targets, key=f"tg_{idx}")
                    s_amt = st.number_input("전송량", 1, int(row.iloc[3]), 1, key=f"s_v_{idx}")
                    if st.button("🚀 전송", key=f"btn_s_{idx}"):
                        # 1. 내 수량 차감
                        google_api_request("UPDATE", f"inventory_data!D{idx+2}", [[int(row.iloc[3]) - s_amt]])
                        # 2. 상대방에게 전송 (단순화를 위해 일단 APPEND 방식 유지하되 현황에서 합산)
                        google_api_request("APPEND", "inventory_data!A:D", [[target, row.iloc[1], row.iloc[2], s_amt]])
                        google_api_request("APPEND", "이력!A:F", [[datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state['user_id'], "전송", row.iloc[1], s_amt, target]])
                        st.cache_data.clear(); st.rerun()

    # --- 탭 3: 일정 달력 ---
    with tab3:
        calendar_url = "https://calendar.google.com/calendar/embed?src=ko.south_korea%23holiday%40group.v.calendar.google.com&ctz=Asia%2FSeoul"
        components.iframe(calendar_url, height=600)

    # --- 탭 4: 설정 및 이력 ---
    with tab4:
        st.subheader("📜 최근 작업 이력")
        logs = google_api_request("GET", "이력!A:F")
        if logs: st.table(pd.DataFrame(logs[1:], columns=logs[0]).iloc[::-1].head(15))