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

    # 2. [서명 에러 방지] Private Key 정밀 재조립
    # 헤더와 푸터를 제외한 순수 암호 본문만 추출
    if "-----BEGIN PRIVATE KEY-----" in pk:
        # 모든 종류의 줄바꿈 기호와 공백을 완전히 제거하여 한 줄로 만듦
        content = pk.replace("-----BEGIN PRIVATE KEY-----", "").replace("-----END PRIVATE KEY-----", "")
        clean_content = re.sub(r"\s+", "", content) # 보이지 않는 모든 공백 제거
        
        # 구글 서버가 좋아하는 64자 줄바꿈 규격으로 정밀 재구성
        lines = [clean_content[i:i+64] for i in range(0, len(clean_content), 64)]
        pk = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END PRIVATE KEY-----\n"
    
    creds_info["private_key"] = pk

    # 3. 인증 시도
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(creds)

st.title("🌐 온라인 창고 관리 시스템")

try:
    client = get_gspread_client()
    sheet = client.open_by_url(SHEET_URL).sheet1
    data = sheet.get_all_records()
    
    if data:
        st.success("✅ 드디어 모든 보안 관문을 통과했습니다!")
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    else:
        st.info("연결 성공! 현재 시트에 데이터가 없습니다.")
except Exception as e:
    st.error(f"❌ 최종 연결 시도 실패: {e}")
    st.info("만약 이 에러가 지속되면, 구글 클라우드에서 '새 JSON 키'를 다시 발급받는 것이 가장 빠릅니다.")