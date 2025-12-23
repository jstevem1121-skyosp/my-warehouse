import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import google.auth.transport.requests
import requests
from datetime import datetime
import streamlit.components.v1 as components

# --- 1. 페이지 설정 및 전문 디자인 ---
st.set_page_config(page_title="통합 창고 관리 시스템", layout="wide")

st.markdown("""
    <style>
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { 
        height: 50px; background-color: #f0f2f6; border-radius: 5px 5px 0 0; padding: 10px;
    }
    .stTabs [aria-selected="true"] { background-color: #5d6d7e !important; color: white !important; }
    thead tr th { background-color: #5d6d7e !important; color: white !important; }
    .main { background-color: #ffffff; }
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
    if not df.empty:
        df = df[df.iloc[:, 1] != "신규 창고 개설"] #
        df.iloc[:, 3] = pd.to_numeric(df.iloc[:, 3], errors='coerce').fillna(0).astype(int)
    u_df = pd.DataFrame(user_rows[1:], columns=user_rows[0]) if user_rows else pd.DataFrame()
    return df, u_df

# --- 3. 메인 로직 ---
df, user_df = load_data()

if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "user_id": "", "role": ""})

if not st.session_state["logged_in"]:
    st.title("🔐 시스템 로그인")
    with st.form("login"):
        id_i = st.text_input("아이디")
        pw_i = st.text_input("비밀번호", type="password")
        if st.form_submit_button("접속"):
            if not user_df.empty:
                u_row = user_df[(user_df.iloc[:, 0] == id_i) & (user_df.iloc[:, 1] == pw_i)]
                if not u_row.empty:
                    st.session_state.update({"logged_in": True, "user_id": id_i, "role": u_row.iloc[0, 2]})
                    st.rerun()
            st.error("로그인 실패")
else:
    # 상단 헤더
    h1, h2 = st.columns([8, 2])
    h1.title("🏢 창고 통합 관리 대시보드")
    if h2.button("로그아웃"):
        st.session_state["logged_in"] = False
        st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(["🏛️ 창고별 재고현황", "📅 일정 달력", "📜 작업 이력", "⚙️ 시스템 설정"])

    # --- 탭 1: 2분할 창고 현황 (이미지 ac142b 스타일) ---
    with tab1:
        col_list, col_detail = st.columns([1, 1.8])
        
        with col_list:
            st.subheader("👥 창고 목록")
            # 왼쪽 테이블: 사용자 리스트 (이미지 ac13b3 재현)
            st.dataframe(user_df[[user_df.columns[0], user_df.columns[2]]], use_container_width=True, hide_index=True)
            selected_user = st.selectbox("상세 조회할 창고 선택", user_df.iloc[:, 0].unique())

        with col_detail:
            st.subheader(f"📦 {selected_user} 창고 상세")
            # 선택된 창고의 물품 합산 표시
            u_df_filtered = df[df.iloc[:, 0] == selected_user]
            if not u_df_filtered.empty:
                # 합산된 데이터프레임 생성
                summary = u_df_filtered.groupby([df.columns[1], df.columns[2]])[df.columns[3]].sum().reset_index()
                st.dataframe(summary, use_container_width=True, hide_index=True)
                
                # 본인 창고일 경우 관리 기능 활성화
                if selected_user == st.session_state["user_id"]:
                    with st.expander("🛠️ 내 재고 입고/전송 관리"):
                        for idx, row in u_df_filtered.iterrows():
                            c1, c2, c3 = st.columns([2, 2, 3])
                            c1.write(f"**{row.iloc[1]}**")
                            with c2:
                                amt = st.number_input("수량", 1, 500, 1, key=f"amt_{idx}")
                                if st.button("➕ 입고", key=f"in_{idx}"):
                                    google_api_request("UPDATE", f"inventory_data!D{idx+2}", [[int(row.iloc[3]) + amt]])
                                    google_api_request("APPEND", "이력!A:F", [[datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state['user_id'], "입고", row.iloc[1], amt, "-"]])
                                    st.cache_data.clear(); st.rerun()
                            with c3:
                                target = st.selectbox("전송지", [u for u in user_df.iloc[:, 0] if u != selected_user], key=f"t_{idx}")
                                if st.button("🚀 전송", key=f"s_{idx}"):
                                    google_api_request("UPDATE", f"inventory_data!D{idx+2}", [[int(row.iloc[3]) - amt]])
                                    google_api_request("APPEND", "inventory_data!A:D", [[target, row.iloc[1], row.iloc[2], amt]])
                                    st.cache_data.clear(); st.rerun()
            else:
                st.info("재고가 없습니다.")

    # --- 탭 2: 일정 달력 ---
    with tab2:
        components.iframe("https://calendar.google.com/calendar/embed?src=ko.south_korea%23holiday%40group.v.calendar.google.com&ctz=Asia%2FSeoul", height=650)

    # --- 탭 3: 작업 이력 ---
    with tab3:
        st.subheader("📜 최근 시스템 로그")
        log_data = google_api_request("GET", "이력!A:F")
        if log_data:
            st.dataframe(pd.DataFrame(log_data[1:], columns=log_data[0]).iloc[::-1], use_container_width=True, hide_index=True)

    # --- 탭 4: 시스템 설정 ---
    with tab4:
        c_reg, c_user = st.columns(2)
        with c_reg:
            st.subheader("🆕 신규 품목 등록")
            with st.form("new_i"):
                n, s, q = st.text_input("품목명"), st.text_input("규격"), st.number_input("수량", 0)
                if st.form_submit_button("등록"):
                    google_api_request("APPEND", "inventory_data!A:D", [[st.session_state['user_id'], n, s, q]])
                    st.cache_data.clear(); st.rerun()
        with c_user:
            if st.session_state["role"] == "admin":
                st.subheader("👥 신규 계정 생성")
                with st.form("new_u"):
                    u, p = st.text_input("ID"), st.text_input("PW")
                    if st.form_submit_button("생성"):
                        google_api_request("APPEND", "사용자!A:C", [[u, p, "user"]])
                        st.success("완료"); st.rerun()