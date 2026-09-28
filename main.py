from datetime import datetime
import re
import requests
import pytz
import streamlit as st

# 페이지 설정
st.set_page_config(page_title="학교 급식 찾아보기", page_icon="🍱")
st.title("🍱 학교 급식 찾아보기")


# ----------------------------------------------------
# 1. 한국 시간(KST) 기준 오늘 날짜 구하기
# ----------------------------------------------------
def get_kst_today():
    kst = pytz.timezone("Asia/Seoul")
    return datetime.now(kst).date()


# ----------------------------------------------------
# 2. 줄임말 보정 함수
# ----------------------------------------------------
def expand_school_name(query: str) -> str:
    """줄여 적은 학교 이름을 정식 명칭 형태로 보정"""
    expanded = query
    # '여고' -> '여자고등학교'
    if expanded.endswith("여고"):
        expanded = expanded[:-2] + "여자고등학교"
    # '고' -> '고등학교' ('여자고등학교' 등으로 변환되지 않은 경우)
    elif expanded.endswith("고"):
        expanded = expanded[:-1] + "고등학교"
    return expanded


# ----------------------------------------------------
# 3. 학교 검색 API 호출 함수
# ----------------------------------------------------
def fetch_school_info(school_name: str):
    url = "https://open.neis.go.kr/hub/schoolInfo"
    params = {"Type": "json", "SCHUL_NM": school_name}

    try:
        response = requests.get(url, params=params, timeout=5)
        data = response.json()

        # 결과 데이터 존재 확인
        if "schoolInfo" in data:
            rows = data["schoolInfo"][1]["row"]
            return rows
        return []
    except Exception:
        return []


def search_school(query: str):
    query = query.strip()
    if not query:
        return []

    # 1차 검색
    results = fetch_school_info(query)

    # 검색 결과가 없고 보정 가능한 키워드인 경우 2차 검색
    if not results:
        expanded_query = expand_school_name(query)
        if expanded_query != query:
            results = fetch_school_info(expanded_query)

    return results


# ----------------------------------------------------
# 4. 급식 정보 API 호출 함수
# ----------------------------------------------------
def fetch_meal_info(atpt_code: str, school_code: str, date_str: str):
    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    params = {
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": atpt_code,
        "SD_SCHUL_CODE": school_code,
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
# 5. 화면 UI 구성
# ----------------------------------------------------
# 검색어 입력
school_query = st.text_input("학교 이름을 입력하세요", placeholder="예: 수도여고, 서울고")

if school_query:
    schools = search_school(school_query)

    if not schools:
        st.warning("검색 결과가 없습니다. 학교 이름을 올바르게 입력했는지 확인해 주세요.")
    else:
        # 학교 선택 드롭다운 목록 생성
        school_options = {
            f"{s['SCHUL_NM']} ({s.get('LCTN_SC_NM', '지역 정보 없음')})": s
            for s in schools
        }

        selected_label = st.selectbox("학교를 선택하세요", list(school_options.keys()))
        selected_school = school_options[selected_label]

        st.divider()

        # 날짜 선택 (기본값: 한국 시간 기준 오늘)
        today_kst = get_kst_today()
        selected_date = st.date_input("날짜 선택", value=today_kst)

        # YYYYMMDD 형식으로 변환
        date_str = selected_date.strftime("%Y%m%d")

        # 급식 정보 조회
        meal_data = fetch_meal_info(
            selected_school["ATPT_OFCDC_SC_CODE"],
            selected_school["SD_SCHUL_CODE"],
            date_str,
        )

        st.subheader(
            f"📋 {selected_school['SCHUL_NM']} - {selected_date.strftime('%Y년 %m월 %d일')} 중식 메뉴"
        )

        if meal_data:
            # HTML 태그 <br/> 및 여러 줄 바꿈 정제
            raw_menu = meal_data.get("DDISH_NM", "")
            formatted_menu = re.sub(r"<br\s*/?>", "\n", raw_menu)

            # 메뉴 출력
            st.markdown("#### 🍱 급식 식단")
            st.text(formatted_menu)

            # 칼로리 정보 출력
            cal_info = meal_data.get("CAL_INFO", "정보 없음")
            st.info(f"🔥 칼로리: **{cal_info}**")
        else:
            st.info("해당 날짜에는 등록된 급식 정보가 없습니다.")
