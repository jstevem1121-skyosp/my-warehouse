import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import google.auth.transport.requests
from datetime import datetime

st.set_page_config(page_title="재고 관리 v3.7", layout="wide")

# --- 에러 원천 차단 인증 로직 ---
def get_final_client():
    try:
        creds_info = dict(st.secrets["gcp_service_account"])
        creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        
        # AuthorizedSession 이슈를 피하기 위해 세션을 매번 새로 생성
        auth_request = google.auth.transport.requests.Request()
        creds.refresh(auth_request)
        
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"인증 오류: {e}")
        return None

@st.cache_data(ttl=5)
def load_data(url):
    client = get_final_client()
    if not client: return None, None, None
    sh = client.open_by_url(url)
    return sh.sheet1.get_all_records(), sh.worksheet("사용자").get_all_records(), sh

# --- 메인 로직 시작 ---
try:
    URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"
    main_data, user_data, sh = load_data(URL)
    
    if main_data is not None:
        df = pd.DataFrame(main_data)
        user_df = pd.DataFrame(user_data)
        
        # 세션 초기화
        if "logged_in" not in st.session_state:
            st.session_state.update({"logged_in": False, "user_id": ""})

        if not st.session_state["logged_in"]:
            st.title("🔐 로그인")
            with st.form("login"):
                id_v = st.text_input("ID")
                pw_v = st.text_input("PW", type="password")
                if st.form_submit_button("접속"):
                    row = user_df[(user_df['ID'].astype(str) == id_v) & (user_df['비밀번호'].astype(str) == pw_v)]
                    if not row.empty:
                        st.session_state.update({"logged_in": True, "user_id": id_v})
                        st.rerun()
                    else: st.error("정보 불일치")
        else:
            # --- 메인 화면 (간결화) ---
            st.sidebar.write(f"✅ {st.session_state['user_id']}님")
            if st.sidebar.button("로그아웃"):
                st.session_state["logged_in"] = False
                st.rerun()
                
            menu = st.sidebar.radio("메뉴", ["재고관리", "이력"])
            
            if menu == "재고관리":
                st.subheader("📦 보유 품목")
                my_df = df[df['사용자'] == st.session_state['user_id']]
                for idx, row in my_df.iterrows():
                    with st.expander(f"{row['품목명']} ({row['수량']}개)"):
                        amt = st.number_input("조정 수량", 1, 100, 1, key=f"n_{idx}")
                        if st.button("전송", key=f"b_{idx}"):
                            # 직접 업데이트 시도
                            new_val = int(row['수량']) - amt
                            # 구글 시트는 인덱스가 2부터 시작 (헤더 1, 데이터 2~)
                            sh.sheet1.update_cell(idx + 2, 4, new_val)
                            
                            # 이력 기록
                            try:
                                log = sh.worksheet("이력")
                                log.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), st.session_state['user_id'], "전송", row['품목명'], amt])
                            except: pass
                            
                            st.cache_data.clear()
                            st.success("완료!")
                            st.rerun()
            
            elif menu == "이력":
                try:
                    log_df = pd.DataFrame(sh.worksheet("이력").get_all_records())
                    st.table(log_df.iloc[::-1].head(20))
                except: st.info("기록이 없습니다.")

except Exception as e:
    st.error(f"시스템 오류: {e}")