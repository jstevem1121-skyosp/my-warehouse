import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import re
from datetime import datetime

# --- 페이지 기본 설정 (가장 위에 와야 합니다) ---
st.set_page_config(page_title="온라인 창고 관리", layout="wide")

# --- 1. 로그인 체크 로직 ---
def check_password():
    """사용자가 올바른 비밀번호를 입력했는지 확인하고 결과 반환"""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    # 로그인 화면 중앙 정렬
    st.markdown("### 🔒 창고 관리 시스템")
    pwd_input = st.text_input("비밀번호를 입력하세요", type="password")
    
    # Secrets에 저장된 app_password와 비교 (직접 "1234"로 테스트하고 싶다면 st.secrets 부분을 "1234"로 바꿔보세요)
    if st.button("로그인"):
        try:
            correct_pwd = st.secrets["app_password"]
            if pwd_input == str(correct_pwd):
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("❌ 비밀번호가 틀렸습니다.")
        except KeyError:
            st.error("❌ 설정(Secrets)에 'app_password'가 등록되어 있지 않습니다.")
    
    return False

# --- 2. 구글 시트 연결 함수 ---
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

# --- 3. 메인 로직 ---
if check_password():
    # 로그아웃 버튼
    if st.sidebar.button("로그아웃"):
        st.session_state["password_correct"] = False
        st.rerun()

    SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"

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
            # 유연한 컬럼 인식
            name_col = next((c for c in df.columns if '품목' in str(c) or '이름' in str(c)), df.columns[0])
            qty_col = next((c for c in df.columns if '수량' in str(c)), df.columns[2] if len(df.columns) > 2 else None)
            
            if qty_col:
                df[qty_col] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0).astype(int)
                qty_col_idx = list(df.columns).index(qty_col)

            menu = st.sidebar.radio("📋 메뉴", ["재고 현황", "간편 입출고", "품목 관리 (등록/수정)", "활동 로그"])

            # 각 메뉴별 코드는 그대로 유지 (이전 통합 코드 내용)
            if menu == "재고 현황":
                st.subheader("📊 전체 재고")
                st.dataframe(df, use_container_width=True, hide_index=True)
            
            elif menu == "간편 입출고":
                # ... (이전 입출고 코드들) ...
                st.info("입출고 기능을 사용하세요.")
            
            # (나머지 관리/로그 메뉴 등등...)
            
    except Exception as e:
        st.error(f"❌ 데이터 로딩 중 오류 발생: {e}")