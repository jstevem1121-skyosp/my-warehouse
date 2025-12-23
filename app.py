import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import google.auth.transport.requests
import requests
from datetime import datetime
import streamlit.components.v1 as components

# --- 1. 페이지 설정 및 디자인 (이미지 스타일 유지) ---
st.set_page_config(page_title="통합 관리 시스템 v7.8", layout="wide")

st.markdown("""
    <style>
    .nav-bar { display: flex; gap: 20px; font-weight: bold; border-bottom: 2px solid #00bcd4; padding-bottom: 10px; margin-bottom: 20px; font-size: 14px; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { 
        height: 50px; font-size: 15px; font-weight: bold; 
        background-color: #f0f2f6; border-radius: 5px 5px 0 0; padding: 0 25px;
    }
    .stTabs [aria-selected="true"] { background-color: #5d6d7e !important; color: white !important; }
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
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers)
            return resp.json().get('values', [])
        elif method == "APPEND":
            requests.post(f"{url}:append", headers=headers, params={"valueInputOption": "USER_ENTERED"}, json={"values": values})
        elif method == "UPDATE":
            requests.put(url, headers=headers, params={"valueInputOption": "USER_ENTERED"}, json={"values": values})
        return True
    except: return None

@st.cache_data(ttl=2)
def load_all_data():
    inv_rows = google_api_request("GET", "inventory_data!A:E")
    user_rows = google_api_request("GET", "사용자!A:C")
    as_rows = google_api_request("GET", "as_data!A:J")
    log_rows = google_api_request("GET", "이력!A:F")
    
    # 데이터프레임 변환 (AS 컬럼명 명시)
    as_cols = ['접수번호', '날짜', '아파트명', '동', '호', '신청자명', '연락처', '위치', '내용', '상태']
    return (pd.DataFrame(inv_rows[1:], columns=inv_rows[0]) if inv_rows else pd.DataFrame(),
            pd.DataFrame(user_rows[1:], columns=user_rows[0]) if user_rows else pd.DataFrame(),
            pd.DataFrame(as_rows[1:], columns=as_cols) if len(as_rows) > 1 else pd.DataFrame(columns=as_cols),
            pd.DataFrame(log_rows[1:], columns=log_rows[0]) if log_rows else pd.DataFrame())

# --- 3. 메인 기능 ---
inv_df, user_df, as_df, log_df = load_all_data()

if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "user_id": "", "role": ""})

if not st.session_state["logged_in"]:
    st.title("🔐 통합 관리 시스템 로그인")
    with st.form("login"):
        id_i, pw_i = st.text_input("ID"), st.text_input("PW", type="password")
        if st.form_submit_button("접속"):
            if not user_df.empty:
                u_row = user_df[(user_df.iloc[:,0] == id_i) & (user_df.iloc[:,1] == pw_i)]
                if not u_row.empty:
                    st.session_state.update({"logged_in": True, "user_id": id_i, "role": u_row.iloc[0, 2]})
                    st.rerun()
            st.error("로그인 정보가 올바르지 않습니다.")
else:
    st.sidebar.title(f"👤 {st.session_state['user_id']}님")
    menu = st.sidebar.radio("메뉴 선택", ["🛠️ AS 관리", "📦 창고/재고 관리", "📜 전체 이력 관리", "📅 일정 달력"])
    if st.sidebar.button("로그아웃"):
        st.session_state["logged_in"] = False
        st.rerun()

    st.markdown('<div class="nav-bar"><span>HOME</span> | <span style="color: #00bcd4;">통합 대시보드</span></div>', unsafe_allow_html=True)

    # --- [A] AS 관리 (접수 탭 / 현황 탭) ---
    if menu == "🛠️ AS 관리":
        tab_write, tab_view = st.tabs(["📝 AS 접수 신청", "📋 AS 현황 및 상태관리"])
        
        with tab_write:
            st.markdown("### < A/S 접수 신청")
            with st.form("as_form", clear_on_submit=True):
                ano = datetime.now().strftime("%y%m%d%H%M%S")
                c1, c2 = st.columns(2)
                c1.text_input("접수번호*", value=ano, disabled=True)
                c2.text_input("접수일자*", value=datetime.now().strftime("%Y-%m-%d"), disabled=True)
                apt = st.selectbox("아파트명*", ["선택하세요", "고덕래미안힐스테이트", "공덕자이", "자양동스타시티"])
                dong, ho = st.columns(2)
                d_val = dong.text_input("동*")
                h_val = ho.text_input("호*")
                name = st.text_input("신청자명*")
                phone = st.text_input("연락처*")
                lc1, lc2, lc3 = st.columns(3)
                l1 = lc1.checkbox("공용욕실")
                l2 = lc2.checkbox("부부욕실")
                l3 = lc3.checkbox("환기시스템")
                desc = st.text_area("상세 내용")
                if st.form_submit_button("🚀 접수하기", use_container_width=True):
                    loc = f"{'공용 ' if l1 else ''}{'부부 ' if l2 else ''}{'환기' if l3 else ''}"
                    google_api_request("APPEND", "as_data!A:J", [[ano, datetime.now().strftime("%Y-%m-%d"), apt, d_val, h_val, name, phone, loc, desc, "신청"]])
                    st.cache_data.clear(); st.rerun()

        with tab_view:
            st.markdown(f"### < A/S 접수 현황 (총 {len(as_df)}건)")
            # [이미지 a21b46 스타일 필터]
            with st.expander("🔍 검색 필터", expanded=False):
                f1, f2 = st.columns(2)
                s_name = f1.text_input("신청자명 검색")
                s_apt = f2.selectbox("아파트명 필터", ["전체"] + list(as_df['아파트명'].unique()))
            
            view_df = as_df.copy()
            if s_name: view_df = view_df[view_df['신청자명'].str.contains(s_name)]
            if s_apt != "전체": view_df = view_df[view_df['아파트명'] == s_apt]
            
            st.dataframe(view_df.iloc[::-1], use_container_width=True, hide_index=True)
            
            # [상태 관리 기능]
            st.write("---")
            st.subheader("⚙️ AS 진행 상태 변경")
            u_c1, u_c2, u_c3 = st.columns([2, 2, 1])
            target_no = u_c1.selectbox("변경할 접수번호", view_df['접수번호'].tolist() if not view_df.empty else ["없음"])
            new_stat = u_c2.selectbox("새로운 상태", ["신청", "진행중", "완료", "취소"])
            if u_c3.button("상태 업데이트"):
                raw_as = google_api_request("GET", "as_data!A:A")
                for i, row in enumerate(raw_as):
                    if row[0] == target_no:
                        google_api_request("UPDATE", f"as_data!J{i+1}", [[new_stat]])
                        break
                st.cache_data.clear(); st.rerun()

    # --- [B] 창고 관리 (2분할 레이아웃) ---
    elif menu == "📦 창고/재고 관리":
        col_l, col_r = st.columns([1, 2])
        with col_l:
            st.subheader("🏛️ 창고 목록")
            st.dataframe(user_df[[user_df.columns[0], user_df.columns[2]]], use_container_width=True, hide_index=True)
            target_u = st.selectbox("조회 창고", user_df.iloc[:, 0].unique())
        with col_r:
            st.subheader(f"📦 {target_u} 재고 상세")
            u_inv = inv_df[inv_df.iloc[:, 0] == target_u]
            if not u_inv.empty:
                # 중복 항목 합산 처리
                summary = u_inv.groupby([inv_df.columns[1], inv_df.columns[2]])[inv_df.columns[3].name].sum().reset_index()
                st.dataframe(summary, use_container_width=True, hide_index=True)

    # --- [C] 이력 관리 (재고 이동 vs AS 접수) ---
    elif menu == "📜 전체 이력 관리":
        st.subheader("📜 데이터 이력 조회")
        t1, t2 = st.tabs(["🚛 재고 이동(입고/전송) 이력", "🛠️ AS 접수 이력"])
        with t1: st.dataframe(log_df.iloc[::-1], use_container_width=True, hide_index=True)
        with t2: st.dataframe(as_df.iloc[::-1], use_container_width=True, hide_index=True)

    # --- [D] 일정 달력 ---
    elif menu == "📅 일정 달력":
        components.iframe("https://calendar.google.com/calendar/embed?src=ko.south_korea%23holiday%40group.v.calendar.google.com&ctz=Asia%2FSeoul", height=650)