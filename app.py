import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import base64

# 1. 시트 설정
SHEET_URL = "https://docs.google.com/spreadsheets/d/1n68yPElTJxguhZUSkBm4rPgAB_jIhh2Il7RY3z9hIbY/edit#gid=0"

# 2. 구글 인증 함수
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # 키 원본을 한 줄로 길게 정의 (공백/줄바꿈 없음)
    raw_key = "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDUvA+YkMcxC/jYcECdEzt3HZf5Jid+y8j+7I+B8yl8hUiB4Sqma55v+0QxkcY1RM/7ar/4GIdKpU72X9Ehtp/GyPRmi0JgUEYVZeU1l/Dv3rbZvWELCNeASHzP/p7hmlTxrj6a2BtkJ9fCMHtbOblWuXyf4soGJ+rWvKDPIR6PKINIn/kxeAshcXndG6bmmKMyto0st02yBCOxTbDQV00GaPY8mwW5NfnpBSVkv1xJbCoG9GEoqPrhXaGqV7oa56NBvIF6idc94SB1grfLWwUxr0yiITNo1wxRKx0vo1OoQX8LFuMPVCq+tXrsqYGaaTWvix4+aPfftgqfYjlWqwDbAgMBAAECggEAC4GNyQ9blrgyYhKANtQJeAHZFxgMiXvK3UQ85tHDbAFm0I+LLQEjyqQT0NKKSUCgNyr+QxRLN6sFQFIiZOkUbz4DP2Cc2x9nCv/oi84yBpH3NdkGXKsXwiUpiwkXMtXpbkD3EIz2aPkMCcFxipeZV1V6UMjawHEm7y0N+DtZrx3FK+O2W0MvC2HmgAP/NHX2IrXqCCPNTnSFBkYjKS5xkCl4VMlii79aMbTtD6cP+i/de8zDqx7EoW5n5uOqp/2tbaWmvnwCZOdSH5l2MyelddkZTsTob1SLL40+VrwmZEVpf15ooDQeMm2tBI6OfT+Nr/dQ8gqIJDVtMB1xkWTJQQKBgQD93Tk6u/y4mJ4hmhGcewWLnrk0yGy632nVU/ZxoSf/SNO4ecUQ9Yc1JJX3US85JPwbFVk23H7IpF481CPUU2Bouip7SnlhpvL7pVT/FhgCDpPymtehO5836gG5vcKQ7EWcsEsk1LswmcH9q8fQ4TQdqjZeHgbn3FnAENw+NTLIcQKBgQDWhkB/RGePTcbVvX2N+WGBW46mGQyA2FhJDylnMiZ8sFDiaCV+6fees9a841vHkmr6gVtDiP3e1R3rXQv3z7BvyAKQjcDCjz9LXGn37eTvk+A9S0GKKr1zI2MgCjq3DV4GgVITKjjMOGlxP3fJY5kf86L48FJOHjW4dlsawFSkCwKBgGJwl1GMNdpK6/6xpKSeG69hVAYAthDcs0hSr5yuVjkqv1aoeV8zJkPYNQLbC0nIaq4B4D9izxL0kcpapK4fyqGxlumKHnlcaJpmKQhlQ9gAWSRZIMZXvUzMQ/EHgVv7Ep9IyUq15wRYix3Xr7ryqOfb6gsi76CXFIJix1SkAlYxAoGBAI8etCr0LQ8bOZtht0Ef7mBKAApqTcAsFgJv/hReDfVEAEJ8bv+UAmK74njUSmgEFCEahPNcmnWzwY2ZoSm6DQ7QRLFr6NdxEF33y7MZN89Te42pfwS9Z+6LSi0CmYTofY/Es28bnY48Ifgav9N1lvNxJ3GX3LEjtyJAdEAHbfvAoGACjsgZAhmMosTY7fcnoX2h1ftW3WYY13niLPZWXCDMy3LX9UY8xXoUqnbWd7I3psvo31m2zg16lvxtwJyFqIp1kwHzlTOEpylmZ7Hza4AjzgmvApxE60aq/XTqyS9XCfaKNvtwuMvw91lvWrH4n+kdT58GTxF1Lc/l8JaYKfRs8="

    # Incorrect Padding 자동 보정 로직
    rem = len(raw_key) % 4
    if rem > 0:
        raw_key += "=" * (4 - rem)
    
    final_key = f"-----BEGIN PRIVATE KEY-----\n{raw_key}\n-----END PRIVATE KEY-----\n"

    creds_dict = {
        "type": "service_account",
        "project_id": "vernal-design-481723-j0",
        "private_key_id": "995db9a26656c83e05d67c754d8b7df8fb6740e7",
        "private_key": final_key,
        "client_email": "skyosp@vernal-design-481723-j0.iam.gserviceaccount.com",
        "client_id": "112636889347820130865",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/skyosp%40vernal-design-481723-j0.iam.gserviceaccount.com"
    }
    return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope))

# UI 설정
st.set_page_config(page_title="온라인 창고 관리", layout="wide")
st.title("🌐 온라인 창고 관리 시스템")

try:
    client = get_gspread_client()
    sheet = client.open_by_url(SHEET_URL).sheet1
    
    with st.expander("➕ 새 물품 등록"):
        with st.form("add_form"):
            col1, col2, col3 = st.columns(3)
            wh = col1.text_input("창고 위치")
            item = col2.text_input("품목명")
            qty = col3.number_input("수량", min_value=0, step=1)
            if st.form_submit_button("저장하기"):
                if wh and item:
                    sheet.append_row([wh, item, qty])
                    st.success("저장되었습니다!")
                    st.rerun()
                else:
                    st.warning("창고 위치와 품목명을 입력해주세요.")

    data = sheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        st.subheader("📊 실시간 재고 현황")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("데이터가 없습니다. 물품을 등록해보세요!")

except Exception as e:
    st.error(f"연결 에러: {e}")