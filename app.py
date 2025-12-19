import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# 구글 시트 URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"

def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
    # 1. Secrets에서 [gcp_service_account] 섹션을 딕셔너리로 가져옵니다.
    creds_info = st.secrets["gcp_service_account"]
    
    # 2. 구글 인증 객체 생성
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(creds)

st.set_page_config(page_title="온라인 창고 관리", layout="wide")
st.title("🌐 온라인 창고 관리 시스템")

try:
    client = get_gspread_client()
    sheet = client.open_by_url(SHEET_URL).sheet1
    
    data = sheet.get_all_records()
    if data:
        st.success("✅ 연결 성공! 데이터를 불러왔습니다.")
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    else:
        st.info("시트에 데이터가 없습니다.")

except Exception as e:
    st.error(f"❌ 연결 실패: {e}")
    st.info("Secrets 설정창에 [gcp_service_account] 섹션이 있는지 다시 확인해주세요.")