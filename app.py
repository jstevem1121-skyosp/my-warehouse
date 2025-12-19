import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials  # 라이브러리 교체

# 구글 시트 URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"

def get_gspread_client():
    # 권한 범위 설정
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # 1. Secrets에서 정보 가져오기
    creds_info = dict(st.secrets["gcp_service_account"])
    
    # 2. 전처리: private_key의 이스케이프 문자 처리
    # (이미 TOML에서 """를 썼다면 불필요할 수 있지만 안전을 위해 유지)
    if "\\n" in creds_info["private_key"]:
        creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        
    # 3. 새로운 방식의 Credentials 생성 (더 안정적임)
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    
    # 4. gspread 인증
    return gspread.authorize(creds)

# UI 설정
st.set_page_config(page_title="온라인 창고 관리", layout="wide")
st.title("🌐 온라인 창고 관리 시스템")

try:
    client = get_gspread_client()
    # URL로 열기
    sheet = client.open_by_url(SHEET_URL).sheet1
    
    data = sheet.get_all_records()
    if data:
        st.success("✅ 창고 시스템 연결 성공!")
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("현재 창고에 등록된 데이터가 없습니다.")
        # 데이터가 없을 때를 위해 컬럼명이라도 보고 싶다면:
        # st.write(sheet.row_values(1))

except Exception as e:
    st.error(f"❌ 연결 실패: {e}")
    # 상세 에러 확인용 (디버깅)
    st.exception(e)