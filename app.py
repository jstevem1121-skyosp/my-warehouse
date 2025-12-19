import streamlit as st
import pandas as pd

# 1. 구글 시트 주소 설정
# 주소창의 주소를 복사해서 아래 따옴표 안에 넣으세요.
# 주의: 주소 끝부분이 /edit#gid=0 형태여야 합니다.
SHEET_URL = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvXdBZjgmUUqptlbs74OgvE2upms/edit#gid=0"

# 구글 시트를 Pandas가 읽을 수 있는 CSV 다운로드 주소로 변환하는 함수
def get_csv_url(url):
    return url.replace('/edit#gid=', '/export?format=csv&gid=')

st.set_page_config(page_title="온라인 창고 관리", layout="wide")
st.title("🌐 온라인 창고 관리 시스템 (간편 연결)")

try:
    # 데이터 불러오기
    csv_url = get_csv_url(SHEET_URL)
    df = pd.read_csv(csv_url)
    
    st.success("✅ 구글 시트 데이터를 성공적으로 가져왔습니다!")
    
    # 검색 기능
    search = st.text_input("🔎 품목 검색")
    if search:
        display_df = df[df['품목'].str.contains(search, na=False)]
    else:
        display_df = df

    # 재고 현황 출력
    st.subheader("📊 실시간 재고 현황")
    st.dataframe(display_df, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"⚠️ 에러 발생: {e}")
    st.info("구글 시트의 공유 설정이 '링크가 있는 모든 사용자'로 되어 있는지 확인해주세요.")