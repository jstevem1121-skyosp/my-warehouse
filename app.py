import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import re

# 구글 시트 URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"

def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
    # 1. Secrets에서 데이터 가져오기
    creds_info = dict(st.secrets["gcp_service_account"])
    pk = creds_info["private_key"]

    # 2. [불순물 제거 로직]
    # 헤더와 푸터 사이의 진짜 '암호 본문'만 추출
    if "-----BEGIN PRIVATE KEY-----" in pk:
        content = pk.split("-----BEGIN PRIVATE KEY-----")[1].split("-----END PRIVATE KEY-----")[0]
        
        # [핵심] Base64에 사용되는 문자(A-Z, a-z, 0-9, +, /, =)만 남기고 모두 제거
        # 유령 문자(\xa6\x90 등)를 여기서 완전히 걸러냅니다.
        clean_content = re.sub(r"[^A-Za-z0-9+/=]", "", content)
        
        # PEM 표준 규격(64자 줄바꿈)으로 재조립
        formatted_body = "\n".join([clean_content[i:i+64] for i in range(0, len(clean_content), 64)])
        pk = f"-----BEGIN PRIVATE KEY-----\n{formatted_body}\n-----END PRIVATE KEY-----\n"

    creds_info["private_key"] = pk

    # 3. 인증 시도
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
        st.success("✅ 드디어 연결에 성공했습니다!")
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    else:
        st.info("시트에 데이터가 없습니다.")

except Exception as e:
    st.error(f"❌ 연결 실패: {e}")
    st.exception(e)