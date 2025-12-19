import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import re
from datetime import datetime

# --- 페이지 설정 ---
st.set_page_config(page_title="온라인 창고 관리", layout="wide")

# --- 1. ID 및 비밀번호 체크 로직 ---
def check_login():
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
        st.session_state["user_id"] = ""
        st.session_state["role"] = None

    if st.session_state["logged_in"]:
        return True

    st.title("🔒 창고 관리 시스템")
    
    with st.container():
        user_id = st.text_input("사용자 성함(ID)을 입력하세요", placeholder="예: 홍길동")
        pwd_input = st.text_input("비밀번호를 입력하세요", type="password")
        
        if st.button("로그인"):
            if not user_id:
                st.error("사용자 성함을 입력해주세요.")
            elif pwd_input == str(st.secrets["app_password"]):
                st.session_state["logged_in"] = True
                st.session_state["user_id"] = user_id
                st.session_state["role"] = "admin"
                st.rerun()
            elif pwd_input == str(st.secrets["user_password"]):
                st.session_state["logged_in"] = True
                st.session_state["user_id"] = user_id
                st.session_state["role"] = "user"
                st.rerun()
            else:
                st.error("❌ 비밀번호가 틀렸습니다.")
    return False

# --- 2. 구글 시트 연결 및 업데이트 함수 (로그에 ID 포함) ---
@st.cache_resource
def get_gspread_client():
    # (기존 서비스 계정 연결 로직 동일)
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = dict(st.secrets["gcp_service_account"])
    pk = creds_info["private_key"]
    if "-----BEGIN PRIVATE KEY-----" in pk:
        content = pk.replace("-----BEGIN PRIVATE KEY-----", "").replace("-----END PRIVATE KEY-----", "")
        clean_content = re.sub(r"\s+", "", content) 
        lines = [clean_content[i:i+64] for i in range(0, len(clean_content), 64)]
        pk = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END PRIVATE KEY-----\n"
    creds_info["private_key"] = pk
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(creds)

def update_stock_with_id(main_sheet, log_sheet, row_idx, item_name, current_qty, change, qty_col_idx):
    new_qty = current_qty + change
    if new_qty < 0:
        st.error("재고 부족!")
        return
    try:
        main_sheet.update_cell(row_idx + 2, qty_col_idx + 1, int(new_qty))
        if log_sheet:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            user_info = st.session_state["user_id"] # 현재 로그인된 ID
            change_text = f"+{change}" if change > 0 else str(change)
            # 로그에 [시간, ID, 품목, 변동, 결과] 기록
            log_sheet.append_row([now, user_info, item_name, change_text, int(new_qty)])
        st.toast(f"✅ {user_info}님 작업 완료")
        st.rerun()
    except Exception as e:
        st.error(f"오류: {e}")

# --- 3. 메인 로직 ---
if check_login():
    user_id = st.session_state["user_id"]
    role = st.session_state["role"]
    
    st.sidebar.info(f"👤 접속자: {user_id} ({'관리자' if role=='admin' else '사용자'})")
    if st.sidebar.button("로그아웃"):
        st.session_state["logged_in"] = False
        st.rerun()

    # --- 메뉴 구성 ---
    menu_list = ["재고 현황", "간편 입출고"]
    if role == "admin":
        menu_list += ["품목 관리", "활동 로그"]
    
    menu = st.sidebar.radio("📋 메뉴", menu_list)

    # (이후 시트 연결 및 메뉴별 실행 코드는 동일하게 구성)
    # 로그 시트에 저장 시 반드시 update_stock_with_id 함수를 사용하세요.