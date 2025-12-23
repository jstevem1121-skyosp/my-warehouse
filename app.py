import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import google.auth.transport.requests
import requests
from datetime import datetime

# --- 1. 페이지 설정 및 디자인 ---
st.set_page_config(page_title="재고관리 대시보드", layout="wide")

# 웹 사이트 느낌을 주기 위한 커스텀 CSS
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; }
    .reportview-container .main .block-container { padding-top: 1rem; }
    th { background-color: #f0f2f6 !important; }
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

# --- 3. 앱 로직 ---
df, user_df = load_data()

if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "user_id": "", "role": ""})

# [로그인 화면]
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

# [메인 대시보드 화면]
else:
    # 상단 헤더 영역 (두 번째 이미지 느낌)
    t1, t2 = st.columns([8, 2])
    with t1:
        st.title("📋 재고 통합 대시보드")
    with t2:
        st.write(f"**{st.session_state['user_id']}**님 접속 중")
        if st.button("로그아웃"):
            st.session_state.update({"logged_in": False})
            st.rerun()

    # 상단 메뉴 탭 (이미지의 메뉴 바 형태)
    tab1, tab2, tab3, tab4 = st.tabs(["🏠 전체 현황", "📦 내 재고 관리", "📜 작업 이력", "⚙️ 시스템 관리"])

    cols = list(df.columns) if not df.empty else []

    # --- 탭 1: 전체 현황 (표 형식) ---
    with tab1:
        st.subheader("전체 재고 리스트")
        if not df.empty:
            # 검색 기능
            search = st.text_input("🔍 품목명 또는 사용자 검색", "")
            display_df = df[df[cols[1]].str.contains(search) | df[cols[0]].str.contains(search)]
            
            # 실제 표 출력
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # 관리자 회수 섹션 (선택형)
            if st.session_state["role"] == "admin":
                with st.expander("🛠️ 관리자 긴급 회수"):
                    target_row = st.selectbox("회수할 행 선택", display_df.index)
                    r_amt = st.number_input("회수 수량", 1, value=1)
                    if st.button("즉시 회수 실행"):
                        orig_qty = int(display_df.loc[target_row, cols[3]])
                        google_api_request("UPDATE", f"inventory_data!D{target_row+2}", [[orig_qty - r_amt]])
                        st.cache_data.clear(); st.rerun()

    # --- 탭 2: 내 재고 관리 (이미지 1의 기능을 세련되게) ---
    with tab2:
        my_df = df[df[cols[0]] == st.session_state["user_id"]]
        st.subheader(f"내 보유 품목 ({len(my_df)}건)")
        
        for idx, row in my_df.iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2,1,2,2])
                c1.write(f"**{row[cols[1]]}** ({row[cols[2]]})")
                c2.write(f"현재: **{row[cols[3]]}**개")
                with c3:
                    adj = st.number_input("입고량", 1, 100, 1, key=f"in_val_{idx}")
                    if st.button("📥 입고하기", key=f"in_btn_{idx}"):
                        google_api_request("UPDATE", f"inventory_data!D{idx+2}", [[int(row[cols[3]]) + adj]])
                        google_api_request("APPEND", "이력!A:F", [[datetime.now().strftime("%m-%d %H:%M"), st.session_state['user_id'], "입고", row[cols[1]], adj, "-"]])
                        st.cache_data.clear(); st.rerun()
                with c4:
                    target = st.selectbox("전송 대상", [u for u in user_df[user_df.columns[0]] if u != st.session_state['user_id']], key=f"tg_{idx}")
                    s_amt = st.number_input("전송량", 1, int(row[cols[3]]), 1, key=f"s_val_{idx}")
                    if st.button("🚀 전송하기", key=f"s_btn_{idx}"):
                        google_api_request("UPDATE", f"inventory_data!D{idx+2}", [[int(row[cols[3]]) - s_amt]])
                        google_api_request("APPEND", "inventory_data!A:D", [[target, row[cols[1]], row[cols[2]], s_amt]])
                        st.cache_data.clear(); st.rerun()

    # --- 탭 3: 이력 조회 ---
    with tab3:
        st.subheader("최근 작업 이력")
        logs = google_api_request("GET", "이력!A:F")
        if logs:
            log_df = pd.DataFrame(logs[1:], columns=logs[0])
            st.table(log_df.iloc[::-1].head(20))

    # --- 탭 4: 시스템 관리 ---
    with tab4:
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
                st.write("### 👥 계정 생성")
                with st.form("new_user"):
                    new_id = st.text_input("아이디")
                    new_pw = st.text_input("비밀번호")
                    if st.form_submit_button("계정 만들기"):
                        google_api_request("APPEND", "사용자!A:C", [[new_id, new_pw, "user"]])
                        st.success("생성 완료"); st.rerun()