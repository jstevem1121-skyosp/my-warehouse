import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import google.auth.transport.requests
import requests
from datetime import datetime
import streamlit.components.v1 as components

# --- 1. 페이지 및 디자인 설정 ---
st.set_page_config(page_title="통합 관리 시스템 v7.0", layout="wide")

st.markdown("""
    <style>
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { height: 45px; white-space: pre-wrap; font-size: 14px; }
    thead tr th { background-color: #5d6d7e !important; color: white !important; }
    .as-form-box { border: 1px solid #ddd; padding: 20px; border-radius: 10px; background-color: #f9f9f9; }
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
    as_rows = google_api_request("GET", "as_data!A:J") # AS 데이터 추가
    
    inv_df = pd.DataFrame(inv_rows[1:], columns=inv_rows[0]) if inv_rows else pd.DataFrame()
    u_df = pd.DataFrame(user_rows[1:], columns=user_rows[0]) if user_rows else pd.DataFrame()
    as_df = pd.DataFrame(as_rows[1:], columns=as_rows[0]) if as_rows else pd.DataFrame()
    
    return inv_df, u_df, as_df

# --- 3. 메인 기능 구성 ---
inv_df, user_df, as_df = load_all_data()

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
    menu = st.sidebar.radio("대메뉴", ["🛠️ AS 관리", "📦 창고/재고 관리", "📅 일정/이력"])

    # --- [A] AS 관리 모듈 (이미지 ac1beb, a21b46 스타일) ---
    if menu == "🛠️ AS 관리":
        tab_as1, tab_as2 = st.tabs(["📝 AS 접수 글쓰기", "📋 AS 접수 현황"])
        
        with tab_as1:
            st.subheader("📝 AS 접수 신청")
            with st.container(border=True):
                c1, c2 = st.columns(2)
                ano = datetime.now().strftime("%y%m%d%H%M%S")
                adate = datetime.now().strftime("%Y-%m-%d")
                
                with c1:
                    st.text_input("접수번호", ano, disabled=True)
                    apt = st.selectbox("아파트명", ["아파트 선택", "고덕래미안힐스테이트", "공덕자이", "자양동스타시티"])
                    dong = st.text_input("동")
                with c2:
                    st.text_input("접수일자", adate, disabled=True)
                    user_nm = st.text_input("신청자명")
                    ho = st.text_input("호")
                
                phone = st.text_input("연락처 (예: 010-0000-0000)")
                
                st.write("**📍 고장위치 (중복 체크)**")
                loc_cols = st.columns(3)
                loc1 = loc_cols[0].checkbox("공용욕실")
                loc2 = loc_cols[1].checkbox("부부욕실")
                loc3 = loc_cols[2].checkbox("환기시스템")
                
                loc_text = f"{'공용 ' if loc1 else ''}{'부부 ' if loc2 else ''}{'환기' if loc3 else ''}"
                desc = st.text_area("상세 AS 내용", placeholder="고장 증상을 자세히 적어주세요.")
                
                if st.button("🚀 AS 접수하기", use_container_width=True):
                    new_as = [[ano, adate, apt, dong, ho, user_nm, phone, loc_text, desc, "신청"]]
                    google_api_request("APPEND", "as_data!A:J", new_as)
                    st.success("AS 접수가 완료되었습니다!"); st.cache_data.clear(); st.rerun()

        with tab_as2:
            st.subheader("📋 전체 AS 접수 현황")
            if not as_df.empty:
                st.dataframe(as_df.iloc[::-1], use_container_width=True, hide_index=True)
            else:
                st.info("접수된 내역이 없습니다.")

    # --- [B] 창고/재고 관리 모듈 (v6.4 2분할 구조 유지) ---
    elif menu == "📦 창고/재고 관리":
        col_l, col_r = st.columns([1, 1.8])
        with col_l:
            st.subheader("🏛️ 창고 목록")
            st.dataframe(user_df[[user_df.columns[0], user_df.columns[2]]], use_container_width=True, hide_index=True)
            target_u = st.selectbox("상세 조회", user_df.iloc[:, 0].unique())
        with col_r:
            st.subheader(f"📦 {target_u} 창고 상세")
            u_inv = inv_df[inv_df.iloc[:, 0] == target_u]
            if not u_inv.empty:
                summary = u_inv.groupby([inv_df.columns[1], inv_df.columns[2]])[inv_df.columns[3]].sum().reset_index()
                st.dataframe(summary, use_container_width=True, hide_index=True)

    # --- [C] 일정 및 이력 ---
    elif menu == "📅 일정/이력":
        tab_c1, tab_c2 = st.tabs(["📅 일정 달력", "📜 작업 이력"])
        with tab_c1:
            components.iframe("https://calendar.google.com/calendar/embed?src=ko.south_korea%23holiday%40group.v.calendar.google.com&ctz=Asia%2FSeoul", height=600)
        with tab_c2:
            logs = google_api_request("GET", "이력!A:F")
            if logs: st.dataframe(pd.DataFrame(logs[1:], columns=logs[0]).iloc[::-1], use_container_width=True)