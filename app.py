import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import re
from datetime import datetime

# --- 구글 시트 및 보안 설정 ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"

# 1. 로그인 체크 함수
def check_password():
    """사용자가 올바른 비밀번호를 입력했는지 확인합니다."""
    def password_entered():
        # 사용자가 입력한 비번과 Secrets에 저장된 비번 비교
        if st.session_state["password"] == st.secrets["app_password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # 보안을 위해 세션에서 비번 삭제
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # 로그인 화면 UI
        st.title("🔒 창고 관리 시스템 로그인")
        st.text_input("비밀번호를 입력하세요", type="password", on_change=password_entered, key="password")
        st.info("비밀번호를 입력하고 Enter를 눌러주세요.")
        return False
    elif not st.session_state["password_correct"]:
        # 비번 틀렸을 때
        st.title("🔒 창고 관리 시스템 로그인")
        st.text_input("비밀번호를 입력하세요", type="password", on_change=password_entered, key="password")
        st.error("❌ 비밀번호가 틀렸습니다. 다시 시도해주세요.")
        return False
    else:
        # 로그인 성공
        return True

@st.cache_resource
def get_gspread_client():
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

# --- 메인 로직 시작 ---
if check_password():  # 로그인 성공 시에만 아래 코드 실행
    st.set_page_config(page_title="온라인 창고 관리", layout="wide")
    
    # 로그아웃 버튼 (사이드바 하단)
    if st.sidebar.button("로그아웃"):
        del st.session_state["password_correct"]
        st.rerun()

    st.title("🌐 온라인 창고 관리 시스템")

    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_url(SHEET_URL)
        main_sheet = spreadsheet.sheet1
        try:
            log_sheet = spreadsheet.worksheet("로그")
        except:
            log_sheet = None

        data = main_sheet.get_all_records()
        
        if data:
            df = pd.DataFrame(data)
            # (이전과 동일한 컬럼 감지 및 변환 로직...)
            name_col = next((c for c in df.columns if '품목' in str(c) or '이름' in str(c)), df.columns[0])
            qty_col = next((c for c in df.columns if '수량' in str(c)), df.columns[2] if len(df.columns) > 2 else None)
            if qty_col:
                df[qty_col] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0).astype(int)
                qty_col_idx = list(df.columns).index(qty_col)

            # --- 사이드바 메뉴 ---
            menu = st.sidebar.radio("메뉴 선택", ["재고 현황", "간편 입출고", "품목 관리", "활동 로그"])

            # 각 메뉴별 코드는 기존과 동일하게 유지...
            if menu == "재고 현황":
                st.dataframe(df, use_container_width=True, hide_index=True)
            # ... (이하 생략 - 이전 답변의 통합 코드를 여기에 그대로 넣으시면 됩니다)
            
    except Exception as e:
        st.error(f"❌ 오류 발생: {e}")