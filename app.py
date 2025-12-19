import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 구글 시트 URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"

def get_gspread_client():
    # 권한 범위 설정
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Streamlit Secrets에서 설정 정보를 딕셔너리로 가져옴
    creds_dict = dict(st.secrets["gcp_service_account"])
    
    # 인증 수행
    return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope))

# UI 설정
st.set_page_config(page_title="온라인 창고 관리", layout="wide")
st.title("🌐 온라인 창고 관리 시스템")

try:
    client = get_gspread_client()
    sheet = client.open_by_url(SHEET_URL).sheet1
    
    # 데이터 불러오기 및 UI 로직 (기존과 동일)
    data = sheet.get_all_records()
    if data:
        st.success("✅ 창고 시스템 연결 성공!")
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("현재 창고에 등록된 데이터가 없습니다.")

except Exception as e:
    st.error(f"❌ 연결 실패: {e}")