import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import re

# 구글 시트 URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"

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

# --- UI 설정 ---
st.set_page_config(page_title="온라인 창고 관리", layout="wide")
st.title("🌐 온라인 창고 관리 시스템")

try:
    client = get_gspread_client()
    sheet = client.open_by_url(SHEET_URL).sheet1
    data = sheet.get_all_records()
    
    if data:
        df = pd.DataFrame(data)
        
        # --- [추가] 사이드바 메뉴 구성 ---
        st.sidebar.title("📦 창고 관리 메뉴")
        menu = st.sidebar.radio("이동할 메뉴", ["재고 현황", "입출고 기록(준비중)", "설정"])

        if menu == "재고 현황":
            # --- 1. 요약 메트릭 ---
            col1, col2, col3 = st.columns(3)
            
            # 수량 데이터가 숫자가 아닐 경우를 대비해 변환
            if '수량' in df.columns:
                df['수량'] = pd.to_numeric(df['수량'], errors='coerce').fillna(0)

            with col1:
                st.metric("전체 품목", f"{len(df)}종")
            with col2:
                low_stock = len(df[(df['수량'] <= 5) & (df['수량'] > 0)]) if '수량' in df.columns else 0
                st.metric("품절 임박", f"{low_stock}종", delta="-발주필요", delta_color="inverse")
            with col3:
                out_of_stock = len(df[df['수량'] <= 0]) if '수량' in df.columns else 0
                st.metric("품절(위험)", f"{out_of_stock}종", delta="재고없음", delta_color="normal")

            st.divider()

            # --- 2. 검색창 ---
            search_term = st.text_input("🔍 검색어 입력 (품목, 규격 등)", placeholder="찾으시는 물건을 입력하세요...")
            
            if search_term:
                filtered_df = df[df.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)]
            else:
                filtered_df = df

            # --- 3. 조건부 색상 스타일링 함수 ---
            def highlight_stock(s):
                if '수량' in s.index:
                    if s['수량'] <= 0:
                        return ['background-color: #ffcccc'] * len(s) # 품절: 연빨강
                    elif s['수량'] <= 5:
                        return ['background-color: #fff4cc'] * len(s) # 부족: 연주황
                return [''] * len(s)

            st.success(f"✅ 현재 재고 현황 (결과: {len(filtered_df)}건)")
            
            # 스타일 적용하여 출력
            if not filtered_df.empty:
                styled_df = filtered_df.style.apply(highlight_stock, axis=1)
                st.dataframe(styled_df, use_container_width=True, hide_index=True)
            else:
                st.warning("검색 결과가 없습니다.")
        
        else:
            st.info(f"'{menu}' 메뉴는 현재 준비 중입니다.")
            
    else:
        st.info("연결 성공! 현재 시트에 데이터가 없습니다.")

except Exception as e:
    st.error(f"❌ 오류 발생: {e}")
    st.exception(e)