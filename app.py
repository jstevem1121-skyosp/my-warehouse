import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import re

# 구글 시트 URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"

def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
    # 1. Secrets에서 데이터 가져오기 (불변 객체이므로 딕셔너리로 복사)
    creds_info = dict(st.secrets["gcp_service_account"])
    pk = creds_info["private_key"]

    # 2. [Base64 규격 정밀 보정]
    if "-----BEGIN PRIVATE KEY-----" in pk:
        # 헤더/푸터 제외한 본문만 추출 및 모든 공백/줄바꿈 제거
        content = pk.split("-----BEGIN PRIVATE KEY-----")[1].split("-----END PRIVATE KEY-----")[0]
        clean_content = re.sub(r"\s+", "", content)
        
        # 4의 배수가 되도록 끝에 '=' 패딩 추가 (에러 원인 해결)
        missing_padding = len(clean_content) % 4
        if missing_padding:
            clean_content += "=" * (4 - missing_padding)
        
        # 표준 PEM 형식(64자 줄바꿈)으로 재조립
        formatted_body = "\n".join([clean_content[i:i+64] for i in range(0, len(clean_content), 64)])
        pk = f"-----BEGIN PRIVATE KEY-----\n{formatted_body}\n-----END PRIVATE KEY-----\n"

    creds_info["private_key"] = pk

    # 3. 인증 시도
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(creds)

st.set_page_config(page_title="온라인 창고 관리", layout="wide")
st.title("🌐 온라인 창고 관리 시스템")

try:
    client = get_gspread_client()
    sheet = client.open_by_url(SHEET_URL).sheet1
    
    data = sheet.get_all_records()
    if data:
        st.success("✅ 축하합니다! 모든 보안 관문을 통과해 연결에 성공했습니다.")
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    else:
        st.info("연결 성공! 현재 시트에 표시할 데이터가 없습니다.")

except Exception as e:
    st.error(f"❌ 연결 실패: {e}")
    st.warning("도움말: 이 메시지가 계속되면 Secrets 창의 private_key 끝에 따옴표 세 개(\"\"\")가 잘 닫혔는지 확인하세요.")