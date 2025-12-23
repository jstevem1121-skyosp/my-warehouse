import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import google.auth.transport.requests
import requests
from datetime import datetime
import streamlit.components.v1 as components

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="창고 통합 관리 시스템 v5.3", layout="wide")

# --- 2. 구글 API 직접 통신 엔진 (에러 방지용) ---
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

# --- 3. 데이터 로딩 및 열 이름 자동 감지 ---
@st.cache_data(ttl=5)
def load_all_data():
    # 시트 이름 자동 시도
    main_rows = google_api_request("GET", "시트1!A:E")
    if not main_rows: main_rows = google_api_request("GET", "Sheet1!A:E")
    user_rows = google_api_request("GET", "사용자!A:C")
    
    # 메인 재고 데이터프레임
    if main_rows and len(main_rows) > 0:
        df = pd.DataFrame(main_rows[1:], columns=main_rows[0])
    else:
        df = pd.DataFrame(columns=['사용자', '품목명', '규격', '수량'])

    # 사용자 데이터프레임
    if user_rows and len(user_rows) > 0:
        u_df = pd.DataFrame(user_rows[1:], columns=user_rows[0])
    else:
        u_df = pd.DataFrame(columns=['ID', '비밀번호', '권한'])
        
    return df, u_df

# --- 4. 메인 실행부 ---
df, user_df = load_all_data()

# 열 이름 유연하게 설정 (KeyError 방지)
u_col = '사용자' if '사용자' in df.columns else (df.columns[0] if not df.empty else '사용자')
item_col = '품목명' if '품목명' in df.columns else (df.columns[1] if len(df.columns) > 1 else '품목명')
qty_col = '수량' if '수량' in df.columns else (df.columns[3] if len(df.columns) > 3 else '수량')

if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "user_id": "", "role": ""})

if not st.session_state["logged_in"]:
    st.title("🔐 창고 관리 시스템")
    with st.form("login"):
        id_i = st.text_input("아이디")
        pw_i = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인"):
            id_col = 'ID' if 'ID' in user_df.columns else user_df.columns[0]
            pw_col = '비밀번호' if '비밀번호' in user_df.columns else user_df.columns[1]
            u_row = user_df[(user_df[id_col] == id_i) & (user_df[pw_col] == pw_i)]
            if not u_row.empty:
                st.session_state.update({"logged_in": True, "user_id": id_i, "role": u_row.iloc[0].get('권한', 'user')})
                st.rerun()
            else: st.error("정보 불일치")
