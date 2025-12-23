import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time
import streamlit.components.v1 as components

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="통합 창고 관리 시스템", layout="wide")

# --- 2. 구글 시트 연결 및 데이터 로드 함수 ---
@st.cache_resource
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = dict(st.secrets["gcp_service_account"])
    # private_key 내의 이스케이프 문자 처리
    creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=5) # 5초마다 캐시 갱신
def fetch_sheet_data(sheet_url, worksheet_name):
    client = get_gspread_client()
    spreadsheet = client.open_by_url(sheet_url)
    return spreadsheet.worksheet(worksheet_name).get_all_records()

# --- 3. [신규] 로그 기록 함수 ---
def log_transaction(spreadsheet, action, item, amount, target_user="-"):
    try:
        log_sheet = spreadsheet.worksheet("이력")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_sheet.append_row([now, st.session_state["user_id"], action, item, int(amount), target_user])
    except Exception as e:
        st.error(f"⚠️ 로그 기록 실패: {e}")

# --- 4. 로그인 로직 ---
def check_login(user_sheet):
    if "logged_in" not in st.session_state:
        st.session_state.update({"logged_in": False, "user_id": "", "role": None})
    if st.session_state["logged_in"]: return True

    st.title("🔐 시스템 로그인")
    user_data = user_sheet.get_all_records()
    user_df = pd.DataFrame(user_data)
    with st.form("login"):
        id_i = st.text_input("아이디(성함)").strip()
        pw_i = st.text_input("비밀번호", type="password").strip()
        if st.form_submit_button("로그인"):
            user_row = user_df[(user_df['ID'].astype(str) == id_i) & (user_df['비밀번호'].astype(str) == pw_i)]
            if not user_row.empty:
                st.session_state.update({"logged_in": True, "user_id": id_i, "role": user_row.iloc[0]['권한']})
                st.rerun()
            else: st.error("❌ 아이디 또는 비밀번호를 확인해주세요.")
    return False

