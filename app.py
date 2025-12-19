import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import re
from datetime import datetime

# --- 페이지 설정 ---
st.set_page_config(page_title="개인별 창고 관리 시스템", layout="wide")

# --- 1. 로그인 로직 ---
def check_login():
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
        st.session_state["user_id"] = ""
        st.session_state["role"] = None

    if st.session_state["logged_in"]:
        return True

    st.title("🔒 개인별 창고 관리 시스템")
    user_id_input = st.text_input("사용자 성함(ID)", placeholder="본인 이름을 입력하세요")
    pwd_input = st.text_input("비밀번호", type="password")
    
    if st.button("내 창고 접속"):
        if not user_id_input:
            st.error("성함을 입력해주세요.")
        elif pwd_input == str(st.secrets["app_password"]):
            st.session_state.update({"logged_in": True, "user_id": user_id_input, "role": "admin"})
            st.rerun()
        elif pwd_input == str(st.secrets["user_password"]):
            st.session_state.update({"logged_in": True, "user_id": user_id_input, "role": "user"})
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    return False

@st.cache_resource
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = dict(st.secrets["gcp_service_account"])
    pk = creds_info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(creds)

# --- 메인 실행 ---
if check_login():
    user_id = st.session_state["user_id"]
    role = st.session_state["role"]
    
    st.sidebar.info(f"👤 {user_id}님의 창고")
    if st.sidebar.button("로그아웃"):
        st.session_state.clear()
        st.rerun()

    SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"
    
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_url(SHEET_URL)
        main_sheet = spreadsheet.sheet1
        try: log_sheet = spreadsheet.worksheet("로그")
        except: log_sheet = None

        # 데이터 로딩
        raw_data = main_sheet.get_all_records()
        full_df = pd.DataFrame(raw_data)
        
        # 컬럼 인덱스 찾기
        cols = list(full_df.columns)
        owner_idx = next(i for i, c in enumerate(cols) if '소유' in str(c) or 'ID' in str(c))
        name_idx = next(i for i, c in enumerate(cols) if '품목' in str(c))
        qty_idx = next(i for i, c in enumerate(cols) if '수량' in str(c))

        # 사용자별 필터링
        df = full_df if role == "admin" else full_df[full_df[cols[owner_idx]] == user_id]

        menu = st.sidebar.radio("메뉴", ["내 재고 현황", "입출고 및 이동", "신규 품목 등록"])

        if menu == "내 재고 현황":
            st.subheader(f"📊 {user_id}님의 재고 현황")
            st.dataframe(df, use_container_width=True, hide_index=True)

        elif menu == "입출고 및 이동":
            st.subheader("📥 물품 관리 및 유저 간 이동")
            if df.empty:
                st.warning("창고가 비어있습니다.")
            else:
                for idx, row in df.iterrows():
                    with st.expander(f"📦 {row[cols[name_idx]]} (현재 수량: {row[cols[qty_idx]]})"):
                        t1, t2 = st.tabs(["일반 입출고", "🎁 타 유저에게 보내기"])
                        
                        # 일반 입출고 탭
                        with t1:
                            amt = st.number_input("수량 설정", 1, 1000, 1, key=f"amt{idx}")
                            c1, c2 = st.columns(2)
                            if c1.button("입고", key=f"in{idx}"):
                                new_q = int(row[cols[qty_idx]] + amt)
                                main_sheet.update_cell(idx+2, qty_idx+1, new_q)
                                if log_sheet: log_sheet.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id, row[cols[name_idx]], f"+{amt} (입고)", new_q])
                                st.rerun()
                            if c2.button("출고", key=f"out{idx}"):
                                new_q = int(row[cols[qty_idx]] - amt)
                                if new_q < 0: st.error("재고 부족")
                                else:
                                    main_sheet.update_cell(idx+2, qty_idx+1, new_q)
                                    if log_sheet: log_sheet.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id, row[cols[name_idx]], f"-{amt} (출고)", new_q])
                                    st.rerun()

                        # 유저 간 이동 탭
                        with t2:
                            # 현재 시스템을 사용 중인 유저 목록 추출 (나 제외)
                            all_users = sorted(list(set(full_df[cols[owner_idx]].unique())))
                            if user_id in all_users: all_users.remove(user_id)
                            
                            target_user = st.selectbox("받는 사람 선택", all_users, key=f"target{idx}")
                            move_amt = st.number_input("보낼 수량", 1, int(row[cols[qty_idx]]) if int(row[cols[qty_idx]]) > 0 else 1, key=f"m_amt{idx}")
                            
                            if st.button("보내기 실행", key=f"move{idx}"):
                                if int(row[cols[qty_idx]]) < move_amt:
                                    st.error("창고에 남은 수량이 부족합니다.")
                                else:
                                    # 1. 내 창고에서 차감
                                    my_new_q = int(row[cols[qty_idx]] - move_amt)
                                    main_sheet.update_cell(idx+2, qty_idx+1, my_new_q)
                                    
                                    # 2. 상대방 창고에 추가 (상대방의 해당 품목이 있는지 확인)
                                    target_item_row = full_df[(full_df[cols[owner_idx]] == target_user) & (full_df[cols[name_idx]] == row[cols[name_idx]])]
                                    
                                    if not target_item_row.empty:
                                        # 상대방에게 이미 해당 물건이 있으면 수량만 플러스
                                        target_idx = target_item_row.index[0]
                                        target_new_q = int(target_item_row.iloc[0][cols[qty_idx]] + move_amt)
                                        main_sheet.update_cell(target_idx+2, qty_idx+1, target_new_q)
                                    else:
                                        # 상대방에게 물건이 없으면 새로 행 추가
                                        new_row = [target_user, row[cols[name_idx]], row[cols[name_idx]-1 if name_idx>0 else 0], move_amt] # 소유자, 품목명, 규격, 수량 순
                                        main_sheet.append_row(new_row)
                                    
                                    # 3. 로그 기록
                                    if log_sheet:
                                        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                        log_sheet.append_row([now, user_id, row[cols[name_idx]], f"보냄 -> {target_user}", my_new_q])
                                        log_sheet.append_row([now, target_user, row[cols[name_idx]], f"받음 <- {user_id}", "확인필요"])
                                    
                                    st.success(f"{target_user}님에게 {move_amt}개를 보냈습니다!")
                                    st.rerun()

        elif menu == "신규 품목 등록":
            st.subheader("🆕 내 창고 신규 등록")
            with st.form("add"):
                n, s, q = st.text_input("품목명"), st.text_input("규격"), st.number_input("초기 수량", 0)
                if st.form_submit_button("등록"):
                    main_sheet.append_row([user_id, n, s, q])
                    st.rerun()

    except Exception as e:
        st.error(f"오류: {e}")