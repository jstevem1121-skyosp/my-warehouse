import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import google.auth.transport.requests
import requests
from datetime import datetime
import streamlit.components.v1 as components

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="고속 창고 관리 v5.5", layout="wide")

# --- 2. 구글 API 직접 통신 엔진 ---
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
    except:
        return None

# --- 3. 데이터 로딩 (탭 이름: inventory_data 지정) ---
@st.cache_data(ttl=2)
def load_all_data():
    # 사용자가 알려주신 탭 이름 'inventory_data'로 데이터 호출
    main_rows = google_api_request("GET", "inventory_data!A:E")
    user_rows = google_api_request("GET", "사용자!A:C")
    
    if main_rows and len(main_rows) > 0:
        df = pd.DataFrame(main_rows[1:], columns=main_rows[0])
    else:
        df = pd.DataFrame()

    if user_rows and len(user_rows) > 0:
        u_df = pd.DataFrame(user_rows[1:], columns=user_rows[0])
    else:
        u_df = pd.DataFrame()
        
    return df, u_df

# --- 4. 메인 실행 로직 ---
df, user_df = load_all_data()

# 세션 관리
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "user_id": "", "role": ""})

if not st.session_state["logged_in"]:
    st.title("🔐 창고 관리 시스템 로그인")
    if user_df.empty:
        st.error("⚠️ '사용자' 시트 연결 실패. 탭 이름을 확인하세요.")
    with st.form("login"):
        id_i = st.text_input("아이디")
        pw_i = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인"):
            u_cols = list(user_df.columns)
            if not user_df.empty and len(u_cols) >= 2:
                u_row = user_df[(user_df[u_cols[0]] == id_i) & (user_df[u_cols[1]] == pw_i)]
                if not u_row.empty:
                    st.session_state.update({"logged_in": True, "user_id": id_i, "role": u_row.iloc[0][u_cols[2]] if len(u_cols)>2 else 'user'})
                    st.rerun()
            st.error("로그인 정보를 다시 확인하세요.")
else:
    user_id = st.session_state["user_id"]
    role = st.session_state["role"]
    st.sidebar.success(f"ID: {user_id} ({role})")
    menu = st.sidebar.radio("메뉴", ["🏠 전체 재고 현황", "📥 내 물품/전송", "📜 작업 이력", "📅 일정 달력", "🆕 새 품목 등록"])

    # 열 인덱스 설정 (안전한 참조용)
    cols = list(df.columns) if not df.empty else []
    
    if not df.empty and len(cols) >= 4:
        # [1] 전체 재고 현황
        if menu == "🏠 전체 재고 현황":
            st.subheader("📊 전체 재고 현황")
            # 품목명(2번째 열), 수량(4번째 열) 자동 감지
            item_col, qty_col, user_col = cols[1], cols[3], cols[0]
            
            items = df[df[item_col] != "신규 창고 개설"][item_col].unique()
            for item in items:
                item_df = df[df[item_col] == item]
                total = pd.to_numeric(item_df[qty_col]).sum()
                with st.expander(f"📦 {item} (총 {total}개)"):
                    for i, row in item_df.iterrows():
                        q = int(row[qty_col])
                        if q > 0:
                            c1, c2, c3 = st.columns([2, 1, 2])
                            c1.write(f"👤 {row[user_col]}")
                            c2.write(f"🔢 {q}개")
                            if role == "admin" and row[user_col] != user_id:
                                if c3.button("회수", key=f"rec_{i}"):
                                    google_api_request("UPDATE", f"inventory_data!D{i+2}", [[0]])
                                    google_api_request("APPEND", "이력!A:F", [[datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id, "회수", item, q, row[user_col]]])
                                    st.cache_data.clear(); st.rerun()

        # [2] 내 물품 관리 및 전송
        elif menu == "📥 내 물품/전송":
            st.subheader("📥 내 재고 관리")
            user_col, item_col, qty_col = cols[0], cols[1], cols[3]
            my_df = df[df[user_col] == user_id]
            
            for idx, row in my_df.iterrows():
                if row[item_col] == "신규 창고 개설": continue
                with st.expander(f"🔹 {row[item_col]} ({row[qty_col]}개)"):
                    c1, c2 = st.columns(2)
                    with c1:
                        adj = st.number_input("조정량", 1, 100, 1, key=f"adj_{idx}")
                        if st.button("➕ 입고", key=f"in_{idx}"):
                            google_api_request("UPDATE", f"inventory_data!D{idx+2}", [[int(row[qty_col]) + adj]])
                            google_api_request("APPEND", "이력!A:F", [[datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id, "입고", row[item_col], adj, "-"]])
                            st.cache_data.clear(); st.rerun()
                    with c2:
                        targets = [u for u in user_df[user_df.columns[0]] if u != user_id]
                        target = st.selectbox("전송 대상", targets, key=f"tg_{idx}")
                        s_amt = st.number_input("전송량", 1, int(row[qty_col]), 1, key=f"s_{idx}")
                        if st.button("🚀 보내기", key=f"send_{idx}"):
                            google_api_request("UPDATE", f"inventory_data!D{idx+2}", [[int(row[qty_col]) - s_amt]])
                            google_api_request("APPEND", "inventory_data!A:D", [[target, row[item_col], row[cols[2]], s_amt]])
                            google_api_request("APPEND", "이력!A:F", [[datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id, "전송", row[item_col], s_amt, target]])
                            st.cache_data.clear(); st.rerun()

        # [3] 작업 이력 / [4] 달력 / [5] 등록 로직 동일하게 유지 (v5.3 참조)
        elif menu == "📜 작업 이력":
            logs = google_api_request("GET", "이력!A:F")
            if logs: st.table(pd.DataFrame(logs[1:], columns=logs[0]).iloc[::-1].head(30))
        elif menu == "📅 일정 달력":
            components.iframe("https://calendar.google.com/calendar/embed?src=ko.south_korea%23holiday&ctz=Asia%2FSeoul", height=600)
        elif menu == "🆕 새 품목 등록":
            with st.form("new"):
                n, s, q = st.text_input("품목명"), st.text_input("규격"), st.number_input("수량", 0)
                if st.form_submit_button("등록"):
                    google_api_request("APPEND", "inventory_data!A:D", [[user_id, n, s, q]])
                    st.cache_data.clear(); st.rerun()
    else:
        st.warning("⚠️ 'inventory_data' 시트에서 데이터를 찾을 수 없습니다. 열 제목(사용자, 품목명, 규격, 수량)이 있는지 확인하세요.")