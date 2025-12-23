import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time
import streamlit.components.v1 as components

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="고속 창고 관리 시스템", layout="wide")

# --- 2. 구글 시트 연결 및 데이터 로드 함수 ---
@st.cache_resource
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = dict(st.secrets["gcp_service_account"])
    creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=10) # 캐시 유지 시간을 10초로 늘려 빈번한 API 호출 방지
def fetch_all_data(sheet_url):
    client = get_gspread_client()
    spreadsheet = client.open_by_url(sheet_url)
    main_sheet = spreadsheet.sheet1
    user_sheet = spreadsheet.worksheet("사용자")
    log_sheet = spreadsheet.worksheet("이력")
    
    # 데이터를 한꺼번에 로드
    main_data = main_sheet.get_all_records()
    user_data = user_sheet.get_all_records()
    
    return main_data, user_data, spreadsheet

# --- 3. 공통 업데이트 함수 (속도 핵심) ---
def update_inventory(spreadsheet, df, action_desc, item_name, amount, target_user="-"):
    """데이터프레임을 시트에 한 번에 업데이트하여 속도 개선"""
    try:
        # 1. 메인 시트 업데이트 (전체 데이터를 덮어쓰는 것이 개별 수정보다 빠를 때가 많음)
        # 하지만 행이 너무 많다면 범위를 지정해 업데이트 하는 것이 좋습니다.
        main_sheet = spreadsheet.sheet1
        # 리스트 형태로 변환 (헤더 포함)
        data_to_save = [df.columns.values.tolist()] + df.values.tolist()
        main_sheet.update('A1', data_to_save) # 배치 업데이트
        
        # 2. 로그 기록 (비동기 처리가 안 되므로 최대한 간결하게)
        log_sheet = spreadsheet.worksheet("이력")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_sheet.append_row([now, st.session_state["user_id"], action_desc, item_name, int(amount), target_user])
        
        st.cache_data.clear() # 데이터 변했으므로 캐시 삭제
        return True
    except Exception as e:
        st.error(f"업데이트 오류: {e}")
        return False

# --- 4. 로그인 체크 ---
def check_login(user_df):
    if "logged_in" not in st.session_state:
        st.session_state.update({"logged_in": False, "user_id": "", "role": None})
    if st.session_state["logged_in"]: return True

    st.title("🔐 시스템 로그인")
    with st.form("login"):
        id_i = st.text_input("아이디(성함)").strip()
        pw_i = st.text_input("비밀번호", type="password").strip()
        if st.form_submit_button("로그인"):
            user_row = user_df[(user_df['ID'].astype(str) == id_i) & (user_df['비밀번호'].astype(str) == pw_i)]
            if not user_row.empty:
                st.session_state.update({"logged_in": True, "user_id": id_i, "role": user_row.iloc[0]['권한']})
                st.rerun()
            else: st.error("❌ 정보 오류")
    return False

# --- 메인 실행부 ---
try:
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"
    main_raw, user_raw, spreadsheet = fetch_all_data(SHEET_URL)
    
    df = pd.DataFrame(main_raw)
    user_df = pd.DataFrame(user_raw)
    cols = df.columns.tolist()

    if check_login(user_df):
        user_id = st.session_state["user_id"]
        role = st.session_state["role"]
        
        st.sidebar.info(f"👤 {user_id}님 ({role})")
        menu = st.sidebar.radio("메뉴", ["🏠 현황", "📥 관리/이동", "📜 이력", "📅 달력", "🆕 등록"])

        # --- [1] 현황 & 관리자 회수 ---
        if menu == "🏠 현황":
            st.subheader("📊 전체 재고")
            items = df[df[cols[1]] != "신규 창고 개설"][cols[1]].unique()
            for item in items:
                item_df = df[df[cols[1]] == item]
                with st.expander(f"📦 {item} ({item_df[cols[3]].sum()}개)"):
                    for i, row in item_df[item_df[cols[3]] > 0].iterrows():
                        c1, c2, c3 = st.columns([2, 1, 2])
                        c1.write(f"👤 {row[cols[0]]}")
                        c2.write(f"🔢 {row[cols[3]]}")
                        if role == "admin" and row[cols[0]] != user_id:
                            t_amt = c3.number_input("회수", 1, int(row[cols[3]]), 1, key=f"t_{i}")
                            if c3.button("회수", key=f"bt_{i}"):
                                # 메모리(DataFrame)상에서 먼저 계산
                                df.at[i, cols[3]] -= t_amt
                                my_idx = df[(df[cols[0]] == user_id) & (df[cols[1]] == row[cols[1]])].index
                                if not my_idx.empty: df.at[my_idx[0], cols[3]] += t_amt
                                else: df = df.append({cols[0]:user_id, cols[1]:row[cols[1]], cols[2]:row[cols[2]], cols[3]:t_amt}, ignore_index=True)
                                
                                if update_inventory(spreadsheet, df, "회수", row[cols[1]], t_amt, row[cols[0]]):
                                    st.rerun()

        # --- [2] 내 물품 관리 ---
        elif menu == "📥 관리/이동":
            my_df = df[df[cols[0]] == user_id]
            for idx, row in my_df.iterrows():
                if row[cols[1]] == "신규 창고 개설": continue
                with st.expander(f"🔹 {row[cols[1]]} ({row[cols[3]]}개)"):
                    c1, c2 = st.columns(2)
                    amt = c1.number_input("수량", 1, 1000, 1, key=f"n_{idx}")
                    if c1.button("입고", key=f"i_{idx}"):
                        df.at[idx, cols[3]] += amt
                        if update_inventory(spreadsheet, df, "입고", row[cols[1]], amt): st.rerun()
                    
                    target = c2.selectbox("받는 사람", [u for u in user_df['ID'] if u != user_id], key=f"s_{idx}")
                    if c2.button("전송", key=f"ts_{idx}"):
                        if row[cols[3]] >= amt:
                            df.at[idx, cols[3]] -= amt
                            t_idx = df[(df[cols[0]] == target) & (df[cols[1]] == row[cols[1]])].index
                            if not t_idx.empty: df.at[t_idx[0], cols[3]] += amt
                            else: # 신규 행 추가
                                new_row = {cols[0]:target, cols[1]:row[cols[1]], cols[2]:row[cols[2]], cols[3]:amt}
                                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                            
                            if update_inventory(spreadsheet, df, "전송", row[cols[1]], amt, target): st.rerun()

        # --- [3] 이력 조회 (가장 빠르게) ---
        elif menu == "📜 이력":
            log_data = spreadsheet.worksheet("이력").get_all_records()
            st.table(pd.DataFrame(log_data).iloc[::-1].head(20)) # 상위 20개만 빠르게 표시

except Exception as e:
    st.error(f"오류: {e}")