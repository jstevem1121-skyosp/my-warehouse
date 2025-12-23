import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import google.auth.transport.requests
import requests
from datetime import datetime
import streamlit.components.v1 as components

# --- 1. 페이지 설정 및 디자인 ---
st.set_page_config(page_title="재고관리 대시보드 v6.1", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; font-size: 16px; }
    </style>
    """, unsafe_allow_html=True)

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
    df = pd.DataFrame(main_rows[1:], columns=main_rows[0]) if main_rows else pd.DataFrame()
    u_df = pd.DataFrame(user_rows[1:], columns=user_rows[0]) if user_rows else pd.DataFrame()
    return df, u_df

# --- 3. 메인 실행부 ---
df, user_df = load_data()

if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "user_id": "", "role": ""})

if not st.session_state["logged_in"]:
    st.title("🏬 재고 관리 시스템")
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        with st.form("login_form"):
            st.subheader("로그인")
            id_i = st.text_input("아이디")
            pw_i = st.text_input("비밀번호", type="password")
            if st.form_submit_button("접속하기"):
                if not user_df.empty:
                    u_cols = list(user_df.columns)
                    u_row = user_df[(user_df[u_cols[0]] == id_i) & (user_df[u_cols[1]] == pw_i)]
                    if not u_row.empty:
                        st.session_state.update({"logged_in": True, "user_id": id_i, "role": u_row.iloc[0][u_cols[2]]})
                        st.rerun()
                st.error("정보가 일치하지 않습니다.")
else:
    # 상단 대시보드 헤더
    t1, t2 = st.columns([8, 2])
    with t1:
        st.title("📋 재고 통합 대시보드")
    with t2:
        st.write(f"**{st.session_state['user_id']}**님 ({st.session_state['role']})")
        if st.button("로그아웃"):
            st.session_state.update({"logged_in": False})
            st.rerun()

    # 상단 메뉴 탭 구성 (일정 달력 추가)
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏠 전체 현황", "📦 내 재고 관리", "📅 일정 달력", "📜 작업 이력", "⚙️ 시스템 관리"])

    cols = list(df.columns) if not df.empty else []

    # --- 탭 1: 전체 현황 ---
    with tab1:
        st.subheader("실시간 재고 데이터 리스트")
        if not df.empty:
            search = st.text_input("🔍 검색 (품목명 또는 사용자)", "")
            display_df = df[df[cols[1]].str.contains(search, na=False) | df[cols[0]].str.contains(search, na=False)]
            st.dataframe(display_df, use_container_width=True, hide_index=True)

    # --- 탭 2: 내 재고 관리 ---
    with tab2:
        my_df = df[df[cols[0]] == st.session_state["user_id"]]
        st.subheader(f"내 물품 리스트 ({len(my_df)}건)")
        for idx, row in my_df.iterrows():
            if row[cols[1]] == "신규 창고 개설": continue
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2,1,2,2])
                c1.write(f"**{row[cols[1]]}**\n\n{row[cols[2]]}")
                c2.metric("수량", f"{row[cols[3]]}개")
                with c3:
                    adj = st.number_input("조정 수량", 1, 500, 1, key=f"adj_{idx}")
                    if st.button("📥 입고", key=f"in_{idx}"):
                        google_api_request("UPDATE", f"inventory_data!D{idx+2}", [[int(row[cols[3]]) + adj]])
                        google_api_request("APPEND", "이력!A:F", [[datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state['user_id'], "입고", row[cols[1]], adj, "-"]])
                        st.cache_data.clear(); st.rerun()
                with c4:
                    targets = [u for u in user_df[user_df.columns[0]] if u != st.session_state['user_id']]
                    target = st.selectbox("전송 대상", targets, key=f"tg_{idx}")
                    s_amt = st.number_input("전송 수량", 1, int(row[cols[3]]), 1, key=f"s_{idx}")
                    if st.button("🚀 전송", key=f"send_{idx}"):
                        google_api_request("UPDATE", f"inventory_data!D{idx+2}", [[int(row[cols[3]]) - s_amt]])
                        google_api_request("APPEND", "inventory_data!A:D", [[target, row[cols[1]], row[cols[2]], s_amt]])
                        google_api_request("APPEND", "이력!A:F", [[datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state['user_id'], "전송", row[cols[1]], s_amt, target]])
                        st.cache_data.clear(); st.rerun()

    # --- 탭 3: 일정 달력 (복구 완료) ---
    with tab3:
        st.subheader("📅 업무 및 공휴일 일정")
        calendar_url = "https://calendar.google.com/calendar/embed?src=ko.south_korea%23holiday%40group.v.calendar.google.com&ctz=Asia%2FSeoul"
        components.iframe(calendar_url, height=700)

    # --- 탭 4: 작업 이력 ---
    with tab4:
        st.subheader("시스템 로그")
        logs = google_api_request("GET", "이력!A:F")
        if logs:
            st.table(pd.DataFrame(logs[1:], columns=logs[0]).iloc[::-1].head(30))

    # --- 탭 5: 시스템 관리 ---
    with tab5:
        col_reg1, col_reg2 = st.columns(2)
        with col_reg1:
            st.write("### 🆕 새 품목 등록")
            with st.form("new_item"):
                n = st.text_input("품목명")
                s = st.text_input("규격")
                q = st.number_input("초기 수량", 0)
                if st.form_submit_button("등록"):
                    google_api_request("APPEND", "inventory_data!A:D", [[st.session_state['user_id'], n, s, q]])
                    st.cache_data.clear(); st.rerun()
        with col_reg2:
            if st.session_state["role"] == "admin":
                st.write("### 👥 계정 관리 (관리자 전용)")
                with st.form("new_user"):
                    new_id = st.text_input("아이디")
                    new_pw = st.text_input("비밀번호")
                    if st.form_submit_button("계정 생성"):
                        google_api_request("APPEND", "사용자!A:C", [[new_id, new_pw, "user"]])
                        google_api_request("APPEND", "inventory_data!A:D", [[new_id, "신규 창고 개설", "-", 0]])
                        st.success(f"{new_id} 계정이 생성되었습니다."); st.rerun()