from datetime import datetime, timedelta
import requests
import pandas as pd
import pytz
import streamlit as st

# ==========================================
# 1. 페이지 기본 설정 및 스타일 정의
# ==========================================
st.set_page_config(
    page_title="어제 박스오피스 순위",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제 일별 박스오피스 순위")
st.caption("KOBIS(영화관입장권통합전산망) 공식 Open API를 이용한 실시간 조회 서비스입니다.")

# ==========================================
# 2. 날짜 계산 (한국 표준시 KST 기준 '어제')
# ==========================================
# 배포 서버(Streamlit Cloud)의 시각이 UTC 기준일 수 있으므로
# 한국 시간(Asia/Seoul)으로 정확히 변환하여 '어제' 날짜를 구합니다.
kst = pytz.timezone("Asia/Seoul")
now_kst = datetime.now(kst)
yesterday_kst = now_kst - timedelta(days=1)

# API 요청 형식에 맞춰 YYYYMMDD (8자리 숫자) 문자열로 변환
target_date_str = yesterday_kst.strftime("%Y%m%d")
# 화면에 표시할 포맷 (예: 2026년 10월 25일)
display_date_str = yesterday_kst.strftime("%Y년 %m월 %d일")

st.markdown(f"### 📅 **{display_date_str}** 기준")

# ==========================================
# 3. Streamlit Secrets에서 API 키 불러오기
# ==========================================
# 비밀 금고(.streamlit/secrets.toml 또는 Cloud Secrets)에서 KOBIS_KEY를 가져옵니다.
if "KOBIS_KEY" not in st.secrets:
    st.error("🚨 API 인증키(KOBIS_KEY)가 설정되지 않았습니다.")
    st.info(
        "💡 **확인 방법:**\n"
        "1. **로컬 실행 시**: `.streamlit/secrets.toml` 파일에 `KOBIS_KEY = '발급받은키'`를 작성해 주세요.\n"
        "2. **Streamlit Cloud 앱 배포 시**: App settings -> Secrets 메뉴에서 `KOBIS_KEY = '발급받은키'`를 등록해 주세요."
    )
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# ==========================================
# 4. KOBIS API 데이터 요청 함수 (캐싱 적용)
# ==========================================
# st.cache_data를 사용하여 동일한 날짜 요청에 대해 API 호출을 절약합니다.
@st.cache_data(ttl=3600)  # 1시간 동안 결과 캐싱
def fetch_box_office_data(key: str, target_dt: str):
    url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
    params = {
        "key": key,
        "targetDt": target_dt
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        # HTTP 상태 코드 확인 (200이 아닌 경우 예외 발생)
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.RequestException as e:
        return None, f"네트워크 통신 오류가 발생했습니다: {e}"

# API 데이터 불러오기 실행
data, error_msg = fetch_box_office_data(api_key, target_date_str)

# ==========================================
# 5. 예외 및 오류 처리
# ==========================================
# 1) HTTP 통신 오류 발생 시
if error_msg:
    st.error(f"❌ 데이터 요청 실패")
    st.write(error_msg)
    st.info("💡 인터넷 연결 상태를 확인하거나 잠시 후 다시 시도해 주세요.")
    st.stop()

# 2) KOBIS 자체 에러 응답(faultInfo) 확인
# KOBIS API는 인증키가 틀려도 HTTP status code 200을 반환하며 faultInfo를 보냅니다.
if "faultInfo" in data:
    fault = data["faultInfo"]
    st.error("🚨 KOBIS API 응답 오류가 발생했습니다.")
    st.warning(f"**오류 메시지**: {fault.get('message', '알 수 없는 오류')}")
    st.info(
        "💡 **확인해 보세요:**\n"
        "- Streamlit Secrets에 입력한 `KOBIS_KEY` 값이 정확한지 확인해 주세요.\n"
        "- KOBIS 오픈API 홈페이지에서 키 상태가 '승인/유효' 상태인지 확인해 주세요."
    )
    st.stop()

# 3) 응답 구조 및 영화 목록 확인
box_office_result = data.get("boxOfficeResult", {})
daily_list = box_office_result.get("dailyBoxOfficeList", [])

if not daily_list:
    st.warning("⚠️ 해당 날짜의 박스오피스 데이터가 존재하지 않거나 집계 중입니다.")
    st.info("💡 KOBIS 전산망의 데이터 집계 시점에 따라 잠시 후 조회할 수 있습니다.")
    st.stop()

# ==========================================
# 6. 데이터 전처리 (문자열 -> 숫자 변환)
# ==========================================
df = pd.DataFrame(daily_list)

# KOBIS 응답은 모든 숫자가 문자열로 넘어오므로 숫자로 변환합니다.
numeric_columns = ["rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt", "rankInten"]
for col in numeric_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# ==========================================
# 7. 1위 영화 주요 지표 카드 (Metric)
# ==========================================
top_1 = df.iloc[0]

st.subheader(f"🥇 1위: {top_1['movieNm']}")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="어제 관객수",
        value=f"{top_1['audiCnt']:,} 명",
        delta=f"전날 대비 순위 {top_1['rankInten']:+} 위" if top_1['rankInten'] != 0 else "순위 변동 없음"
    )

with col2:
    st.metric(
        label="누적 관객수",
        value=f"{top_1['audiAcc']:,} 명"
    )

with col3:
    st.metric(
        label="상영 스크린수",
        value=f"{top_1['scrnCnt']:,} 개"
    )

st.divider()

# ==========================================
# 8. 관객수 상위 5편 막대그래프
# ==========================================
st.subheader("📊 관객수 TOP 5 영화")

# 상위 5개 데이터 추출
top_5_df = df.head(5).copy()

# 시각화를 위해 영화명을 인덱스로 설정
chart_df = top_5_df.set_index("movieNm")[["audiCnt"]]
chart_df.columns = ["관객수"]

# Streamlit 기본 막대그래프 출력
st.bar_chart(chart_df)

st.divider()

# ==========================================
# 9. 전체 박스오피스 순위 표
# ==========================================
st.subheader("📋 전체 순위 목록")

# 화면에 보여줄 컬럼선택 및 이름 변경
display_df = df[[
    "rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"
]].copy()

display_df.columns = [
    "순위", "영화명", "개봉일", "어제 관객수", "누적 관객수", "스크린수"
]

# 숫자에 천 단위 쉼표(,) 포맷팅 적용
st.dataframe(
    display_df.style.format({
        "어제 관객수": "{:,}명",
        "누적 관객수": "{:,}명",
        "스크린수": "{:,}개"
    }),
    use_container_width=True,
    hide_index=True
)
