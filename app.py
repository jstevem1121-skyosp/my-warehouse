import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="통합 창고 및 일정 관리 시스템", layout="wide")

# --- 2. 구글 시트 연결 및 캐싱 ---
@st.cache_resource
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = dict(st.secrets["gcp_service_account"])
    pk = creds_info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=2)
def fetch_sheet_data(sheet_url, worksheet_name):
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_url(sheet_url)
        return spreadsheet.worksheet(worksheet_name).get_all_records()
    except:
        return []

# --- 3. 로그인 로직 ---
def check_login(user_sheet_data):
    if "logged_in" not in st.session_state:
        st.session_state.update({"logged_in": False, "user_id": "", "role": None})
    if st.session_state["logged_in"]: return True

    st.title("🔐 시스템 로그인")
    user_df = pd.DataFrame(user_sheet_data)
    with st.form("login"):
        id_i = st.text_input("아이디(성함)").strip()
        pw_i = st.text_input("비밀번호", type="password").strip()
        if st.form_submit_button("로그인"):
            if not user_df.empty:
                user_row = user_df[(user_df['ID'].astype(str).str.strip() == id_i) & 
                                   (user_df['비밀번호'].astype(str).str.strip() == pw_i)]
                if not user_row.empty:
                    st.session_state.update({"logged_in": True, "user_id": id_i, "role": user_row.iloc[0]['권한']})
                    st.rerun()
                else: st.error("❌ 정보가 일치하지 않습니다.")
            else: st.error("❌ 사용자 데이터를 불러올 수 없습니다.")
    return False

