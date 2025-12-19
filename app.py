import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import re

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

# --- 수량 변경 함수 ---
def update_stock(sheet, row_idx, current_qty, change):
    new_qty = current_qty + change
    if new_qty < 0:
        st.error("재고는 0보다 작을 수 없습니다!")
        return
    # 구글 시트는 1부터 시작하며, 헤더가 1번이므로 row_idx + 2를 함 (get_all_records 기준)
    # 실제 데이터의 위치: 인덱스 0번 데이터는 시트의 2행에 있음
    sheet.update_cell(row_idx + 2, list(df.columns).index('수량') + 1, new_qty)
    st.toast(f"수량이 {new_qty}로 변경되었습니다!")
    st.rerun()

# --- UI 설정 ---
st.set_page_config(page_title="온라인 창고 관리", layout="wide")
st.title("🌐 온라인 창고 관리 시스템")

try:
    client = get_gspread_client()
    sheet = client.open_by_url(SHEET_URL).sheet1
    data = sheet.get_all_records()
    
    if data:
        df = pd.DataFrame(data)
        if '수량' in df.columns:
            df['수량'] = pd.to_numeric(df['수량'], errors='coerce').fillna(0).astype(int)

        # --- 사이드바 메뉴 ---
        st.sidebar.title("📦 창고 관리 메뉴")
        menu = st.sidebar.radio("이동할 메뉴", ["재고 현황", "간편 입출고", "설정"])

        if menu == "재고 현황":
            # 1. 요약 메트릭
            col1, col2, col3 = st.columns(3)
            with col1: st.metric("전체 품목", f"{len(df)}종")
            with col2:
                low_stock = len(df[(df['수량'] <= 5) & (df['수량'] > 0)])
                st.metric("품절 임박", f"{low_stock}종", delta="-발주필요", delta_color="inverse")
            with col3:
                out_of_stock = len(df[df['수량'] <= 0])
                st.metric("품절(위험)", f"{out_of_stock}종", delta="재고없음", delta_color="normal")

            st.divider()

            # 2. 검색창
            search_term = st.text_input("🔍 검색어 입력 (품목, 규격 등)", placeholder="찾으시는 물건을 입력하세요...")
            filtered_df = df[df.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)] if search_term else df

            # 3. 데이터 표시 (스타일링 적용)
            def highlight_stock(s):
                if s['수량'] <= 0: return ['background-color: #ffcccc'] * len(s)
                elif s['수량'] <= 5: return ['background-color: #fff4cc'] * len(s)
                return [''] * len(s)

            st.dataframe(filtered_df.style.apply(highlight_stock, axis=1), use_container_width=True, hide_index=True)

        elif menu == "간편 입출고":
            st.subheader("🛠️ 수량 간편 조정")
            st.info("각 품목의 버튼을 눌러 재고를 즉시 수정할 수 있습니다.")
            
            # 검색 기능 (입출고 메뉴에서도 검색 가능하게)
            edit_search = st.text_input("수정할 품목 검색", key="edit_search")
            display_df = df[df.astype(str).apply(lambda x: x.str.contains(edit_search, case=False)).any(axis=1)] if edit_search else df

            # 표 형태 대신 버튼이 포함된 리스트 형태로 출력
            for idx, row in display_df.iterrows():
                with st.container():
                    c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
                    c1.write(f"**{row.get('품목명', '이름없음')}** ({row.get('규격', '-')})")
                    c2.write(f"현재 재고: `{row['수량']}`")
                    
                    # 입고 버튼
                    if c3.button(f"➕ 입고 (+1)", key=f"in_{idx}"):
                        update_stock(sheet, idx, row['수량'], 1)
                    
                    # 출고 버튼
                    if c4.button(f"➖ 출고 (-1)", key=f"out_{idx}"):
                        update_stock(sheet, idx, row['수량'], -1)
                st.divider()

    else:
        st.info("연결 성공! 현재 시트에 데이터가 없습니다.")

except Exception as e:
    st.error(f"❌ 오류 발생: {e}")