import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json

SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"

def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
    # Secrets에서 가져온 정보를 dict로 변환
    creds_info = dict(st.secrets["gcp_service_account"])
    
    # \n 문자열을 실제 줄바꿈 바이트로 복구 (이게 핵심입니다)
    creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
    
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(creds)

st.title("🌐 온라인 창고 관리 시스템")

try:
    client = get_gspread_client()
    sheet = client.open_by_url(SHEET_URL).sheet1
    data = sheet.get_all_records()
    
    if data:
        st.success("✅ 드디어 연결에 성공했습니다!")
        st.dataframe(pd.DataFrame(data))
    else:
        st.info("연결은 성공했으나 데이터가 없습니다.")
except Exception as e:
    st.error(f"❌ 에러 발생: {e}")