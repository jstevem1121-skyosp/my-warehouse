import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import google.auth.transport.requests
import requests
from datetime import datetime
import streamlit.components.v1 as components

# --- 1. 페이지 및 디자인 설정 ---
st.set_page_config(page_title="통합 관리 시스템 v7.4", layout="wide")

st.markdown("""
    <style>
    /* 상단 메뉴바 및 탭 스타일 */
    .nav-bar { display: flex; gap: 20px; font-weight: bold; border-bottom: 2px solid #00bcd4; padding-bottom: 10px; margin-bottom: 20px; font-size: 14px; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { 
        height: 50px; 
        font-size: 16px; 
        font-weight: bold; 
        background-color: #f0f2f6; 
        border-radius: 5px 5px 0 0;
        padding: 0 30px;
    }
    .stTabs [aria-selected="true"] { background-color: #00bcd4 !important; color: white !important; }
    /* 테이블 헤더 */
    thead tr th { background-color: #5d6d7e !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 구글 API 엔진 ---
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
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers)
            return resp.json().get('values', [])
        elif method == "APPEND":
            requests.post(f"{url}:append", headers=headers, params={"valueInputOption": "USER_ENTERED"}, json={"values": values})
        return True
    except: return None

@st.cache_data(ttl=2)
def load_all_data():
    inv_rows = google_api_request("GET", "inventory_data!A:E")
    user_rows = google_api_request("GET", "사용자!A:C")
    as_rows = google_api_request("GET", "as_data!A:J")
    log_rows = google_api_request("GET", "이력!A:F")
    return (pd.DataFrame(inv_rows[1:], columns=inv_rows[0]) if inv_rows else pd.DataFrame(),
            pd.DataFrame(user_rows[1:], columns=user_rows[0]) if user_rows else pd.DataFrame(),
            pd.DataFrame(as_rows[1:], columns=as_rows[0]) if as_rows else pd.DataFrame(),
            pd.DataFrame(log_rows[1:], columns=log_rows[0]) if log_rows else pd.DataFrame())

# --- 3. 메인 화면 구성 ---
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
else:
    st.sidebar.title(f"👤 {st.session_state['user_id']}님")
    menu = st.sidebar.radio("메뉴 선택", ["🛠️ AS 관리", "📦 창고/재고 관리", "📜 전체 이력 관리", "📅 일정 달력"])

    st.markdown('<div class="nav-bar"><span>HOME</span> | <span style="color: #00bcd4;">A/S접수시스템</span> | <span>통합재고현황</span></div>', unsafe_allow_html=True)

    # --- [A] AS 관리 (사용자 요청: 탭 분리) ---
    if menu == "🛠️ AS 관리":
        # 접수신청과 접수현황을 탭으로 분리
        tab_write, tab_list = st.tabs(["📝 AS 접수 신청 (글쓰기)", "📋 AS 접수 현황 (조회)"])
        
        with tab_write:
            st.markdown("### < A/S접수현황 글쓰기")
            with st.form("as_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                ano = datetime.now().strftime("%y%m%d%H%M%S")
                col1.text_input("접수번호*", value=ano, disabled=True)
                col2.text_input("접수일자*", value=datetime.now().strftime("%Y-%m-%d"), disabled=True)
                
                apt = st.selectbox("아파트명*", ["아파트를 선택하세요", "고덕래미안힐스테이트", "공덕자이", "자양동스타시티"])
                c1, c2 = st.columns(2)
                dong = c1.text_input("동*")
                ho = c2.text_input("호*")
                
                name = st.text_input("신청자명*")
                phone = st.text_input("연락처*")
                
                st.write("**고장위치**")
                lc1, lc2, lc3 = st.columns(3)
                l1, l2, l3 = lc1.checkbox("공용욕실"), lc2.checkbox("부부욕실"), lc3.checkbox("환기시스템")
                
                desc = st.text_area("AS 내용", placeholder="AS를 신청합니다")
                
                if st.form_submit_button("🚀 AS 접수하기", use_container_width=True):
                    loc_val = f"{'공용 ' if l1 else ''}{'부부 ' if l2 else ''}{'환기' if l3 else ''}"
                    google_api_request("APPEND", "as_data!A:J", [[ano, datetime.now().strftime("%Y-%m-%d"), apt, dong, ho, name, phone, loc_val, desc, "신청"]])
                    st.success("AS 접수가 완료되었습니다!"); st.cache_data.clear(); st.rerun()

        with tab_list:
            st.markdown(f"### < A/S접수현황 (Total: {len(as_df)}건)")
            if not as_df.empty:
                st.dataframe(as_df.iloc[::-1], use_container_width=True, hide_index=True)
            else:
                st.info("접수된 내역이 없습니다.")

    # --- [B] 창고/재고 관리 ---
    elif menu == "📦 창고/재고 관리":
        col_l, col_r = st.columns([1, 1.8])
        with col_l:
            st.subheader("🏛️ 창고 목록")
            st.dataframe(user_df[[user_df.columns[0], user_df.columns[2]]], use_container_width=True, hide_index=True)
            target_u = st.selectbox("조회 창고", user_df.iloc[:, 0].unique() if not user_df.empty else ["없음"])
        with col_r:
            st.subheader(f"📦 {target_u} 재고 상세")
            u_inv = inv_df[inv_df.iloc[:, 0] == target_u]
            if not u_inv.empty:
                summary = u_inv.groupby([inv_df.columns[1], inv_df.columns[2]])[inv_df.columns[3]].sum().reset_index()
                st.dataframe(summary, use_container_width=True, hide_index=True)

    # --- [C] 전체 이력 관리 ---
    elif menu == "📜 전체 이력 관리":
        st.subheader("📜 데이터 이력 조회")
        t1, t2 = st.tabs(["🚛 재고 이동 이력", "🛠️ AS 접수 이력"])
        with t1: st.dataframe(log_df.iloc[::-1], use_container_width=True, hide_index=True)
        with t2: st.dataframe(as_df.iloc[::-1], use_container_width=True, hide_index=True)

    # --- [D] 일정 달력 ---
    elif menu == "📅 일정 달력":
        components.iframe("https://calendar.google.com/calendar/embed?src=ko.south_korea%23holiday%40group.v.calendar.google.com&ctz=Asia%2FSeoul", height=650)