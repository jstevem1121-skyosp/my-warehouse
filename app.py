import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

st.set_page_config(page_title="온라인 창고 관리", layout="wide")

def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # 설정(Secrets)에서 키 정보를 딕셔너리로 가져오기
    # 이 부분이 틀리면 연결 에러가 발생합니다.
    creds_info = st.secrets["gcp_service_account"]
    
    # 딕셔너리 안의 private_key 내 줄바꿈(\n) 문자 보정
    if isinstance(creds_info, dict):
        creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
    return gspread.authorize(creds)

try:
    client = get_gspread_client()
    # 시트 이름이 'inventory_data'인지 꼭 확인하세요!
    sheet = client.open("inventory_data").sheet1
    
    st.title("🌐 온라인 창고 관리 시스템")
    st.success("✅ 구글 시트 연결 성공!")

    rows = sheet.get_all_records()
    df = pd.DataFrame(rows)

    with st.form("add_form"):
        c1, c2, c3 = st.columns(3)
        wh = c1.text_input("창고")
        item = c2.text_input("품목")
        qty = c3.number_input("수량", min_value=0)
        if st.form_submit_button("등록"):
            sheet.append_row([wh, item, qty])
            st.rerun()

    st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(f"⚠️ 연결 에러: {e}")
    st.info("Streamlit App Settings의 Secrets 메뉴에 [gcp_service_account]를 올바르게 입력했는지 확인하세요.")