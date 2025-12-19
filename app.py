import streamlit as st
import pandas as pd

# 1. 여기에 본인의 시트 주소를 따옴표 안에 정확히 넣으세요.
SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"

def get_csv_url(url):
    try:
        # 주소에서 핵심 아이디 부분만 추출하여 안전하게 변환합니다.
        base_url = url.split('/edit')[0]
        # gid 번호 추출 (없으면 0번 시트)
        gid = "0"
        if "gid=" in url:
            gid = url.split("gid=")[1]
        return f"{base_url}/export?format=csv&gid={gid}"
    except:
        return url

st.set_page_config(page_title="온라인 창고 관리", layout="wide")
st.title("🌐 온라인 창고 관리 시스템")

try:
    csv_url = get_csv_url(SHEET_URL)
    # 데이터를 읽어올 때 제목줄(Header)이 없어서 생기는 오류 방지
    df = pd.read_csv(csv_url)
    
    if df.empty:
        st.warning("시트에 데이터가 없습니다. 첫 줄에 '창고', '품목', '수량'이라고 적어주세요.")
    else:
        st.success("✅ 연결 성공!")
        st.subheader("📊 실시간 재고 현황")
        st.dataframe(df, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"⚠️ 연결 실패: {e}")
    st.info("시트 주소가 정확한지, '링크가 있는 모든 사용자 - 뷰어'로 설정했는지 다시 확인해주세요.")