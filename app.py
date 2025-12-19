import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import re

# 구글 시트 URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"

def get_gspread_client():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # 1. Secrets에서 데이터 가져오기
    creds_info = dict(st.secrets["gcp_service_account"])
    
    # 2. [핵심] Private Key 정밀 보정
    pk = creds_info["private_key"]
    
    # 혹시 모를 양끝의 따옴표나 공백 제거
    pk = pk.strip().strip('"').strip("'")
    
    # \n 문자가 글자 그대로 들어온 경우 실제 줄바꿈으로 변경
    pk = pk.replace("\\n", "\n")
    
    # 만약 줄바꿈이 아예 없는 통짜 문자열이라면, 64자마다 줄바꿈을 넣어 암호 규격 강제 준수
    if "\n" not in pk.replace("-----BEGIN PRIVATE KEY-----", "").replace("-----END PRIVATE KEY-----", "").strip():
        header = "-----BEGIN PRIVATE KEY-----"
        footer = "-----END PRIVATE KEY-----"
        content = pk.replace(header, "").replace(footer, "").replace("\n", "").strip()
        # 64자 단위로 자르기
        lines = [content[i:i+64] for i in range(0, len(content), 64)]
        pk = header + "\n" + "\n".join(lines) + "\n" + footer
    
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
        st.success("✅ 창고 시스템 연결 성공!")
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    else:
        st.info("현재 창고에 등록된 데이터가 없습니다.")

except Exception as e:
    st.error(f"❌ 연결 실패: {e}")
    st.exception(e) # 에러 상세 내용 출력