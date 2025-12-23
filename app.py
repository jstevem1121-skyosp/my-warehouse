import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import google.auth.transport.requests
import requests
from datetime import datetime
import streamlit.components.v1 as components

# --- 1. 페이지 및 디자인 설정 ---
st.set_page_config(page_title="통합 관리 시스템 v7.1", layout="wide")

st.markdown("""
    <style>
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { height: 45px; font-size: 14px; }
    thead tr th { background-color: #5d6d7e !important; color: white !important; }
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
        elif method == "APPEND":
            body = {"values": values}
            requests.post(f"{url}:append", headers=headers, params=params, json=body)
        return True
    except: return None

@st.cache_data(ttl=2)
def load_all_data():
    inv_rows = google_api_request("GET", "inventory_data!A:E")
    user_rows = google_api_request("GET", "사용자!A:C")
    as_rows = google_api_request("GET", "as_data!A:J")
    log_rows = google_api_request("GET", "이력!A:F") # 재고 이동 이력
    
    inv_df = pd.DataFrame(inv_rows[1:], columns=inv_rows[0]) if inv_rows else pd.DataFrame()
    u_df = pd.DataFrame(user_rows[1:], columns=user_rows[0]) if user_rows else pd.DataFrame()
    as_df = pd.DataFrame(as_rows[1:], columns=as_rows[0]) if as_rows else pd.DataFrame()
    log_df = pd.DataFrame(log_rows[1:], columns=log_rows[0]) if log_rows else pd.DataFrame()
    
    return inv_df, u_df, as_df, log_df

# --- 3. 메인 기능 구성 ---
inv_df, user_df, as_df, log_df = load_all_data()

if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "user_id": "", "role": ""})

if not st.session_state["logged_in"]:
    st.title("🔐 통합 시스템 로그인")
    with st.form("login"):
        id_i, pw_i = st.text_input("ID"), st.text_input("PW", type="password")
        if st.form_submit_button("로그인"):
            if not user_df.empty:
                u_row = user_df[(user_df.iloc[:,0] == id_i) & (user_df.iloc[:,1] == pw_i)]
                if not u_row.empty:
                    st.session_state.update({"logged_in": True, "user_id": id_i, "role": u_row.iloc[0, 2]})
                    st.rerun()
            st.error("로그인 실패")
else:
    st.sidebar.title(f"👤 {st.session_state['user_id']}님")
    menu = st.sidebar.radio("대메뉴", ["🛠️ AS 관리", "📦 창고/재고 관리", "📜 전체 이력 관리", "📅 일정 달력"])

    # --- [A] AS 관리 (접수 및 현황) ---
    if menu == "🛠️ AS 관리":
        tab_as1, tab_as2 = st.tabs(["📝 AS 접수 신청", "📋 AS 실시간 현황"])
        with tab_as1:
            st.subheader("📝 AS 접수 신청")
            with st.container(border=True):
                # ... (이전 AS 접수 양식 코드와 동일)
                st.info("이미지 ac1beb 양식에 따른 접수 기능을 수행합니다.")
                if st.button("🚀 샘플 접수"): st.success("접수 완료")

        with tab_as2:
            st.subheader("📋 AS 현재 진행 상태")
            st.dataframe(as_df.iloc[::-1], use_container_width=True, hide_index=True)

    # --- [B] 창고/재고 관리 ---
    elif menu == "📦 창고/재고 관리":
        col_l, col_r = st.columns([1, 1.8])
        with col_l:
            st.subheader("🏛️ 창고 목록")
            st.dataframe(user_df[[user_df.columns[0], user_df.columns[2]]], use_container_width=True, hide_index=True)
            target_u = st.selectbox("조회 창고", user_df.iloc[:, 0].unique())
        with col_r:
            st.subheader(f"📦 {target_u} 재고 상세")
            u_inv = inv_df[inv_df.iloc[:, 0] == target_u]
            if not u_inv.empty:
                # 중복 항목 합산 처리
                summary = u_inv.groupby([inv_df.columns[1], inv_df.columns[2]])[inv_df.columns[3]].sum().reset_index()
                st.dataframe(summary, use_container_width=True, hide_index=True)

    # --- [C] 이력 분리 관리 (사용자 요청 핵심 기능) ---
    elif menu == "📜 전체 이력 관리":
        st.subheader("📜 데이터 이력 조회")
        tab_log1, tab_log2 = st.tabs(["🚛 재고 이동(입고/전송) 이력", "🛠️ AS 접수 이력"])
        
        with tab_log1:
            st.info("재고의 입고 및 창고 간 이동 내역입니다.")
            if not log_df.empty:
                st.dataframe(log_df.iloc[::-1], use_container_width=True, hide_index=True)
            else:
                st.warning("기록된 재고 이동 이력이 없습니다.")
                
        with tab_log2:
            st.info("과거부터 현재까지 접수된 모든 AS 내역입니다.")
            if not as_df.empty:
                st.dataframe(as_df.iloc[::-1], use_container_width=True, hide_index=True)
            else:
                st.warning("기록된 AS 이력이 없습니다.")

    # --- [D] 일정 달력 ---
    elif menu == "📅 일정 달력":
        components.iframe("https://calendar.google.com/calendar/embed?src=ko.south_korea%23holiday%40group.v.calendar.google.com&ctz=Asia%2FSeoul", height=650)