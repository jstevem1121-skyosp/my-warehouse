import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import google.auth.transport.requests
import requests
from datetime import datetime

# --- 1. 디자인 설정 (이미지 스타일 재현) ---
st.set_page_config(page_title="창고 재고 현황 v6.3", layout="wide")

st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 24px; }
    .stTable { font-size: 12px; }
    .selected-row { background-color: #fde2e2 !important; } /* 선택된 행 강조 */
    thead tr th { background-color: #5d6d7e !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 구글 API 통신 (v6.2 엔진 사용) ---
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
        return True
    except: return None

@st.cache_data(ttl=2)
def load_data():
    main_rows = google_api_request("GET", "inventory_data!A:E")
    user_rows = google_api_request("GET", "사용자!A:C")
    
    # 데이터 정제: 합산 로직 적용
    df = pd.DataFrame(main_rows[1:], columns=main_rows[0]) if main_rows else pd.DataFrame()
    if not df.empty:
        df = df[df.iloc[:, 1] != "신규 창고 개설"]
        df.iloc[:, 3] = pd.to_numeric(df.iloc[:, 3], errors='coerce').fillna(0).astype(int)
    
    u_df = pd.DataFrame(user_rows[1:], columns=user_rows[0]) if user_rows else pd.DataFrame()
    return df, u_df

# --- 3. 메인 UI 구성 ---
df, user_df = load_data()

st.title("📂 창고 재고 관리 대시보드")

if not df.empty and not user_df.empty:
    # 상단 탭 (이미지 2 느낌 유지)
    tab1, tab2 = st.tabs(["🏛️ 창고별 현황", "📜 전체 이력 및 설정"])

    with tab1:
        # 화면을 왼쪽(목록)과 오른쪽(상세)으로 분할
        col_list, col_detail = st.columns([1, 1.5])

        with col_list:
            st.subheader("👥 사용자/창고 목록")
            # 사용자별 대표 정보 요약 (이미지 왼쪽 테이블 재현)
            user_list = user_df.iloc[:, 0].unique()
            
            # 선택창 (이미지의 클릭 효과를 위해 selectbox 사용)
            selected_user = st.selectbox("조회할 창고(사용자)를 선택하세요", user_list)
            
            # 왼쪽 테이블 출력 (이미지 ac13b3 느낌)
            st.dataframe(user_df[[user_df.columns[0], user_df.columns[2]]], 
                         use_container_width=True, hide_index=True)

        with col_detail:
            st.subheader(f"📦 {selected_user} 창고 세부 내역")
            # 선택된 사용자의 물품만 필터링 + 중복 합산
            target_df = df[df.iloc[:, 0] == selected_user]
            
            if not target_df.empty:
                # 품목/규격별로 합산하여 표시 (이미지 ac142b 오른쪽 테이블 재현)
                detail_summary = target_df.groupby([df.columns[1], df.columns[2]])[df.columns[3]].sum().reset_index()
                detail_summary.columns = ['품목명', '규격', '현재재고']
                
                # 수량 강조를 위한 스타일 적용
                st.dataframe(detail_summary, use_container_width=True, hide_index=True)
                
                # 추가 정보 (총 수량 등)
                total_stock = detail_summary['현재재고'].sum()
                st.metric("해당 창고 총 물량", f"{total_stock} 개")
            else:
                st.info("해당 창고에 보관된 물품이 없습니다.")

    with tab2:
        st.subheader("📅 최근 시스템 로그")
        # 시스템 이력 로드
        logs = google_api_request("GET", "이력!A:F")
        if logs:
            st.table(pd.DataFrame(logs[1:], columns=logs[0]).iloc[::-1].head(20))

else:
    st.warning("데이터를 불러오는 중입니다. 잠시만 기다려주세요.")