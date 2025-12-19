import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import io

# 구글 시트 URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"

def get_gspread_client():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # 1. Secrets에서 데이터 가져오기 (딕셔너리로 복사)
    creds_info = dict(st.secrets["gcp_service_account"])
    
    # 2. [초강력 보정] 문자열을 바이트로 강제 처리
    pk = creds_info["private_key"]
    
    # 혹시 모를 이스케이프된 줄바꿈(\n 글자 자체)을 실제 줄바꿈으로 변경
    pk = pk.replace("\\n", "\n")
    
    # 불필요한 따옴표나 공백 완벽 제거
    pk = pk.strip().strip('"').strip("'")
    
    # RSA 키 규격에 맞게 헤더/푸터 재정렬 (공백 방지)
    if "-----BEGIN PRIVATE KEY-----" in pk:
        parts = pk.split("-----BEGIN PRIVATE KEY-----")
        body = parts[1].split("-----END PRIVATE KEY-----")
        # 헤더와 푸터 사이의 본문만 추출하여 줄바꿈 정리
        content = body[0].replace(" ", "").replace("\n", "").strip()
        
        # 64자마다 줄바꿈을 넣은 표준 PEM 형식 재구성
        formatted_content = "\n".join([content[i:i+64] for i in range(0, len(content), 64)])
        pk = f"-----BEGIN PRIVATE KEY-----\n{formatted_content}\n-----END PRIVATE KEY-----\n"

    creds_info["private_key"] = pk

    # 3. 인증 시도 (from_service_account_info 사용)
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
    # 상세 에러 원인 분석을 위해 출력
    st.write("에러 타입:", type(e).__name__)
    st.exception(e)