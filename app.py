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
    raw_pk = creds_info["private_key"]

    # 2. [초강력 필터] Base64 문자만 남기고 싹 다 제거 (찌꺼기 바이트 원천 봉쇄)
    # 헤더와 푸터를 제외한 본문에서 A-Z, a-z, 0-9, +, /, = 만 골라냅니다.
    core_body = re.sub(r"[^A-Za-z0-9+/=]", "", raw_pk.replace("-----BEGIN PRIVATE KEY-----", "").replace("-----END PRIVATE KEY-----", ""))
    
    # 3. 깨끗해진 본문을 다시 표준 PEM 형식으로 조립
    clean_pk = "-----BEGIN PRIVATE KEY-----\n"
    # 64자마다 줄바꿈 추가
    for i in range(0, len(core_body), 64):
        clean_pk += core_body[i:i+64] + "\n"
    clean_pk += "-----END PRIVATE KEY-----\n"
    
    # 보정된 키를 다시 삽입
    creds_info["private_key"] = clean_pk

    # 4. 인증 시도
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
        st.success("✅ 드디어 모든 장애물을 넘고 연결에 성공했습니다!")
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    else:
        st.info("연결은 성공했으나, 시트에 데이터가 없습니다.")

except Exception as e:
    st.error(f"❌ 연결 실패: {e}")
    st.write("🔧 해결 팁: 이 에러가 계속되면 구글 시트에서 '공유' 버튼을 눌러 서비스 계정 이메일이 추가되어 있는지 확인하세요.")
    st.exception(e)