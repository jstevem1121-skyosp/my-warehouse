import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import json

st.set_page_config(page_title="온라인 창고 관리", layout="wide")

def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # 1. Secrets에서 json_data 문자열을 통째로 가져옵니다.
    json_string = st.secrets["gcp_service_account"]["json_data"]
    
    # 2. 문자열을 파이썬 딕셔너리로 변환합니다.
    creds_info = json.loads(json_string)
    
    # 3. 인증 진행
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
    return gspread.authorize(creds)

try:
    client = get_gspread_client()
    # 구글 시트 제목이 'inventory_data'인지 다시 한번 확인하세요!
    sheet = client.open("inventory_data").sheet1
    
    st.title("🌐 온라인 창고 관리 시스템")
    st.success("✅ 드디어 연결에 성공했습니다!")

    # 데이터 읽기 및 화면 구성 (생략 - 이전과 동일)
    rows = sheet.get_all_records()
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

except Exception as e:
    st.error(f"⚠️ 에러 내용: {e}")
    st.info("시트 이름이 'inventory_data'가 맞는지, 공유 설정에 서비스 계정 이메일이 있는지 확인하세요.")