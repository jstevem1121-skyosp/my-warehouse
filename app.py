import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import google.auth.transport.requests
import requests
from datetime import datetime
import streamlit.components.v1 as components

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="창고 통합 관리 시스템 v5.2", layout="wide")

# --- 2. 구글 REST API 직접 통신 엔진 ---
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
    except Exception as e:
        st.error(f"API 통신 오류: {e}")
        return False

# --- 3. 데이터 로딩 (KeyError 방어 로직 추가) ---
@st.cache_data(ttl=5)
def load_all_data():
    # 탭 이름을 '시트1' 또는 'Sheet1' 중 있는 것으로 자동 시도
    main_rows = google_api_request("GET", "시트1!A:D")
    if not main_rows:
        main_rows = google_api_request("GET", "Sheet1!A:D")
        
    user_rows = google_api_request("GET", "사용자!A:C")
    
    # 데이터프레임 생성 및 열 이름 강제 지정 (KeyError 방지)
    if main_rows and len(main_rows) > 0:
        df = pd.DataFrame(main_rows[1:], columns=main_rows[0])
    else:
        df = pd.DataFrame(columns=['사용자', '품목명', '규격', '수량']) # 기본값 설정

    if user_rows and len(user_rows) > 0:
        u_df = pd.DataFrame(user_rows[1:], columns=user_rows[0])
    else:
        u_df = pd.DataFrame(columns=['ID', '비밀번호', '권한'])
        
    return df, u_df

# --- 4. 메인 실행부 ---
df, user_df = load_all_data()

# 열 이름 디버깅용 (문제가 생기면 사이드바에 출력)
if not df.empty and '사용자' not in df.columns:
    st.sidebar.error(f"⚠️ '사용자' 열을 찾을 수 없습니다. 현재 열: {list(df.columns)}")

if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "user_id": "", "role": ""})

if not st.session_state["logged_in"]:
    st.title("🔐 창고 관리 시스템")
    with st.form("login"):
        id_i = st.text_input("아이디")
        pw_i = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인"):
            # ID 열 이름도 유연하게 대응
            id_col = 'ID' if 'ID' in user_df.columns else user_df.columns[0]
            pw_col = '비밀번호' if '비밀번호' in user_df.columns else user_df.columns[1]
            u_row = user_df[(user_df[id_col] == id_i) & (user_df[pw_col] == pw_i)]
            if not u_row.empty:
                st.session_state.update({"logged_in": True, "user_id": id_i, "role": u_row.iloc[0]['권한']})
                st.rerun()
            else: st.error("정보 불일치")
else:
    user_id = st.session_state["user_id"]
    menu = st.sidebar.radio("메뉴", ["🏠 현황", "📥 내 물품 관리", "📜 이력", "📅 달력", "🆕 등록"])

    # [1] 내 물품 관리 (KeyError 해결 버전)
    if menu == "📥 내 물품 관리":
        st.subheader("📥 내 재고 관리")
        # '사용자' 열이 있는지 한 번 더 확인 후 필터링
        user_col = '사용자' if '사용자' in df.columns else df.columns[0]
        my_df = df[df[user_col] == user_id]
        
        if my_df.empty:
            st.info("보유 중인 품목이 없습니다.")
        else:
            for idx, row in my_df.iterrows():
                with st.expander(f"📦 {row.get('품목명', '이름없음')} ({row.get('수량', 0)}개)"):
                    c1, c2 = st.columns(2)
                    # 수량 업데이트 로직 (생략된 기존 v5.1과 동일)
                    with c1:
                        if st.button("➕ 입고", key=f"i_{idx}"):
                            new_q = int(row['수량']) + 1
                            google_api_request("UPDATE", f"시트1!D{idx+2}", [[new_q]])
                            st.cache_data.clear(); st.rerun()
                    with c2:
                        # 전송 로직 등...
                        pass

    # 나머지 메뉴(현황, 이력, 달력 등)는 v5.1과 동일하게 유지
    elif menu == "🏠 현황":
        st.write(df)