import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# --- 구글 시트 연결 설정 ---
def get_gspread_client():
    # 'key.json' 파일로 인증 진행
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    import json
creds_info = st.secrets["gcp_service_account"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
    return gspread.authorize(creds)

try:
    client = get_gspread_client()
    # 주의: 구글 시트 이름이 'inventory_data'여야 합니다. (본인의 시트 이름으로 수정 가능)
    sheet = client.open("inventory_data").sheet1
except Exception as e:
    st.error(f"연결 에러: {e}")
    st.info("구글 시트 이름을 확인하거나, 서비스 계정 이메일에 공유 권한을 줬는지 확인하세요.")

# --- 메인 화면 UI ---
st.set_page_config(page_title="스마트 창고 관리 (온라인)", layout="wide")
st.title("🌐 온라인 창고 관리 시스템")

# 1. 데이터 불러오기
def load_data():
    rows = sheet.get_all_records()
    return pd.DataFrame(rows)

df = load_data()

# 2. 상단 입력 폼
with st.expander("➕ 새 물품 등록"):
    with st.form("add_form"):
        col1, col2, col3 = st.columns(3)
        wh = col1.text_input("창고 위치")
        item = col2.text_input("품목명")
        qty = col3.number_input("수량", min_value=0, step=1)
        
        if st.form_submit_button("저장하기"):
            if wh and item:
                sheet.append_row([wh, item, qty])
                st.success("구글 시트에 저장되었습니다!")
                st.rerun() # 화면 새로고침

# 3. 검색 및 리스트업
st.subheader("📊 실시간 재고 현황")
search = st.text_input("🔎 품목명 검색")

if search:
    display_df = df[df['품목'].str.contains(search)]
else:
    display_df = df

st.dataframe(display_df, use_container_width=True, hide_index=True)

# ... (기존 코드 뒷부분에 추가)

st.divider()
st.subheader("🛠️ 재고 수정 및 삭제")

# 1. 수정/삭제할 행 선택
if not df.empty:
    selected_item = st.selectbox("수정 또는 삭제할 품목을 선택하세요", df['품목'].unique())
    
    col_edit1, col_edit2, col_edit3 = st.columns([2, 1, 1])
    
    with col_edit1:
        new_qty = st.number_input("새로운 수량 입력", min_value=0, value=int(df[df['품목'] == selected_item]['수량'].values[0]))
    
    with col_edit2:
        if st.button("수량 업데이트", use_container_width=True):
            # 구글 시트에서 해당 품목 찾아서 수량 변경
            cell = sheet.find(selected_item)
            sheet.update_cell(cell.row, 3, new_qty) # 3번째 열(수량) 수정
            st.success("수정 완료!")
            st.rerun()

    with col_edit3:
        if st.button("품목 삭제", use_container_width=True, type="primary"):
            # 구글 시트에서 해당 행 삭제
            cell = sheet.find(selected_item)
            sheet.delete_rows(cell.row)
            st.warning("삭제 완료!")
            st.rerun()
else:
    st.info("데이터가 없습니다. 물품을 먼저 등록해주세요.")