else:
    user_id = st.session_state["user_id"]
    role = st.session_state["role"]
    st.sidebar.success(f"접속: {user_id} ({role})")
    menu = st.sidebar.radio("메뉴", ["🏠 재고 현황", "📥 내 물품 관리", "📜 작업 이력", "📅 일정 달력", "🆕 새 품목 등록", "👥 계정 관리"])

    # [1] 재고 현황 (회수 기능 포함)
    if menu == "🏠 재고 현황":
        st.subheader("📊 전체 재고 현황")
        items = df[df[item_col] != "신규 창고 개설"][item_col].unique()
        for item in items:
            item_df = df[df[item_col] == item]
            with st.expander(f"📦 {item} (전체 {item_df[qty_col].astype(int).sum()}개)"):
                for i, row in item_df.iterrows():
                    if int(row[qty_col]) <= 0: continue
                    c1, c2, c3 = st.columns([2, 1, 2])
                    c1.write(f"👤 {row[u_col]}")
                    c2.write(f"🔢 {row[qty_col]}개")
                    if role == "admin" and row[u_col] != user_id:
                        r_amt = c3.number_input("회수량", 1, int(row[qty_col]), 1, key=f"r_{i}")
                        if c3.button("즉시 회수", key=f"rb_{i}"):
                            google_api_request("UPDATE", f"시트1!D{i+2}", [[int(row[qty_col]) - r_amt]])
                            google_api_request("APPEND", "이력!A:F", [[datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id, "회수", item, r_amt, row[u_col]]])
                            st.cache_data.clear(); st.rerun()

    # [2] 내 물품 관리 (입/출고 및 전송)
    elif menu == "📥 내 물품 관리":
        st.subheader("📥 내 재고 관리 및 전송")
        my_df = df[df[u_col] == user_id]
        if my_df.empty: st.info("보유 물품이 없습니다.")
        for idx, row in my_df.iterrows():
            if row[item_col] == "신규 창고 개설": continue
            with st.expander(f"🔹 {row[item_col]} ({row[qty_col]}개)"):
                c1, c2 = st.columns(2)
                with c1:
                    adj = st.number_input("조정량", 1, 1000, 1, key=f"adj_{idx}")
                    if st.button("➕ 입고", key=f"in_{idx}"):
                        google_api_request("UPDATE", f"시트1!D{idx+2}", [[int(row[qty_col]) + adj]])
                        google_api_request("APPEND", "이력!A:F", [[datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id, "입고", row[item_col], adj, "-"]])
                        st.cache_data.clear(); st.rerun()
                    if st.button("➖ 출고", key=f"out_{idx}"):
                        if int(row[qty_col]) >= adj:
                            google_api_request("UPDATE", f"시트1!D{idx+2}", [[int(row[qty_col]) - adj]])
                            google_api_request("APPEND", "이력!A:F", [[datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id, "출고", row[item_col], adj, "-"]])
                            st.cache_data.clear(); st.rerun()
                with c2:
                    targets = [u for u in user_df['ID'] if u != user_id]
                    target = st.selectbox("전송 대상", targets, key=f"tg_{idx}")
                    s_amt = st.number_input("전송량", 1, int(row[qty_col]), 1, key=f"s_{idx}")
                    if st.button("🚀 보내기", key=f"send_{idx}"):
                        google_api_request("UPDATE", f"시트1!D{idx+2}", [[int(row[qty_col]) - s_amt]])
                        google_api_request("APPEND", "시트1!A:D", [[target, row[item_col], row.get('규격','-'), s_amt]])
                        google_api_request("APPEND", "이력!A:F", [[datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id, "전송", row[item_col], s_amt, target]])
                        st.cache_data.clear(); st.rerun()

    # [3] 작업 이력
    elif menu == "📜 작업 이력":
        st.subheader("📜 최근 작업 기록")
        logs = google_api_request("GET", "이력!A:F")
        if logs:
            st.dataframe(pd.DataFrame(logs[1:], columns=logs[0]).iloc[::-1].head(50), use_container_width=True)

    # [4] 일정 달력
    elif menu == "📅 일정 달력":
        components.iframe("https://calendar.google.com/calendar/embed?src=ko.south_korea%23holiday%40group.v.calendar.google.com&ctz=Asia%2FSeoul", height=600)

    # [5] 새 품목 등록
    elif menu == "🆕 새 품목 등록":
        with st.form("new_i"):
            n, s, q = st.text_input("품목명"), st.text_input("규격"), st.number_input("수량", 0)
            if st.form_submit_button("등록"):
                google_api_request("APPEND", "시트1!A:D", [[user_id, n, s, q]])
                google_api_request("APPEND", "이력!A:F", [[datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id, "신규등록", n, q, "-"]])
                st.cache_data.clear(); st.rerun()

    # [6] 계정 관리
    elif menu == "👥 계정 관리" and role == "admin":
        with st.form("new_u"):
            u, p, r = st.text_input("신규 ID"), st.text_input("PW"), st.selectbox("권한", ["user", "admin"])
            if st.form_submit_button("계정 생성"):
                google_api_request("APPEND", "사용자!A:C", [[u, p, r]])
                google_api_request("APPEND", "시트1!A:D", [[u, "신규 창고 개설", "-", 0]])
                st.cache_data.clear(); st.rerun()