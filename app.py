import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# 페이지 설정
st.set_page_config(page_title="온라인 창고 관리", layout="wide")

# --- 구글 시트 연결 함수 ---
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # 전달해주신 키 정보를 직접 입력
    creds_dict = {
      "type": "service_account",
      "project_id": "vernal-design-481723-j0",
      "private_key_id": "995db9a26656c83e05d67c754d8b7df8fb6740e7",
      "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDUvA+YkMcxC/jY\ncECdEzt3HZf5Jid+y8j+7I+B8yl8hUiB4Sqma55v+0QxkcY1RM/7ar/4GIdKpU72\nX9Ehtp/GyPRmi0JgUEYVZeU1l/Dv3rbZvWELCNeASHzP/p7hmlTxrj6a2BtkJ9fC\nMHtbOblWuXyf4soGJ+rWvKDPIR6PKINIn/kxeAshcXndG6bmmKMyto0st02yBCOx\nTbDQV00GaPY8mwW5NfnpBSVkv1xJbCoG9GEoqPrhXaGqV7oa56NBvIF6idc94SB1\ngrfLWwUxr0yiITNo1wxRKx0vo1OoQX8LFuMPVCq+tXrsqYGaaTWvix4+aPfftgqf\nYjlWqwDbAgMBAAECggEAC4GNyQ9blrgyYhKANtQJeAHZFxgMiXvK3UQ85tHDbAFm\n0I+LLQEjyqQT0NKKSUCgNyr+QxRLN6sFQFIiZOkUbz4DP2Cc2x9nCv/oi84yBpH3\nNdkGXKsXwiUpiwkXMtXpbkD3EIz2aPkMCcFxipeZV1V6UMjawHEm7y0N+DtZrx3F\nK+O2W0MvC2HmgAP/NHX2IrXqCCPNTnSFBkYjKS5xkCl4VMlii79aMbTtD6cP+i/d\ne8zDqx7EoW5n5uOqp/2tbaWmvnwCZOdSH5l2MyelddkZTsTob1SLL40+VrwmZEVp\nf15ooDQeMm2tBI6OfT+Nr/dQ8gqIJDVtMB1xkWTJQQKBgQD93Tk6u/y4mJ4hmhGc\newWLnrk0yGy632nVU/ZxoSf/SNO4ecUQ9Yc1JJX3US85JPwbFVk23H7IpF481CPU\nU2Bouip7SnlhpvL7pVT/FhgCDpPymtehO5836gG5vcKQ7EWcsEsk1LswmcH9q8fQ\n4TQdqjZeHgbn3FnAENw+NTLIcQKBgQDWhkB/RGePTcbVvX2N+WGBW46mGQyA2FhJ\nDylnMiZ8sFDiaCV+6fees9a841vHkmr6gVtDiP3e1R3rXQv3z7BvyAKQjcDCjz9L\nXGn37eTvk+A9S0GKKr1zI2MgCjq3DV4GgVITKjjMOGlxP3fJY5kf86L48FJOHjW4\ndlsawFSkCwKBgGJwl1GMNdpK6/6xpKSeG69hVAYAthDcs0hSr5yuVjkqv1aoeV8z\nJkPYNQLbC0nIaq4B4D9izxL0kcpapK4fyqGxlumKHnlcaJpmKQhlQ9gAWSRZIMZX\nvUzMQ/EHgVv7Ep9IyUq15wRYix3Xr7ryqOfb6gsi76CXFIJix1SkAlYxAoGBAI8e\ntCr0LQ8bOZtht0Ef7mBKAApqTcAsFgJv/hReDfVEAEJ8bv+UAmK74njUSmgEFCEa\nahPNcmnWzwY2ZoSm6DQ7QRLFr6NdxEF33y7MZN89Te42pfwS9Z+6LSi0CmYTofY/\nEs28bnY48Ifgav9N1lvNxJ3GX3LEjtyJAdEAHbfvAoGACjsgZAhmMosTY7fcnoX2\nh1ftW3WYY13niLPZWXCDMy3LX9UY8xXoUqnbWd7I3psvo31m2zg16lvxtwJyFqIp\n1kwHzlTOEpylmZ7Hza4AjzgmvApxE60aq/XTqyS9XCfaKNvtwuMvw91lvpWrH4n+\nkdT58GTxF1Lc/l8JaYKfRs8=\n-----END PRIVATE KEY-----\n",
      "client_email": "skyosp@vernal-design-481723-j0.iam.gserviceaccount.com",
      "client_id": "112636889347820130865",
      "auth_uri": "https://accounts.google.com/o/oauth2/auth",
      "token_uri": "https://oauth2.googleapis.com/token",
      "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
      "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/skyosp%40vernal-design-481723-j0.iam.gserviceaccount.com",
      "universe_domain": "googleapis.com"
    }
    
    # 딕셔너리를 사용하여 인증 진행
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

# 실행 및 UI 구성
try:
    client = get_gspread_client()
    # 주의: 구글 시트 이름이 'inventory_data'여야 합니다. 
    # 만약 시트 이름을 바꾸셨다면 아래 괄호 안의 이름을 똑같이 수정하세요.
    sheet = client.open("inventory_data").sheet1
    
    st.title("🌐 온라인 창고 관리 시스템")
    st.success("✅ 구글 시트에 연결되었습니다!")

    # 데이터 불러오기
    rows = sheet.get_all_records()
    df = pd.DataFrame(rows)

    # 신규 물품 등록 폼
    with st.form("add_item_form"):
        col1, col2, col3 = st.columns(3)
        new_wh = col1.text_input("창고 위치")
        new_item = col2.text_input("품목명")
        new_qty = col3.number_input("수량", min_value=0, step=1)
        
        if st.form_submit_button("등록하기"):
            if new_wh and new_item:
                sheet.append_row([new_wh, new_item, new_qty])
                st.success(f"{new_item} 등록 완료!")
                st.rerun()

    # 재고 현황 테이블
    st.subheader("📊 실시간 재고 현황")
    st.dataframe(df, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"⚠️ 에러 발생: {e}")
    st.info("구글 시트 제목이 'inventory_data' 인지, 그리고 서비스 계정 이메일을 공유 편집자로 추가했는지 확인하세요.")
