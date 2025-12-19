import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import json

# 페이지 설정
st.set_page_config(page_title="온라인 창고 관리", layout="wide")

# --- 구글 시트 연결 함수 ---
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Secrets 정보를 딕셔너리로 가져오기
    # 스트림릿 Secrets는 TOML 형식이므로 딕셔너리로 바로 변환됩니다.
    creds_dict = dict(st.secrets["gcp_service_account"])
    
    # 만약 private_key 안의 \n이 제대로 인식 안 되는 경우를 대비한 보정
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

# 데이터 불러오기
try:
    client = get_gspread_client()
    # 주의: 구글 시트 제목이 'inventory_data'와 일치해야 합니다.
    sheet = client.open("inventory_data").sheet1
    
    st.success("✅ 구글 시트 연결 성공!")
    
    # 데이터 읽기
    rows = sheet.get_all_records()
    df = pd.DataFrame(rows)

    st.title("🌐 온라인 창고 관리 시스템")

    # 입력창
    with st.expander("📦 신규 물품 등록"):
        with st.form("add_item"):
            col1, col2, col3 = st.columns(3)
            wh = col1.text_input("창고")
            item = col2.text_input("품목")
            qty = col3.number_input("수량", min_value=0)
            submit = st.form_submit_button("저장")
            
            if submit and wh and item:
                sheet.append_row([wh, item, qty])
                st.balloons() # 축하 효과
                st.rerun()

    # 리스트 출력
    st.subheader("📊 재고 현황")
    search = st.text_input("🔎 품목 검색")
    if search:
        df = df[df['품목'].str.contains(search)]
    st.dataframe(df, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"❌ 연결 중 오류가 발생했습니다: {e}")
    st.info("비밀번호(Secrets) 설정이나 key.json 파일이 깃허브에 있는지 확인하세요.")