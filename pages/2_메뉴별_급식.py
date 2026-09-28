from collections import defaultdict
import math
import re
import altair as alt
import pandas as pd
import requests
import streamlit as st

# 페이지 기본 설정
st.set_page_config(page_title="우리 학교 메뉴별 급식", page_icon="📊", layout="wide")


# ----------------------------------------------------
# 1. Secrets에서 API KEY 로드
# ----------------------------------------------------
def get_api_key():
    if "NEIS_API_KEY" in st.secrets:
        return st.secrets["NEIS_API_KEY"]
    return None


# ----------------------------------------------------
# 2. 전수 데이터 수집 함수 (페이지네이션 적용)
# ----------------------------------------------------
@st.cache_data(ttl=3600)
def fetch_all_meals(api_key: str):
    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    p_size = 1000
    p_index = 1
    all_rows = []

    while True:
        params = {
            "KEY": api_key,
            "Type": "json",
            "pIndex": p_index,
            "pSize": p_size,
            "ATPT_OFCDC_SC_CODE": "J10",  # 경기도교육청
            "SD_SCHUL_CODE": "7530480",  # 송탄고등학교
            "MMEAL_SC_CODE": "2",  # 중식
            "MLSV_FROM_YMD": "20250901",
            "MLSV_TO_YMD": "20260930",
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if "mealServiceDietInfo" in data:
                head = data["mealServiceDietInfo"][0]["head"]
                total_count = head[0]["list_total_count"]
                rows = data["mealServiceDietInfo"][1]["row"]
                all_rows.extend(rows)

                # 전체 건수를 모두 불러왔으면 종료
                if len(all_rows) >= total_count or len(rows) < p_size:
                    break
                p_index += 1
            else:
                break
        except Exception:
            break

    return all_rows


# ----------------------------------------------------
# 3. 메뉴 데이터 정제 및 집계
# ----------------------------------------------------
def process_menu_data(rows):
    # 날짜별 중복 메뉴 제거를 위한 구획
    # {메뉴명: set(급식일자들)}
    menu_dates = defaultdict(set)
    total_dates = set()

    for row in rows:
        ymd = row.get("MLSV_YMD")
        raw_ddish = row.get("DDISH_NM", "")

        if not ymd or not raw_ddish:
            continue

        total_dates.add(ymd)

        # <br/> 태그 기준 분할
        items = re.split(r"<br\s*/?>", raw_ddish)

        for item in items:
            item = item.strip()
            if not item:
                continue

            # 괄호 안의 알레르기 번호 제거 (예: 1.2.5. 또는 (1.2))
            clean_name = re.sub(r"\([0-9\.]+\)", "", item).strip()

            if clean_name:
                # 같은 날 같은 메뉴는 set에 의해 1회만 카운트됨
                menu_dates[clean_name].add(ymd)

    # 데이터프레임으로 변환
    data = []
    total_days_count = len(total_dates)

    for menu_name, dates in menu_dates.items():
        count = len(dates)
        ratio = (count / total_days_count * 100) if total_days_count > 0 else 0
        data.append(
            {
                "메뉴명": menu_name,
                "제공일수": count,
                "제공비율": round(ratio, 1),
            }
        )

    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values(by="제공일수", ascending=False).reset_index(drop=True)

    return df, total_days_count


# ----------------------------------------------------
# 4. 화면 UI 구성
# ----------------------------------------------------
st.title("📊 우리 학교 메뉴별 급식 통계")
st.caption("2025년 9월부터 2026년 9월까지 송탄고등학교 중식 메뉴 트렌드를 분석합니다.")
st.divider()

api_key = get_api_key()

if not api_key:
    st.error(
        "⚠️ Streamlit Secrets에 `NEIS_API_KEY`가 설정되어 있지 않습니다.\n"
        "`.streamlit/secrets.toml` 파일 또는 배포 환경 설정에 `NEIS_API_KEY = '발급받은키'`를 입력해 주세요."
    )
else:
    with st.spinner("급식 데이터를 불러오는 중입니다..."):
        raw_rows = fetch_all_meals(api_key)

    if not raw_rows:
        st.warning("해당 기간의 급식 정보 데이터를 불러오지 못했습니다.")
    else:
        df_menu, total_days = process_menu_data(raw_rows)

        if df_menu.empty:
            st.info("집계할 메뉴 데이터가 없습니다.")
        else:
            # 1위 메뉴 정보
            top_1_name = df_menu.iloc[0]["메뉴명"]
            top_1_count = df_menu.iloc[0]["제공일수"]
            top_1_ratio = df_menu.iloc[0]["제공비율"]

            # 상단 주요 요약 메트릭 카드
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric(label="📅 총 집계 일수", value=f"{total_days}일")
            with m2:
                st.metric(label="🥇 가장 자주 나온 메뉴 1위", value=top_1_name)
            with m3:
                st.metric(
                    label="📈 1위 메뉴 등장 비율 (출석률)",
                    value=f"{top_1_ratio}% ({top_1_count}회)",
                )

            st.divider()

            # 슬라이더로 상위 순위 개수 선택 (기본값: TOP 10)
            max_rank = min(len(df_menu), 30)
            top_n = st.slider(
                "보여줄 순위 범위 선택 (TOP N)",
                min_value=5,
                max_value=max_rank,
                value=10,
                step=1,
            )

            df_top = df_menu.head(top_n).copy()

            st.subheader(f"🏆 인기 메뉴 TOP {top_n}")

            # 가로 막대 그래프 생성 (Altair)
            # 1위가 맨 위에 위치하도록 sort=None 또는 -x 사용, 값이 클수록 진한 색상 적용
            chart = (
                alt.Chart(df_top)
                .mark_bar()
                .encode(
                    x=alt.X(
                        "제공일수:Q",
                        title="제공 일수 (일)",
                        axis=alt.Axis(tickMinStep=1),
                    ),
                    y=alt.Y("메뉴명:N", title="메뉴", sort="-x"),
                    color=alt.Color(
                        "제공일수:Q",
                        scale=alt.Scale(scheme="blues"),
                        legend=None,
                    ),
                    tooltip=[
                        alt.Tooltip("메뉴명", title="메뉴"),
                        alt.Tooltip("제공일수", title="제공 일수(일)"),
                        alt.Tooltip("제공비율", title="제공 비율(%)"),
                    ],
                )
                .properties(height=40 * top_n)
            )

            # 막대 우측 레이블 표시
            text = chart.mark_text(
                align="left", baseline="middle", dx=5
            ).encode(text=alt.Text("label:N"))

            # 표시용 레이블 컬럼 추가
            df_top["label"] = df_top.apply(
                lambda r: f"{r['제공일수']}일 ({r['제공비율']}%)", axis=1
            )

            chart_with_text = (
                alt.Chart(df_top)
                .mark_bar()
                .encode(
                    x=alt.X(
                        "제공일수:Q",
                        title="제공 일수 (일)",
                        axis=alt.Axis(tickMinStep=1),
                    ),
                    y=alt.Y("메뉴명:N", title="메뉴", sort="-x"),
                    color=alt.Color(
                        "제공일수:Q", scale=alt.Scale(scheme="blues"), legend=None
                    ),
                    tooltip=[
                        alt.Tooltip("메뉴명", title="메뉴"),
                        alt.Tooltip("제공일수", title="제공 일수(일)"),
                        alt.Tooltip("제공비율", title="제공 비율(%)"),
                    ],
                )
                + alt.Chart(df_top)
                .mark_text(align="left", baseline="middle", dx=5)
                .encode(
                    x="제공일수:Q", y=alt.Y("메뉴명:N", sort="-x"), text="label:N"
                )
            ).properties(height=35 * top_n)

            st.altair_chart(chart_with_text, use_container_width=True)

            # 상세 데이터표 보기
            with st.expander("📄 상세 데이터표 보기"):
                st.dataframe(
                    df_top.drop(columns=["label"]),
                    use_container_width=True,
                    hide_index=True,
                )
