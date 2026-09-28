from datetime import datetime
import re
import requests
import pytz
import streamlit as st

# 페이지 기본 설정
st.set_page_config(page_title="송탄고등학교 달력별 급식", page_icon="📅", layout="wide")


# ----------------------------------------------------
# 1. 한국 시간(KST) 기준 오늘 날짜 구하기
# ----------------------------------------------------
def get_kst_today():
    kst = pytz.timezone("Asia/Seoul")
    return datetime.now(kst).date()


# ----------------------------------------------------
# 2. 송탄고등학교 급식 정보 API 호출 함수
# ----------------------------------------------------
def fetch_songtan_meal(date_str: str):
    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    params = {
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": "J10",  # 경기도교육청
        "SD_SCHUL_CODE": "7530480",  # 송탄고등학교
        "MMEAL_SC_CODE": "2",  # 중식
        "MLSV_FROM_YMD": date_str,
        "MLSV_TO_YMD": date_str,
    }

    try:
        response = requests.get(url, params=params, timeout=5)
        data = response.json()

        if "mealServiceDietInfo" in data:
            rows = data["mealServiceDietInfo"][1]["row"]
            if rows:
                return rows[0]
        return None
    except Exception:
        return None


# ----------------------------------------------------
# 3. 메뉴 데이터 정제 및 알레르기 번호 제거 함수
# ----------------------------------------------------
def parse_menu_items(raw_ddish_nm: str, show_allergy: bool):
    """<br/> 태그로 구분된 메뉴 문자열을 리스트로 분할하고,

    show_allergy가 False인 경우 괄호 속 알레르기 번호를 제거합니다.
    """
    if not raw_ddish_nm:
        return []

    # <br/> 태그 기준으로 split
    raw_list = re.split(r"<br\s*/?>", raw_ddish_nm)
    cleaned_list = []

    for item in raw_list:
        item = item.strip()
        if not item:
            continue

        # 알레르기 스위치가 꺼져있으면 괄호 안의 숫자/점 제거
        if not show_allergy:
            item = re.sub(r"\([0-9\.]+\)", "", item).strip()

        cleaned_list.append(item)

    return cleaned_list


# ----------------------------------------------------
# 4. 화면 UI 구성
# ----------------------------------------------------
st.title("📅 우리 학교(송탄고등학교) 달력별 급식")
st.caption("송탄고등학교의 날짜별 중식 메뉴와 칼로리 정보를 확인하세요.")
st.divider()

# 컨트롤 영역 (날짜 선택 & 알레르기 스위치 나란히 배치)
col_date, col_toggle = st.columns([1, 1], vertical_alignment="bottom")

with col_date:
    today_kst = get_kst_today()
    selected_date = st.date_input("📅 날짜 선택", value=today_kst)

with col_toggle:
    show_allergy = st.toggle("알레르기 정보 보기", value=True)

# API 호출용 YYYYMMDD 변환
date_str = selected_date.strftime("%Y%m%d")

# 급식 정보 가져오기
meal_data = fetch_songtan_meal(date_str)

st.divider()

# 급식 데이터 존재 여부에 따른 화면 처리
if meal_data:
    raw_menu = meal_data.get("DDISH_NM", "")
    cal_info = meal_data.get("CAL_INFO", "정보 없음")

    # 메뉴 가공
    menu_items = parse_menu_items(raw_menu, show_allergy)

    # 요약 메트릭 카드 (메뉴 가짓수 & 칼로리)
    metric_col1, metric_col2 = st.columns(2)
    with metric_col1:
        st.metric(label="🍱 반찬 가짓수", value=f"{len(menu_items)}개")
    with metric_col2:
        st.metric(label="🔥 칼로리", value=cal_info)

    st.subheader(f"🍴 {selected_date.strftime('%Y년 %m월 %d일')} 메뉴 목록")

    # 메뉴 카드를 여러 열로 나란히 나열 (최대 4개씩 한 줄)
    if menu_items:
        num_cols = min(len(menu_items), 4)
        cols = st.columns(num_cols)

        for idx, item in enumerate(menu_items):
            with cols[idx % num_cols]:
                st.container(border=True).markdown(f"### 🍽️\n**{item}**")
    else:
        st.info("등록된 메뉴 항목이 없습니다.")
else:
    # 주말, 방학 등 급식이 없는 날 안내
    st.info("💡 급식이 없는 날입니다.")