# --- 메인 실행부 ---
try:
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"
    client = get_gspread_client()
    spreadsheet = client.open_by_url(SHEET_URL)
    main_sheet = spreadsheet.sheet1
    user_sheet = spreadsheet.worksheet("사용자")
    
    if check_login(user_sheet):
        user_id = st.session_state["user_id"]
        role = st.session_state["role"]
        
        # 사이드바 메뉴
        st.sidebar.info(f"👤 {user_id}님 ({role})")
        menu_options = ["🏠 전체 품목 현황", "📥 내 물품 관리 및 이동", "📜 입출고 이력", "📅 일정 달력", "🆕 새 품목 등록"]
        if role == "admin":
            menu_options.append("👥 계정 관리")
        menu = st.sidebar.radio("메뉴 선택", menu_options)

        # 데이터 로드
        raw_data = main_sheet.get_all_records()
        df = pd.DataFrame(raw_data)
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
        cols = df.columns.tolist() # [소유자, 품목명, 규격, 수량]

        # --- [1] 전체 품목 현황 ---
        if menu == "🏠 전체 품목 현황":
            st.subheader("📊 전체 재고 소유 현황")
            items = df[df[cols[1]] != "신규 창고 개설"][cols[1]].unique()
            if len(items) == 0:
                st.info("등록된 품목이 없습니다.")
            else:
                for item in items:
                    item_df = df[df[cols[1]] == item]
                    total_q = item_df[cols[3]].sum()
                    with st.expander(f"📦 {item} (전체 합계: {total_q}개)"):
                        display_df = item_df[item_df[cols[3]] > 0]
                        for i, row in display_df.iterrows():
                            c1, c2, c3 = st.columns([2, 1, 2])
                            c1.write(f"👤 소유자: **{row[cols[0]]}**")
                            c2.write(f"🔢 수량: {row[cols[3]]}")
                            if role == "admin" and row[cols[0]] != user_id:
                                take_amt = c3.number_input(f"회수 수량", 1, int(row[cols[3]]), 1, key=f"t_{i}")
                                if c3.button(f"회수하기", key=f"btn_t_{i}"):
                                    # 상대방 차감
                                    main_sheet.update_cell(i+2, 4, int(row[cols[3]] - take_amt))
                                    # 내 수량 증가
                                    my_idx = df[(df[cols[0]] == user_id) & (df[cols[1]] == row[cols[1]]) & (df[cols[2]] == row[cols[2]])].index
                                    if not my_idx.empty:
                                        main_sheet.update_cell(int(my_idx[0])+2, 4, int(df.loc[my_idx[0], cols[3]] + take_amt))
                                    else:
                                        main_sheet.append_row([user_id, row[cols[1]], row[cols[2]], int(take_amt)])
                                    
                                    log_transaction(spreadsheet, "관리자 회수", row[cols[1]], take_amt, row[cols[0]])
                                    st.success("회수 완료!"); st.cache_data.clear(); time.sleep(1); st.rerun()
                            st.divider()

        # --- [2] 내 물품 관리 및 이동 ---
        elif menu == "📥 내 물품 관리 및 이동":
            st.subheader(f"📥 {user_id}님의 보관함")
            my_df = df[(df[cols[0]] == user_id) & (df[cols[1]] != "신규 창고 개설")]
            if my_df.empty:
                st.warning("내 창고에 물품이 없습니다.")
            else:
                for idx, row in my_df.iterrows():
                    with st.expander(f"🔹 {row[cols[1]]} ({row[cols[3]]}개)"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write("🛠️ 입출고")
                            amt = st.number_input("조정 수량", 1, 1000, 1, key=f"a_{idx}")
                            if st.button("➕ 입고", key=f"in_{idx}"):
                                main_sheet.update_cell(idx+2, 4, int(row[cols[3]] + amt))
                                log_transaction(spreadsheet, "입고", row[cols[1]], amt)
                                st.cache_data.clear(); st.rerun()
                            if st.button("➖ 출고", key=f"out_{idx}"):
                                if row[cols[3]] >= amt:
                                    main_sheet.update_cell(idx+2, 4, int(row[cols[3]] - amt))
                                    log_transaction(spreadsheet, "출고", row[cols[1]], amt)
                                    st.cache_data.clear(); st.rerun()
                                else: st.error("재고 부족")
                        with col2:
                            st.write("🎁 보내기")
                            u_list = [str(u['ID']).strip() for u in user_sheet.get_all_records() if str(u['ID']).strip() != user_id]
                            target = st.selectbox("받는 사람", u_list, key=f"tg_{idx}")
                            m_amt = st.number_input("보낼 수량", 1, int(row[cols[3]]) if int(row[cols[3]]) > 0 else 1, key=f"m_{idx}")
                            if st.button("전송 실행", key=f"btn_s_{idx}"):
                                main_sheet.update_cell(idx+2, 4, int(row[cols[3]] - m_amt))
                                t_idx = df[(df[cols[0]] == target) & (df[cols[1]] == row[cols[1]]) & (df[cols[2]] == row[cols[2]])].index
                                if not t_idx.empty:
                                    main_sheet.update_cell(int(t_idx[0])+2, 4, int(df.loc[t_idx[0], cols[3]] + m_amt))
                                else:
                                    main_sheet.append_row([target, row[cols[1]], row[cols[2]], int(m_amt)])
                                log_transaction(spreadsheet, "물품 전송", row[cols[1]], m_amt, target)
                                st.success("전송 완료!"); st.cache_data.clear(); time.sleep(1); st.rerun()

        # --- [3] 입출고 이력 조회 ---
        elif menu == "📜 입출고 이력":
            st.subheader("📜 최근 입출고 및 이동 기록")
            try:
                log_data = spreadsheet.worksheet("이력").get_all_records()
                if log_data:
                    log_df = pd.DataFrame(log_data)
                    st.dataframe(log_df.iloc[::-1], use_container_width=True) # 최신순
                else:
                    st.info("기록된 이력이 없습니다.")
            except:
                st.error("'이력' 시트를 찾을 수 없습니다. 구글 시트에 '이력' 시트를 만들어주세요.")

        # --- [4] 일정 달력 ---
        elif menu == "📅 일정 달력":
            st.subheader("📅 창고 및 업무 일정")
            calendar_url = "https://calendar.google.com/calendar/embed?src=ko.south_korea%23holiday%40group.v.calendar.google.com&ctz=Asia%2FSeoul"
            components.iframe(calendar_url, height=600, scrolling=True)

        # --- [5] 새 품목 등록 ---
        elif menu == "🆕 새 품목 등록":
            st.subheader("🆕 내 창고에 새 품목 추가")
            with st.form("new_item_form"):
                n = st.text_input("품목명").strip()
                s = st.text_input("규격").strip()
                q = st.number_input("초기 수량", 0)
                if st.form_submit_button("등록 완료"):
                    if n:
                        main_sheet.append_row([user_id, n, s, q])
                        log_transaction(spreadsheet, "새 품목 등록", n, q)
                        st.cache_data.clear()
                        st.success(f"'{n}' 등록되었습니다."); time.sleep(1); st.rerun()

        # --- [6] 계정 관리 (Admin 전용) ---
        elif menu == "👥 계정 관리" and role == "admin":
            st.subheader("👥 사용자 계정 추가")
            with st.form("new_user_form"):
                new_u = st.text_input("아이디(성함)").strip()
                new_p = st.text_input("비밀번호").strip()
                new_r = st.selectbox("권한", ["user", "admin"])
                if st.form_submit_button("사용자 생성"):
                    if new_u and new_p:
                        user_sheet.append_row([new_u, new_p, new_r])
                        main_sheet.append_row([new_u, "신규 창고 개설", "-", 0])
                        st.success(f"'{new_u}'님 계정 생성 완료."); st.cache_data.clear(); st.rerun()

except Exception as e:
    st.error(f"⚠️ 시스템 오류 발생: {e}")