import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import base64
import json

# 구글 시트 URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"

def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
    # 1. Base64로 인코딩된 안전한 문자열을 가져옴
    encoded_key = st.secrets["encoded_gcp_key"]
    
    # 2. 디코딩하여 원본 JSON 데이터(바이트)로 복구
    # 이 과정에서 b'\xa6\x90' 같은 유령 문자가 원천 차단됩니다.
    decoded_key = base64.b64decode(encoded_key).decode('utf-8')
    creds_info = json.loads(decoded_key)
    
    # 3. 인증 수행
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(creds)

# UI 설정
st.set_page_config(page_title="온라인 창고 관리", layout="wide")
st.title("🌐 온라인 창고 관리 시스템")

try:
    client = get_gspread_client()
    sheet = client.open_by_url(SHEET_URL).sheet1
    data = sheet.get_all_records()
    
    if data:
        st.success("✅ 완벽하게 연결되었습니다!")
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    else:
        st.info("연결 성공! 하지만 시트 데이터가 비어있습니다.")

except Exception as e:
    st.error(f"❌ 연결 실패: {e}")
    st.exception(e)