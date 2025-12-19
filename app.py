import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import re
from datetime import datetime

# 구글 시트 URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"

@st.cache_resource
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = dict(st.secrets["gcp_service_account"])
    pk = creds_info["private_key"]
    if "-----BEGIN PRIVATE KEY-----" in pk:
        content = pk.replace("-----BEGIN PRIVATE KEY-----", "").replace("-----END PRIVATE KEY-----", "")
        clean_content = re.sub(r"\s+", "", content) 
        lines = [clean_content[i:i+64] for i in range(0, len(clean_content), 64)]
        pk = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END PRIVATE KEY-----\n"
    creds_info["private_key"] = pk
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(creds)

# 정보 수정 함수
def update_item_info(main_sheet, log_sheet, row_idx, old_name, col_name, new_value, df_columns):
    try:
        col_idx = list(df_columns).index(col_name) + 1
        main_sheet.update_cell(row_idx + 2, col_idx, new_value)
        if log_sheet:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_sheet.append_row([now, old_name, f"{col_name} 변경", str(new_value)])
        st.toast(f"✅ 수정 완료: {new_value}")
        st.rerun()
    except Exception as e:
        st.error(f"수정 오류: {e}")

st.set_page_config(page_title="온라인 창고 관리", layout="wide")
st.title("🌐 온라인 창고 관리 시스템")

try:
    client = get_gspread_client()
    spreadsheet = client.open_by_url(SHEET_URL)
    main_sheet = spreadsheet.sheet1
    try:
        log_sheet = spreadsheet.worksheet("로그")
    except:
        log_sheet = None

    data = main_sheet.get_all_records()
    
    if data:
        df = pd.DataFrame(data)
        name_col = next((c for c in df.columns if '품목' in str(c) or '이름' in str(c)), df.columns[0])
        spec_col = df.columns[1] if len(df.columns) > 1 else None
        qty_col = next((c for c in df.columns if '수량' in str(c)), df.columns[2] if len(df.columns) > 2 else None)
        
        if qty_col:
            df[qty_col] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0).astype(int)

        st.sidebar.title("📦 메뉴")
        menu = st.sidebar.radio("이동", ["재고 현황", "간편 입출고", "품목 관리 (등록/수정)", "활동 로그"])

        # --- 메뉴: 품목 관리 (등록/수정 통합) ---
        if menu == "품목 관리 (등록/수정)":
            st.subheader("🛠️ 품목 데이터 관리")
            tab1, tab2 = st.tabs(["✨ 신규 품목 등록", "📝 기존 품목 수정"])

            with tab1:
                st.write("새로운 물건을 리스트에 추가합니다.")
                with st.form("add_form", clear_on_submit=True):
                    in_name = st.text_input("품목명 (필수)")
                    in_spec = st.text_input("규격 (선택)")
                    in_qty = st.number_input("초기 수량", min_value=0, value=0)
                    if st.form_submit_button("시트에 추가하기"):
                        if in_name:
                            main_sheet.append_row([in_name, in_spec, int(in_qty)])
                            if log_sheet:
                                log_sheet.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), in_name, "신규등록", int(in_qty)])
                            st.success(f"'{in_name}' 등록 완료!")
                            st.rerun()
                        else: st.error("품목명을 입력해주세요.")

            with tab2:
                st.write("기존 품목의 이름이나 규격을 수정합니다.")
                mod_search = st.text_input("수정할 품목 검색", key="mod_search")
                mod_df = df[df.astype(str).apply(lambda x: x.str.contains(mod_search, case=False)).any(axis=1)] if mod_search else df
                
                for idx, row in mod_df.iterrows():
                    with st.expander(f"✏️ {row[name_col]} 수정하기"):
                        c1, c2 = st.columns(2)
                        with c1:
                            new_n = st.text_input("품목명 변경", value=row[name_col], key=f"n_{idx}")
                            if st.button("이름 저장", key=f"bn_{idx}"):
                                update_item_info(main_sheet, log_sheet, idx, row[name_col], name_col, new_n, df.columns)
                        with c2:
                            new_s = st.text_input("규격 변경", value=row.get(spec_col, ""), key=f"s_{idx}")
                            if st.button("규격 저장", key=f"bs_{idx}"):
                                update_item_info(main_sheet, log_sheet, idx, row[name_col], spec_col, new_s, df.columns)

        # --- 나머지 메뉴 (기존과 동일) ---
        elif menu == "재고 현황":
            st.subheader("📊 전체 재고")
            st.dataframe(df, use_container_width=True, hide_index=True)
        
        elif menu == "간편 입출고":
            # (기존 입출고 코드 유지...)
            st.subheader("🛠️ 수량 증감")
            edit_search = st.text_input("품목 검색")
            display_df = df[df.astype(str).apply(lambda x: x.str.contains(edit_search, case=False)).any(axis=1)] if edit_search else df
            for idx, row in display_df.iterrows():
                with st.expander(f"📦 {row[name_col]} (현재: {row[qty_col]}개)"):
                    # ... (입출고 버튼 로직 생략, 기존 코드 사용) ...
                    st.write("입출고 버튼을 배치하세요") # 실제 코드엔 기존 버튼 로직을 넣으시면 됩니다.

        elif menu == "활동 로그":
            if log_sheet:
                log_df = pd.DataFrame(log_sheet.get_all_values())
                st.table(log_df.iloc[::-1].head(20))

except Exception as e:
    st.error(f"❌ 에러: {e}")