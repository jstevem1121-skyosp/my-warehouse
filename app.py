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
        # 데이터프레임 변환
        df = pd.DataFrame(data)
        
        # --- 1단계: 상단 대시보드 요약 (간단하게) ---
        col1, col2 = st.columns(2)
        with col1:
            st.metric("총 품목 수", f"{len(df)}개")
        with col2:
            # '재고량' 혹은 '수량' 컬럼이 있다면 합계 표시 가능
            if '수량' in df.columns:
                st.metric("총 재고량", f"{df['수량'].sum()}개")

        st.divider() # 구분선

        # --- 2단계: 검색 기능 ---
        st.subheader("🔍 재고 검색")
        search_term = st.text_input("검색어를 입력하세요 (품목명, 규격, 위치 등)", "")
        
        # 전체 열에서 검색어가 포함된 행 필터링
        if search_term:
            filtered_df = df[df.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)]
        else:
            filtered_df = df

        # --- 3단계: 테이블 출력 ---
        st.success(f"✅ 현재 재고 현황 (결과: {len(filtered_df)}건)")
        st.dataframe(
            filtered_df, 
            use_container_width=True, 
            hide_index=True
        )
        
    else:
        st.info("연결 성공! 현재 시트에 데이터가 없습니다.")

except Exception as e:
    st.error(f"❌ 오류 발생: {e}")
    st.exception(e)