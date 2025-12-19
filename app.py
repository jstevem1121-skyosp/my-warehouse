import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import re
from datetime import datetime

# 구글 시트 URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"

# --- 구글 시트 연결 함수 ---
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

# --- 수량 변경 및 로그 기록 함수 (통합 버전) ---
def update_stock(main_sheet, log_sheet, row_idx, item_name, current_qty, change, is_direct=False):
    # is_direct가 True면 change 자체가 새로운 수량이 됨
    if is_direct:
        new_qty = change
        diff = new_qty - current_qty
    else:
        new_qty = current_qty + change
        diff = change

    if new_qty < 0:
        st.error("재고는 0보다 작을 수 없습니다!")
        return
    
    try:
        qty_col_idx = list(df.columns).index('수량') + 1
        main_sheet.update_cell(row_idx + 2, qty_col_idx, int(new_qty))
        
        # 로그 기록
        if diff != 0:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            change_text = f"+{diff}" if diff > 0 else str(diff)
            if log_sheet:
                log_sheet.append_row([now, item_name, change_text, int(new_qty)])
        
        st.toast(f"✅ {item_name}: {new_qty}개로 업데이트 완료!")
        st.rerun()
    except Exception as e:
        st.error(f"업데이트 중 오류 발생: {e}")

# --- UI 설정 ---
st.set_page_config(page_title="온라인 창고 관리", layout="wide")
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
        if '수량' in df.columns:
            df['수량'] = pd.to_numeric(df['수량'], errors='coerce').fillna(0).astype(int)

        # --- 사이드바 메뉴 ---
        st.sidebar.title("📦 창고 관리 메뉴")
        menu = st.sidebar.radio("이동할 메뉴", ["재고 현황", "간편 입출고", "활동 로그"])

        if menu == "재고 현황":
            # 요약 메트릭 및 대시보드 (기존과 동일)
            col1, col2, col3 = st.columns(3)
            with col1: st.metric("전체 품목", f"{len(df)}종")
            with col2:
                low_stock = len(df[(df['수량'] <= 5) & (df['수량'] > 0)])
                st.metric("품절 임박", f"{low_stock}종", delta="-발주필요", delta_color="inverse")
            with col3:
                out_of_stock = len(df[df['수량'] <= 0])
                st.metric("품절(위험)", f"{out_of_stock}종", delta="재고없음", delta_color="normal")
            st.divider()
            search_term = st.text_input("🔍 재고 검색", placeholder="품목명을 입력하세요...")
            filtered_df = df[df.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)] if search_term else df
            st.dataframe(filtered_df, use_container_width=True, hide_index=True)

        elif menu == "간편 입출고":
            st.subheader("🛠️ 수량 상세 조정")
            edit_search = st.text_input("수정할 품목 검색", placeholder="이름을 입력하면 해당 품목만 나타납니다.")
            display_df = df[df.astype(str).apply(lambda x: x.str.contains(edit_search, case=False)).any(axis=1)] if edit_search else df

            for idx, row in display_df.iterrows():
                with st.expander(f"📦 {row.get('품목명', '이름없음')} (현재: {row['수량']}개)", expanded=True):
                    c1, c2 = st.columns([1, 1])
                    
                    with c1:
                        st.write("**증감 조절 (-1 / +1)**")
                        btn_col1, btn_col2 = st.columns(2)
                        if btn_col1.button(f"➖ 출고", key=f"out_{idx}"):
                            update_stock(main_sheet, log_sheet, idx, row['품목명'], row['수량'], -1)
                        if btn_col2.button(f"➕ 입고", key=f"in_{idx}"):
                            update_stock(main_sheet, log_sheet, idx, row['품목명'], row['수량'], 1)
                    
                    with c2:
                        st.write("**수량 직접 입력**")
                        new_input = st.number_input("최종 수량 설정", value=int(row['수량']), key=f"num_{idx}", step=1)
                        if st.button("수량 확정", key=f"set_{idx}"):
                            if new_input != row['수량']:
                                update_stock(main_sheet, log_sheet, idx, row['품목명'], row['수량'], new_input, is_direct=True)
                            else:
                                st.warning("현재 수량과 같습니다.")

        elif menu == "활동 로그":
            st.subheader("📜 최근 활동 내역")
            if log_sheet:
                log_data = log_sheet.get_all_values()
                if len(log_data) > 1:
                    log_df = pd.DataFrame(log_data[1:], columns=log_data[0] if log_data[0] else ['일시', '품목명', '변동', '최종재고'])
                    st.dataframe(log_df.iloc[::-1].head(30), use_container_width=True)
                else: st.info("아직 기록된 로그가 없습니다.")
            else: st.error("구글 시트에 '로그' 탭을 만들어주세요.")

except Exception as e:
    st.error(f"❌ 오류 발생: {e}")