# --- 메인 실행 ---
try:
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"
    user_data_list = fetch_sheet_data(SHEET_URL, "사용자")
    
    if check_login(user_data_list):
        client = get_gspread_client()
        spreadsheet = client.open_by_url(SHEET_URL)
        main_sheet = spreadsheet.sheet1
        user_sheet = spreadsheet.worksheet("사용자")
        
        # '일정' 시트 확인 및 생성 안내
        try: event_sheet = spreadsheet.worksheet("일정")
        except: event_sheet = None

        user_id = st.session_state["user_id"]
        role = st.session_state["role"]
        
        st.sidebar.info(f"👤 {user_id}님 ({role})")
        if st.sidebar.button("로그아웃"):
            st.session_state.clear()
            st.cache_data.clear()
            st.rerun()

        menu = st.sidebar.radio("메뉴 선택", ["🏠 전체 품목 현황", "📥 내 물품 관리/보내기", "📅 일정 관리", "🆕 새 품목 등록", "👥 계정 관리"])

        # 데이터 로드
        raw_inventory = main_sheet.get_all_records()
        df = pd.DataFrame(raw_inventory)
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
        cols = df.columns.tolist() # [소유자, 품목명, 규격, 수량]

        # --- 메뉴 1: 전체 품목 현황 (관리자 가져오기 포함) ---
        if menu == "🏠 전체 품목 현황":
            st.subheader("📊 전체 재고 소유 현황")
            items = df[df[cols[1]] != "신규 창고 개설"][cols[1]].unique()
            
            if len(items) == 0:
                st.info("등록된 품목이 없습니다.")
            else:
                for item in items:
                    item_df = df[df[cols[1]] == item]
                    total_q = item_df[cols[3]].sum()
                    with st.expander(f"📦 {item} (합계: {total_q}개)"):
                        display_df = item_df[item_df[cols[3]] > 0]
                        for i, row in display_df.iterrows():
                            c1, c2, c3 = st.columns([2, 1, 2])
                            c1.write(f"👤 소유자: **{row[cols[0]]}**")
                            c2.write(f"🔢 수량: {row[cols[3]]}")
                            if role == "admin" and row[cols[0]] != user_id:
                                t_amt = c3.number_input(f"수량", 1, int(row[cols[3]]), 1, key=f"t_{i}")
                                if c3.button(f"가져오기", key=f"b_{i}"):
                                    main_sheet.update_cell(i+2, 4, int(row[cols[3]] - t_amt))
                                    my_idx = df[(df[cols[0]] == user_id) & (df[cols[1]] == row[cols[1]]) & (df[cols[2]] == row[cols[2]])].index
                                    if not my_idx.empty:
                                        main_sheet.update_cell(int(my_idx[0])+2, 4, int(df.loc[my_idx[0], cols[3]] + t_amt))
                                    else:
                                        main_sheet.append_row([user_id, row[cols[1]], row[cols[2]], int(t_amt)])
                                    st.success("회수 완료!")
                                    st.cache_data.clear()
                                    time.sleep(1); st.rerun()
                            st.divider()

        # --- 메뉴 2: 내 물품 관리 및 보내기 ---
        elif menu == "📥 내 물품 관리/보내기":
            st.subheader(f"📥 {user_id}님의 창고")
            my_df = df[(df[cols[0]] == user_id) & (df[cols[1]] != "신규 창고 개설")]
            if my_df.empty:
                st.warning("보관 중인 품목이 없습니다.")
            else:
                for idx, row in my_df.iterrows():
                    with st.expander(f"🔹 {row[cols[1]]} [{row[cols[2]]}] - {row[cols[3]]}개"):
                        col1, col2 = st.columns(2)
                        with col1:
                            amt = st.number_input("수량", 1, 1000, 1, key=f"a_{idx}")
                            if st.button("입고", key=f"in_{idx}"):
                                main_sheet.update_cell(idx+2, 4, int(row[cols[3]] + amt))
                                st.cache_data.clear(); st.rerun()
                            if st.button("출고", key=f"ou_{idx}"):
                                if row[cols[3]] >= amt:
                                    main_sheet.update_cell(idx+2, 4, int(row[cols[3]] - amt))
                                    st.cache_data.clear(); st.rerun()
                                else: st.error("재고 부족")
                        with col2:
                            u_list = [str(u['ID']).strip() for u in user_data_list if str(u['ID']).strip() != user_id]
                            target = st.selectbox("받는 사람", u_list, key=f"tg_{idx}")
                            m_amt = st.number_input("보낼 수량", 1, int(row[cols[3]]), key=f"ma_{idx}")
                            if st.button("보내기", key=f"se_{idx}"):
                                main_sheet.update_cell(idx+2, 4, int(row[cols[3]] - m_amt))
                                t_idx = df[(df[cols[0]] == target) & (df[cols[1]] == row[cols[1]]) & (df[cols[2]] == row[cols[2]])].index
                                if not t_idx.empty:
                                    main_sheet.update_cell(int(t_idx[0])+2, 4, int(df.loc[t_idx[0], cols[3]] + m_amt))
                                else:
                                    main_sheet.append_row([target, row[cols[1]], row[cols[2]], int(m_amt)])
                                st.success("전달 완료!"); st.cache_data.clear(); time.sleep(1); st.rerun()

        # --- 메뉴 3: 📅 일정 관리 ---
        elif menu == "📅 일정 관리":
            st.subheader("📅 창고 및 물품 관련 일정")
            if event_sheet is None:
                st.error("구글 시트에 '일정' 탭을 만들어주세요. (헤더: 날짜, 일정명, 담당자, 내용)")
            else:
                with st.expander("➕ 새 일정 등록"):
                    with st.form("new_event"):
                        e_date = st.date_input("날짜")
                        e_title = st.text_input("일정명")
                        e_desc = st.text_area("내용")
                        if st.form_submit_button("일정 저장"):
                            event_sheet.append_row([str(e_date), e_title, user_id, e_desc])
                            st.success("일정 등록 완료!"); st.rerun()

                e_data = event_sheet.get_all_records()
                if e_data:
                    e_df = pd.DataFrame(e_data).sort_values(by="날짜", ascending=False)
                    st.write("### 최근 등록된 일정")
                    st.dataframe(e_df, use_container_width=True, hide_index=True)
                else: st.info("등록된 일정이 없습니다.")

        # --- 메뉴 4: 새 품목 등록 ---
        elif menu == "🆕 새 품목 등록":
            st.subheader("🆕 품목 신규 등록")
            with st.form("new_item"):
                n, s, q = st.text_input("품목명"), st.text_input("규격"), st.number_input("수량", 0)
                if st.form_submit_button("등록"):
                    main_sheet.append_row([user_id, n, s, q])
                    st.cache_data.clear(); st.success("등록 완료"); st.rerun()

        # --- 메뉴 5: 계정 관리 ---
        elif menu == "👥 계정 관리" and role == "admin":
            st.subheader("👥 계정 생성")
            with st.form("new_user"):
                u, p = st.text_input("ID"), st.text_input("PW")
                r = st.selectbox("권한", ["user", "admin"])
                if st.form_submit_button("생성"):
                    user_sheet.append_row([u, p, r])
                    main_sheet.append_row([u, "신규 창고 개설", "-", 0])
                    st.cache_data.clear(); st.success("계정 생성 완료"); st.rerun()

except Exception as e:
    st.error(f"⚠️ 시스템 오류: {e}")