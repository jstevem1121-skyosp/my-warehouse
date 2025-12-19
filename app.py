import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 구글 시트 URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"

def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # 1. Secrets에서 정보를 가져온 후 명시적으로 딕셔너리로 변환합니다.
    # st.secrets["gcp_service_account"] 자체가 딕셔너리처럼 작동하지만, 
    # 일부 환경에서는 dict()로 한 번 더 감싸주는 것이 안전합니다.
    creds_info = dict(st.secrets["gcp_service_account"])
    
    # 2. private_key 내부에 실제 줄바꿈이 필요한 경우를 대비해 처리 (선택 사항)
    if "\\n" in creds_info["private_key"]:
        creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        
    # 3. dict 데이터를 사용하여 인증을 수행합니다.
    return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope))

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