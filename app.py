import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import re
from datetime import datetime

# --- 1. 페이지 설정 및 다중 사용자 로그인 로직 ---
st.set_page_config(page_title="온라인 창고 관리", layout="wide")

def check_login():
    # 세션 상태 초기화
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
        st.session_state["user_id"] = ""
        st.session_state["role"] = None

    if st.session_state["logged_in"]:
        return True

    # 로그인 화면 UI
    st.title("🔒 창고 관리 시스템")
    st.markdown("사용자 성함을 입력하고 부여받은 비밀번호로 로그인하세요.")
    
    with st.container():
        # 여기서 입력하는 이름이 '활동 로그'에 기록됩니다.
        user_id_input = st.text_input("사용자 성함 (ID)", placeholder="예: 홍길동, 김철수")
        pwd_input = st.text_input("비밀번호", type="password")
        
        if st.button("로그인"):
            if not user_id_input:
                st.error("성함(ID)을 입력해야 접속이 가능합니다.")
            elif pwd_input == str(st.secrets["app_password"]): # 관리자 비번
                st.session_state["logged_in"] = True
                st.session_state["user_id"] = user_id_input
                st.session_state["role"] = "admin"
                st.success(f"관리자 {user_id_input}님 환영합니다!")
                st.rerun()
            elif pwd_input == str(st.secrets["user_password"]): # 일반 유저 비번
                st.session_state["logged_in"] = True
                st.session_state["user_id"] = user_id_input
                st.session_state["role"] = "user"
                st.success(f"{user_id_input}님 환영합니다!")
                st.rerun()
            else:
                st.error("❌ 비밀번호가 올바르지 않습니다.")
    return False

# --- 2. 구글 시트 연결 및 로그 기록 함수 ---
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

def log_activity(log_sheet, user_id, item_name, action, result_qty):
    if log_sheet:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # 시간, 사용자ID, 품목명, 작업내용, 최종수량 순으로 기록
        log_sheet.append_row([now, user_id, item_name, action, result_qty])

# --- 3. 메인 로직 시작 ---
if check_login():
    user_id = st.session_state["user_id"]
    role = st.session_state["role"]
    
    # 사이드바 상단 정보 및 로그아웃
    st.sidebar.info(f"👤 접속자: {user_id}\n\n🎖️ 권한: {'관리자' if role=='admin' else '일반 사용자'}")
    if st.sidebar.button("로그아웃"):
        st.session_state.clear()
        st.rerun()

    # 권한별 메뉴 구성 (이전 요청사항 반영)
    if role == "admin":
        menu_list = ["재고 현황", "간편 입출고", "품목 관리 (등록/수정)", "활동 로그"]
    else:
        menu_list = ["재고 현황"] # 일반 유저는 조회만 가능
    
    menu = st.sidebar.radio("📋 메뉴 선택", menu_list)

    SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"
    
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_url(SHEET_URL)
        main_sheet = spreadsheet.sheet1
        try: log_sheet = spreadsheet.worksheet("로그")
        except: log_sheet = None

        data = main_sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # 컬럼 감지
        name_col = next((c for c in df.columns if '품목' in str(c) or '이름' in str(c)), df.columns[0])
        qty_col = next((c for c in df.columns if '수량' in str(c)), df.columns[2] if len(df.columns) > 2 else None)
        df[qty_col] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0).astype(int)

        # --- 메뉴별 화면 ---
        if menu == "재고 현황":
            st.subheader("📊 실시간 재고 현황")
            st.dataframe(df, use_container_width=True, hide_index=True)

        elif menu == "간편 입출고" and role == "admin":
            st.subheader("🛠️ 수량 조정 (관리자 권한)")
            # ... (기존 관리자용 입출고 로직) ...
            search = st.text_input("검색")
            display_df = df[df[name_col].str.contains(search, case=False)] if search else df
            for idx, row in display_df.iterrows():
                with st.expander(f"📦 {row[name_col]} (현재: {row[qty_col]}개)"):
                    c1, c2 = st.columns(2)
                    with c1:
                        p_val = st.number_input("입고", 1, 1000, 1, key=f"p{idx}")
                        if st.button("입고 확인", key=f"bp{idx}"):
                            new_q = int(row[qty_col] + p_val)
                            main_sheet.update_cell(idx+2, list(df.columns).index(qty_col)+1, new_q)
                            log_activity(log_sheet, user_id, row[name_col], f"+{p_val}", new_q)
                            st.rerun()
                    with c2:
                        m_val = st.number_input("출고", 1, 1000, 1, key=f"m{idx}")
                        if st.button("출고 확인", key=f"bm{idx}"):
                            new_q = int(row[qty_col] - m_val)
                            if new_q < 0: st.error("재고 부족")
                            else:
                                main_sheet.update_cell(idx+2, list(df.columns).index(qty_col)+1, new_q)
                                log_activity(log_sheet, user_id, row[name_col], f"-{m_val}", new_q)
                                st.rerun()

        elif menu == "활동 로그" and role == "admin":
            st.subheader("📜 전체 활동 기록")
            if log_sheet:
                logs = log_sheet.get_all_values()
                if len(logs) > 1:
                    log_df = pd.DataFrame(logs[1:], columns=logs[0])
                    st.dataframe(log_df.iloc[::-1], use_container_width=True) # 최신순 정렬

    except Exception as e:
        st.error(f"❌ 오류 발생: {e}")