import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# 1. 시트 설정
SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"

def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # Secrets에서 통째로 가져오기
    creds_info = st.secrets["gcp_service_account"]
    return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope))

st.set_page_config(page_title="온라인 창고 관리", layout="wide")
st.title("🌐 온라인 창고 관리 시스템")

try:
    client = get_gspread_client()
    sheet = client.open_by_url(SHEET_URL).sheet1
    
    # 데이터 읽기
    data = sheet.get_all_records()
    st.success("✅ 구글 시트와 완벽하게 연결되었습니다!")
    
    # (이하 기존 출력 로직 동일...)
    if data:
        st.subheader("📊 실시간 재고 현황")
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"⚠️ 연결 실패: {e}")
    st.info("아래 'Secrets 설정 방법'을 따라 새 키를 등록해 주세요.")