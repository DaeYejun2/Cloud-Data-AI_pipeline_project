import os
import re
from collections import Counter

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
import plotly.express as px
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.linear_model import LinearRegression

# 1. 페이지 기본 설정 (가장 위에 와야 함)
st.set_page_config(page_title="금융상품 x 분쟁조정사례 EDA", layout="wide", initial_sidebar_state="collapsed")

# 2. 전역 CSS 주입 (Pretendard 폰트 및 카드형 UI 디자인)
st.markdown("""
<style>
    /* Pretendard 폰트 적용 */
    @import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css");
    html, body, [class*="css"], p, h1, h2, h3, h4, h5, h6 {
        font-family: 'Pretendard', sans-serif !important;
    }

    /* 숫자 지표(Metric) 카드 디자인 */
    [data-testid="stMetric"] {
        background-color: #1E2127;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        border: 1px solid #2A2D35;
        transition: all 0.3s ease;
    }

    /* 마우스 오버 시 카드 강조 효과 */
    [data-testid="stMetric"]:hover {
        transform: translateY(-5px);
        border-color: #00E5FF;
        box-shadow: 0 8px 25px rgba(0, 229, 255, 0.15);
    }

    /* 메인 타이틀 그라데이션 효과 */
    .main-title {
        background: linear-gradient(90deg, #00E5FF 0%, #007BFF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.5rem;
        margin-bottom: 0;
    }

    /* 탭(Tab) 글씨 크기 키우기 */
    [data-testid="stTabs"] button {
        font-size: 1.1rem;
        font-weight: 600;
        padding-bottom: 10px;
    }

    /* 인사이트 콜아웃 박스 */
    .insight-box {
        background-color: #16232E;
        border: 1px solid #1E3A4C;
        border-left: 4px solid #00E5FF;
        border-radius: 10px;
        padding: 16px 20px;
        margin: 6px 0 14px 0;
        line-height: 1.7;
        font-size: 0.95rem;
    }
    .insight-box b { color: #00E5FF; }
</style>
""", unsafe_allow_html=True)

# DB 접속 설정
DB_CONFIG = {
    "host": os.environ.get("PGHOST", "localhost"),
    "port": os.environ.get("PGPORT", "5432"),
    "dbname": os.environ.get("PGDATABASE", "finlife_pipeline"),
    "user": os.environ.get("PGUSER", "postgres"),
    "password": os.environ.get("PGPASSWORD", ""),
}

@st.cache_resource
def get_engine():
    url = (
        f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
    )
    return create_engine(url)

@st.cache_data(ttl=300)
def run_query(sql: str) -> pd.DataFrame:
    engine = get_engine()
    try:
        with engine.connect() as conn:
            return pd.read_sql(text(sql), conn)
    except Exception as e:
        st.error(f"DB 조회 실패: {e}")
        return pd.DataFrame()


OPTION_TABLES = [
    "product_deposit_option", "product_saving_option", "product_annuity_option",
    "product_mortgage_option", "product_rent_house_loan_option", "product_credit_loan_option",
]

# 카테고리 코드 -> 한글 표기 (차트 축/범례용)
CATEGORY_LABELS = {
    "deposit": "정기예금",
    "saving": "적금",
    "annuity": "연금저축",
    "mortgage": "주택담보대출",
    "rent_house_loan": "전세자금대출",
    "credit_loan": "개인신용대출",
}

# 차트 색상 팔레트: 카드 UI의 시안(#00E5FF) 계열로 통일
CHART_COLORS = ["#00E5FF", "#007BFF", "#7C4DFF", "#00BFA5", "#FFD166", "#FF6E6E"]

# 키워드 빈도 분석용 불용어 (조사 결합/범용 어휘 위주, 형태소 분석 미적용 한계 보완)
STOPWORDS = {
    "신청인은", "신청인이", "신청인의", "신청인에게", "피신청인은", "피신청인이", "피신청인의",
    "피신청인에게", "신청인", "피신청인", "있습니다", "하였습니다", "합니다", "있으며",
    "경우에는", "경우", "대하여", "대한", "관련", "따라", "따른", "위해", "통해", "또한",
    "그러나", "하지만", "이러한", "해당", "당시", "이후", "이전", "동안", "관하여",
    "있다는", "없다는", "것으로", "것이", "것을", "것은", "수단", "내용", "사실",
}


def insight_box(html_lines):
    """DB 값 기반으로 동적 생성되는 인사이트 콜아웃"""
    st.markdown('<div class="insight-box">' + "<br>".join(html_lines) + "</div>",
                unsafe_allow_html=True)


def style_fig(fig, height=380):
    """모든 차트 공통 스타일: 투명 배경 + 여백 정리"""
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=30, b=0),
        height=height,
        legend_title_text="",
    )
    return fig


# ============================================================
# 데이터 로더 (탭 간 공유, 5분 캐시)
# ============================================================

@st.cache_data(ttl=300)
def load_product_summary() -> pd.DataFrame:
    """통합 view에서 상품 단위 데이터 로드 (약 1천 행 규모, 전체 로드 후 pandas 필터)"""
    df = run_query("""
        SELECT category, kor_co_nm, fin_prdt_nm, area_grp_nm, is_active
        FROM v_product_summary
    """)
    if not df.empty:
        df["카테고리"] = df["category"].map(CATEGORY_LABELS).fillna(df["category"])
    return df


@st.cache_data(ttl=300)
def load_option_rates() -> pd.DataFrame:
    """카테고리별로 컬럼 구조가 다른 option 테이블들을 (카테고리, 기간, 금리) 공통 구조로 통합.
    - 예금/적금: 기본금리(intr_rate), 우대금리(intr_rate2), 가입기간(save_trm)
    - 주담대/전세대출: 평균금리(lend_rate_avg), 최고금리(lend_rate_max)
    - 신용대출: 등급 평균금리(crdt_grad_avg)
    - 연금저축: 옵션 테이블에 금리 개념 없음 -> 제외
    """
    return run_query("""
        SELECT 'deposit' AS category, save_trm, intr_rate AS rate, intr_rate2 AS rate_max, area_grp_nm
        FROM product_deposit_option WHERE intr_rate IS NOT NULL
        UNION ALL
        SELECT 'saving', save_trm, intr_rate, intr_rate2, area_grp_nm
        FROM product_saving_option WHERE intr_rate IS NOT NULL
        UNION ALL
        SELECT 'mortgage', NULL::INTEGER, lend_rate_avg, lend_rate_max, area_grp_nm
        FROM product_mortgage_option WHERE lend_rate_avg IS NOT NULL
        UNION ALL
        SELECT 'rent_house_loan', NULL::INTEGER, lend_rate_avg, lend_rate_max, area_grp_nm
        FROM product_rent_house_loan_option WHERE lend_rate_avg IS NOT NULL
        UNION ALL
        SELECT 'credit_loan', NULL::INTEGER, crdt_grad_avg, NULL::NUMERIC, area_grp_nm
        FROM product_credit_loan_option WHERE crdt_grad_avg IS NOT NULL
    """)


@st.cache_data(ttl=300)
def load_disputes() -> pd.DataFrame:
    """분쟁조정사례 전체 로드 (201건 규모)"""
    return run_query("""
        SELECT case_no, area, dispute_type, title, reg_date, view_count,
               reg_year, body_length, parse_status,
               complaint_text, issue_text, result_text, consumer_note_text, detail_url
        FROM dispute_cases
        ORDER BY reg_date DESC, case_no DESC
    """)


# ============================================================
# 홈 대시보드
# ============================================================

def render_home():
    st.markdown("###### 📊 금융감독원 데이터 기반 EDA 서비스")
    st.markdown('<h1 class="main-title">금융상품 × 분쟁조정사례 교차분석</h1>', unsafe_allow_html=True)
    st.caption("상품 스펙과 실제 분쟁조정 판단 근거를 한 화면에서 대조하여 다각적 인사이트를 제공합니다.")
    st.write("")

    df_p = run_query("SELECT COUNT(*) AS cnt FROM v_product_summary")
    product_count = int(df_p["cnt"].iloc[0]) if not df_p.empty else 0

    df_o = run_query(f"SELECT COUNT(*) AS cnt FROM ({' UNION ALL '.join(f'SELECT 1 FROM {t}' for t in OPTION_TABLES)}) x")
    option_count = int(df_o["cnt"].iloc[0]) if not df_o.empty else 0

    df_d = run_query("SELECT COUNT(*) AS cnt FROM dispute_cases")
    dispute_count = int(df_d["cnt"].iloc[0]) if not df_d.empty else 0

    # 카드형 KPI 지표
    col1, col2, col3 = st.columns(3)
    col1.metric("📦 수집된 금융상품 수", f"{product_count:,} 개", delta="표준 스펙")
    col2.metric("⚙️ 세부 옵션(금리/조건) 수", f"{option_count:,} 개", delta="DB 적재 완료")
    col3.metric("⚖️ 분쟁조정사례 수", f"{dispute_count:,} 건", delta="비정형 텍스트", delta_color="off")

    st.divider()

    # 데이터 파이프라인 시각적 표현
    st.markdown("#### 🔄 Data Pipeline")
    step_cols = st.columns(4)
    steps = [
        ("01 수집", "API & 크롤링", "finlife.fss.or.kr"),
        ("02 저장", "PostgreSQL + Object Storage", "Raw 스냅샷/정형 적재"),
        ("03 가공", "데이터 정제/매핑", "Pandas & SQL (cron 배치)"),
        ("04 제공", "인터랙티브 대시보드", "Streamlit UI")
    ]
    for c, (title, sub, desc) in zip(step_cols, steps):
        with c:
            st.info(f"**{title}**\n\n{sub}\n\n*{desc}*")

    st.divider()

    # 하단: DB 실데이터 기반 사례 미리보기
    disputes = load_disputes()
    bcol1, bcol2 = st.columns(2)

    with bcol1:
        st.markdown("#### 🕐 최근 등록 분쟁조정사례")
        if disputes.empty:
            st.info("분쟁사례 데이터가 없습니다.")
        else:
            for _, row in disputes.head(5).iterrows():
                st.markdown(f"- **[{row['area']}]** {row['title']}  \n"
                            f"  <span style='color:#8B92A5'>{row['dispute_type']} · {row['reg_date']}</span>",
                            unsafe_allow_html=True)

    with bcol2:
        st.markdown("#### 🔥 조회수 상위 분쟁조정사례")
        if disputes.empty:
            st.info("분쟁사례 데이터가 없습니다.")
        else:
            top_view = disputes.sort_values("view_count", ascending=False).head(5)
            for _, row in top_view.iterrows():
                st.markdown(f"- **[{row['area']}]** {row['title']}  \n"
                            f"  <span style='color:#8B92A5'>조회수 {int(row['view_count']):,} · {row['dispute_type']}</span>",
                            unsafe_allow_html=True)

    st.caption("상세 본문은 '분쟁사례 EDA' 탭의 사례 열람에서 확인할 수 있습니다.")


# ============================================================
# 금융상품 EDA 탭
# ============================================================

def render_product_eda():
    st.markdown("### 📊 금융상품 EDA")
    st.caption("금융감독원 통합비교공시 기준 6개 카테고리 상품의 분포와 금리 지형을 탐색합니다.")

    df = load_product_summary()
    if df.empty:
        st.warning("상품 데이터가 없습니다. 파이프라인 적재 상태를 확인하세요.")
        return

    # ---------- 필터 ----------
    fcol1, fcol2 = st.columns(2)
    with fcol1:
        areas = ["전체 권역"] + sorted(df["area_grp_nm"].dropna().unique().tolist())
        sel_area = st.selectbox("권역", areas)
    with fcol2:
        cats = ["전체 상품종류"] + [CATEGORY_LABELS[c] for c in CATEGORY_LABELS if c in df["category"].unique()]
        sel_cat = st.selectbox("상품종류", cats)

    filtered = df.copy()
    if sel_area != "전체 권역":
        filtered = filtered[filtered["area_grp_nm"] == sel_area]
    if sel_cat != "전체 상품종류":
        filtered = filtered[filtered["카테고리"] == sel_cat]

    if filtered.empty:
        st.info("선택한 조건에 해당하는 상품이 없습니다. 필터를 변경해 보세요.")
        return

    # ---------- KPI ----------
    k1, k2, k3 = st.columns(3)
    k1.metric("상품 수", f"{len(filtered):,} 개")
    active_ratio = filtered["is_active"].mean() * 100
    k2.metric("판매중 비율", f"{active_ratio:.1f} %")
    k3.metric("금융회사 수", f"{filtered['kor_co_nm'].nunique():,} 개사")

    st.divider()

    # ---------- 행 1: 상품종류별 상품 수 | 권역별 분포 ----------
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("##### 상품종류별 상품 수")
        cat_counts = filtered["카테고리"].value_counts().reset_index()
        cat_counts.columns = ["카테고리", "상품 수"]
        fig = px.bar(cat_counts, x="카테고리", y="상품 수",
                     color="카테고리", color_discrete_sequence=CHART_COLORS)
        fig.update_layout(showlegend=False)
        st.plotly_chart(style_fig(fig), use_container_width=True)

    with c2:
        st.markdown("##### 권역별 상품 분포")
        area_counts = filtered["area_grp_nm"].value_counts().reset_index()
        area_counts.columns = ["권역", "상품 수"]
        fig = px.bar(area_counts, x="권역", y="상품 수",
                     color="권역", color_discrete_sequence=CHART_COLORS)
        fig.update_layout(showlegend=False)
        st.plotly_chart(style_fig(fig), use_container_width=True)

    # ---------- 행 2: 금융회사 Top 10 | 판매 상태 도넛 ----------
    c3, c4 = st.columns(2)

    with c3:
        st.markdown("##### 금융회사별 상품 수 Top 10")
        top_co = filtered["kor_co_nm"].value_counts().head(10).reset_index()
        top_co.columns = ["금융회사", "상품 수"]
        fig = px.bar(top_co.sort_values("상품 수"), x="상품 수", y="금융회사", orientation="h",
                     color_discrete_sequence=[CHART_COLORS[0]])
        st.plotly_chart(style_fig(fig, height=420), use_container_width=True)

    with c4:
        st.markdown("##### 판매중 vs 판매종료")
        status = filtered["is_active"].map({True: "판매중", False: "판매종료"}).value_counts().reset_index()
        status.columns = ["상태", "상품 수"]
        fig = px.pie(status, names="상태", values="상품 수", hole=0.55,
                     color="상태",
                     color_discrete_map={"판매중": CHART_COLORS[0], "판매종료": "#3A3F4B"})
        st.plotly_chart(style_fig(fig, height=420), use_container_width=True)

    st.divider()

    # ---------- 행 3: 금리 분포 박스플롯 ----------
    st.markdown("##### 상품종류별 금리 분포")
    st.caption("예금·적금은 기본금리, 주담대·전세대출은 평균금리, 신용대출은 신용등급 평균금리 기준. 연금저축은 금리형 옵션이 없어 제외.")

    rates = load_option_rates()
    if rates.empty:
        st.info("금리 옵션 데이터가 없습니다.")
    else:
        rates = rates.copy()
        rates["카테고리"] = rates["category"].map(CATEGORY_LABELS).fillna(rates["category"])
        r_filtered = rates
        if sel_area != "전체 권역":
            r_filtered = r_filtered[r_filtered["area_grp_nm"] == sel_area]
        if sel_cat != "전체 상품종류":
            r_filtered = r_filtered[r_filtered["카테고리"] == sel_cat]

        if r_filtered.empty:
            st.info("선택한 조건에 해당하는 금리 옵션이 없습니다. (예: 연금저축은 금리형 옵션 미제공)")
        else:
            fig = px.box(r_filtered, x="카테고리", y="rate", color="카테고리",
                         color_discrete_sequence=CHART_COLORS,
                         labels={"rate": "금리 (%)"})
            fig.update_layout(showlegend=False)
            st.plotly_chart(style_fig(fig, height=420), use_container_width=True)

            # ---------- 행 4: 가입기간별 금리 추이 (예금/적금만 해당) ----------
            trm = r_filtered[r_filtered["save_trm"].notna()]
            if not trm.empty:
                st.markdown("##### 가입기간별 평균 금리 추이 (예금·적금)")
                trend = (trm.groupby(["카테고리", "save_trm"])
                            .agg(기본금리=("rate", "mean"), 우대금리=("rate_max", "mean"))
                            .reset_index()
                            .rename(columns={"save_trm": "가입기간(개월)"}))
                trend_long = trend.melt(id_vars=["카테고리", "가입기간(개월)"],
                                        value_vars=["기본금리", "우대금리"],
                                        var_name="금리 구분", value_name="평균 금리 (%)")
                fig = px.line(trend_long, x="가입기간(개월)", y="평균 금리 (%)",
                              color="카테고리", line_dash="금리 구분",
                              markers=True, color_discrete_sequence=CHART_COLORS)
                st.plotly_chart(style_fig(fig, height=420), use_container_width=True)

    # ---------- 종합 인사이트 (전체 데이터 기준 동적 계산) ----------
    st.divider()
    st.markdown("##### 📌 데이터가 말하는 것")

    lines = []

    # 1) 권역 간 예금 금리 격차
    dep = rates[rates["category"] == "deposit"] if not rates.empty else pd.DataFrame()
    if not dep.empty and dep["area_grp_nm"].nunique() >= 2:
        by_area = dep.groupby("area_grp_nm")["rate"].mean().sort_values(ascending=False)
        hi_a, lo_a = by_area.index[0], by_area.index[-1]
        gap = by_area.iloc[0] - by_area.iloc[-1]
        lines.append(f"<b>권역 간 금리 격차</b> — 정기예금 평균 기본금리는 {hi_a} {by_area.iloc[0]:.2f}% vs "
                     f"{lo_a} {by_area.iloc[-1]:.2f}%로 <b>{gap:.2f}%p 차이</b>. 동일한 예금 상품이라도 "
                     f"권역 선택만으로 수익 차가 발생하며, 이 격차가 소비자 이동과 분쟁 노출의 배경이 됨.")

    # 2) 우대금리 스프레드
    spread_df = rates[rates["category"].isin(["deposit", "saving"]) & rates["rate_max"].notna()] if not rates.empty else pd.DataFrame()
    if not spread_df.empty:
        spread = (spread_df["rate_max"] - spread_df["rate"]).mean()
        max_spread = (spread_df["rate_max"] - spread_df["rate"]).max()
        lines.append(f"<b>우대조건의 무게</b> — 예·적금의 우대금리는 기본금리보다 평균 <b>{spread:.2f}%p</b>, "
                     f"최대 {max_spread:.2f}%p 높음. 광고되는 최고금리와 실수령 금리의 간극이 크다는 뜻으로, "
                     f"우대조건(급여이체·카드실적 등) 충족 여부가 분쟁의 단골 쟁점이 되는 구조적 이유.")

    # 3) 가입기간-금리 관계 강도
    trm_all = rates[rates["save_trm"].notna()] if not rates.empty else pd.DataFrame()
    if len(trm_all) > 30:
        corr = trm_all["save_trm"].corr(trm_all["rate"])
        lines.append(f"<b>기간보다 상품</b> — 가입기간과 기본금리의 상관계수는 <b>{corr:.2f}</b>에 그침. "
                     f"'오래 맡길수록 이자가 높다'는 통념과 달리 금리는 기간보다 상품·회사 선택에 좌우되며, "
                     f"회귀분석(교차 인사이트 탭)에서도 동일하게 확인됨.")

    # 4) 판매 상태
    if not df.empty:
        act = df["is_active"].mean() * 100
        lines.append(f"<b>공시의 생애주기</b> — 전체 수집 상품 중 <b>{act:.0f}%만 현재 판매중</b>. "
                     f"나머지는 공시 종료된 이력 데이터로, 판매중 필터 없이 금리를 비교하면 "
                     f"이미 사라진 특판 금리에 눈높이가 맞춰지는 착시가 생길 수 있음.")

    if lines:
        insight_box(lines)
    st.caption("위 수치는 화면 조회 시점의 DB 집계로 자동 계산됩니다. (월배치 갱신 반영)")


# ============================================================
# 분쟁사례 EDA 탭
# ============================================================

def render_dispute_eda():
    st.markdown("### ⚖️ 분쟁사례 EDA")
    st.caption("금융감독원 분쟁조정사례 게시판 크롤링 데이터.")

    df = load_disputes()
    if df.empty:
        st.warning("분쟁사례 데이터가 없습니다. 파이프라인 적재 상태를 확인하세요.")
        return

    # ---------- 권역 필터 (드릴다운 진입점) ----------
    areas = ["전체 권역"] + sorted(df["area"].dropna().unique().tolist())
    sel_area = st.radio("권역 선택", areas, horizontal=True)

    filtered = df if sel_area == "전체 권역" else df[df["area"] == sel_area]

    # ---------- KPI ----------
    k1, k2, k3 = st.columns(3)
    k1.metric("분쟁사례 수", f"{len(filtered):,} 건")
    k2.metric("분쟁 유형 수", f"{filtered['dispute_type'].nunique()} 개")
    k3.metric("평균 본문 길이", f"{filtered['body_length'].mean():,.0f} 자")

    st.divider()

    # ---------- 행 1: 권역별 건수 | 연도별 추이 ----------
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("##### 권역별 분쟁 건수")
        area_counts = df["area"].value_counts().reset_index()
        area_counts.columns = ["권역", "건수"]
        fig = px.bar(area_counts, x="권역", y="건수",
                     color="권역", color_discrete_sequence=CHART_COLORS)
        fig.update_layout(showlegend=False)
        st.plotly_chart(style_fig(fig), use_container_width=True)
        st.caption("보험 권역이 전체의 약 80%를 차지합니다. (권역 선택과 무관한 전체 분포)")

    with c2:
        st.markdown("##### 등록 연도별 발생 추이")
        year_counts = (filtered.groupby("reg_year").size()
                       .reset_index(name="건수").dropna())
        fig = px.line(year_counts, x="reg_year", y="건수", markers=True,
                      labels={"reg_year": "등록 연도"},
                      color_discrete_sequence=CHART_COLORS)
        fig.update_xaxes(dtick=1)
        st.plotly_chart(style_fig(fig), use_container_width=True)

    # ---------- 행 2: 유형별 건수 (드릴다운) ----------
    st.markdown(f"##### 유형별 건수 — {sel_area}")
    type_counts = filtered["dispute_type"].value_counts().reset_index()
    type_counts.columns = ["유형", "건수"]
    fig = px.bar(type_counts.sort_values("건수"), x="건수", y="유형", orientation="h",
                 color_discrete_sequence=[CHART_COLORS[0]])
    st.plotly_chart(style_fig(fig, height=max(300, 24 * len(type_counts))), use_container_width=True)

    st.divider()

    # ---------- 행 3: 본문 길이 히스토그램 | 유형별 본문 길이 박스플롯 ----------
    c3, c4 = st.columns(2)

    with c3:
        st.markdown("##### 본문 길이 분포")
        fig = px.histogram(filtered, x="body_length", nbins=30,
                           labels={"body_length": "본문 길이 (자)"},
                           color_discrete_sequence=[CHART_COLORS[1]])
        fig.update_layout(yaxis_title="사례 수")
        st.plotly_chart(style_fig(fig), use_container_width=True)

    with c4:
        st.markdown("##### 유형별 본문 길이 비교 (상위 8개 유형)")
        top_types = filtered["dispute_type"].value_counts().head(8).index
        box_df = filtered[filtered["dispute_type"].isin(top_types)]
        fig = px.box(box_df, x="body_length", y="dispute_type",
                     labels={"body_length": "본문 길이 (자)", "dispute_type": ""},
                     color_discrete_sequence=[CHART_COLORS[2]])
        st.plotly_chart(style_fig(fig), use_container_width=True)

    # ---------- 행 4: 민원 본문 키워드 빈도 ----------
    st.markdown(f"##### 민원 본문 키워드 빈도 Top 15 — {sel_area}")
    st.caption("단순 어절 빈도 기준(형태소 분석 미적용). 조사가 결합된 형태가 섞일 수 있습니다.")

    texts = filtered["complaint_text"].dropna()
    if texts.empty:
        st.info("민원 본문 텍스트가 없습니다.")
    else:
        tokens = []
        for t in texts:
            tokens.extend(re.findall(r"[가-힣]{2,}", t))
        tokens = [t for t in tokens if t not in STOPWORDS]
        top_kw = Counter(tokens).most_common(15)
        kw_df = pd.DataFrame(top_kw, columns=["키워드", "빈도"])
        fig = px.bar(kw_df.sort_values("빈도"), x="빈도", y="키워드", orientation="h",
                     color_discrete_sequence=[CHART_COLORS[3]])
        st.plotly_chart(style_fig(fig, height=420), use_container_width=True)

    st.divider()

    # ---------- 행 5: 조회수 상위 목록 + 사례 상세 열람 ----------
    c5, c6 = st.columns([1, 1])

    with c5:
        st.markdown("##### 조회수 상위 분쟁사례")
        top_view = (filtered.sort_values("view_count", ascending=False)
                    .head(10)[["title", "dispute_type", "view_count", "reg_date"]]
                    .rename(columns={"title": "제목", "dispute_type": "유형",
                                     "view_count": "조회수", "reg_date": "등록일"}))
        st.dataframe(top_view, use_container_width=True, hide_index=True)

    with c6:
        st.markdown("##### 사례 상세 열람")
        options = filtered.apply(
            lambda r: f"[{r['dispute_type']}] {r['title']}", axis=1).tolist()
        sel_case = st.selectbox("사례 선택", options, label_visibility="collapsed")
        idx = options.index(sel_case)
        row = filtered.iloc[idx]

        st.markdown(f"**{row['title']}**")
        st.caption(f"{row['area']} · {row['dispute_type']} · {row['reg_date']} · 조회수 {int(row['view_count']):,}")

        sections = [
            ("민원내용", row["complaint_text"]),
            ("쟁점", row["issue_text"]),
            ("처리결과", row["result_text"]),
            ("소비자 유의사항", row["consumer_note_text"]),
        ]
        for name, content in sections:
            with st.expander(f"▣ {name}", expanded=(name == "민원내용")):
                if isinstance(content, str) and content.strip():
                    st.write(content)
                else:
                    st.caption("해당 섹션이 없는 사례입니다. (parse_status: " + str(row["parse_status"]) + ")")

    # ---------- 종합 인사이트 (전체 데이터 기준 동적 계산) ----------
    st.divider()
    st.markdown("##### 📌 데이터가 말하는 것")

    lines = []

    # 1) 권역 편중
    ins_share = (df["area"] == "보험").mean() * 100
    top_type = df["dispute_type"].value_counts()
    lines.append(f"<b>분쟁의 무게중심은 보험</b> — 전체 {len(df)}건 중 <b>{ins_share:.0f}%가 보험 권역</b>이고, "
                 f"단일 유형 1위는 '{top_type.index[0]}'({top_type.iloc[0]}건). 상품 스펙이 명확한 예·적금과 달리 "
                 f"보험은 '지급 요건 해석'이 개입하는 구조라 분쟁이 집중되는 것으로 해석됨.")

    # 2) 관심도(조회수) 편중
    top10 = df.sort_values("view_count", ascending=False).head(10)
    top10_ins = (top10["area"] == "보험").sum()
    lines.append(f"<b>소비자 관심도 동조</b> — 조회수 상위 10건 중 <b>{top10_ins}건이 보험</b> 사례. "
                 f"발생 건수뿐 아니라 소비자가 찾아보는 선례도 보험에 쏠려 있어, "
                 f"보험 분쟁 정보의 접근성 개선이 실질 수요가 가장 큰 영역임을 시사.")

    # 3) 키워드가 가리키는 분쟁의 성격
    texts_all = df["complaint_text"].dropna()
    if not texts_all.empty:
        tokens_all = []
        for t in texts_all:
            tokens_all.extend(re.findall(r"[가-힣]{2,}", t))
        pay_related = sum(1 for t in tokens_all if t.startswith(("지급", "부지급", "미지급")))
        lines.append(f"<b>분쟁의 언어는 '지급'</b> — 민원 본문에서 '지급/부지급' 계열 어휘가 <b>{pay_related:,}회</b> 등장. "
                     f"분쟁 대다수가 상품 자체의 하자가 아니라 <b>지급 심사·약관 해석 단계</b>에서 발생함을 보여주며, "
                     f"이는 본 서비스가 상품 스펙과 분쟁 선례를 함께 보여주는 이유이기도 함.")

    # 4) 본문 길이 = 사건 복잡도 프록시
    len_by_area = df.groupby("area")["body_length"].mean().sort_values(ascending=False)
    lines.append(f"<b>본문 길이는 복잡도의 프록시</b> — 권역별 평균 본문 길이는 {len_by_area.index[0]} "
                 f"{len_by_area.iloc[0]:,.0f}자로 최장. 긴 본문일수록 쟁점·심사 논거가 많다는 뜻이라, "
                 f"길이 분포는 어떤 유형이 '설명이 필요한 분쟁'인지 가늠하는 간접 지표가 됨.")

    insight_box(lines)
    st.caption("위 수치는 화면 조회 시점의 DB 집계로 자동 계산됩니다. (월배치 갱신 반영)")


# ============================================================
# 교차 인사이트 탭
# ============================================================

def render_insight():
    st.markdown("### 💡 교차 인사이트")
    st.caption("상품 데이터(정형)와 분쟁사례(비정형)를 연결한 분석. "
               "교차 대상은 은행ㆍ중소서민·금융투자 41건에 한정되며, 유형당 표본이 적어 "
               "통계적 결론보다 탐색적 참고 지표로 제공합니다.")

    # ---------- 0. 교차분석 핵심 요약 (동적 계산) ----------
    cross = run_query("SELECT * FROM v_dispute_product_cross")
    disputes_all = load_disputes()
    if not cross.empty and not disputes_all.empty:
        unmatched = int(cross[cross["product_category"] == "미매칭"]["dispute_count"].sum())
        yeosusin = disputes_all[disputes_all["dispute_type"] == "여ㆍ수신"]
        insight_box([
            f"<b>교차의 핵심 발견</b> — 상품 데이터와 직접 연결 가능한 분쟁은 '여ㆍ수신' 유형 "
            f"<b>{len(yeosusin)}건</b>뿐이고, {unmatched}건은 대응 상품이 없어 미매칭. "
            f"즉 <b>'상품 스펙 위반'형 분쟁은 소수</b>이며, 대다수는 지급 심사·약관 해석 단계에서 발생 — "
            f"이것이 본 분석이 상품-분쟁을 1:1 매칭 대신 '조건 관련 분쟁 요인 탐색' 프레임으로 설계된 근거.",
            f"<b>데이터 구조가 주는 교훈</b> — 원본에 상품↔분쟁 공유 코드가 없다는 사실 자체가 발견. "
            f"금융 공시 데이터와 분쟁 데이터가 연결 고리 없이 관리되고 있어, 소비자가 두 정보를 함께 보려면 "
            f"본 서비스 같은 별도의 통합 계층이 필요함.",
        ])

    # ---------- 1. 상품카테고리 x 분쟁유형 교차 건수 ----------
    st.markdown("##### 상품카테고리 × 분쟁유형 교차 건수")
    if cross.empty:
        st.info("교차 데이터가 없습니다.")
    else:
        cross_disp = cross.copy()
        cross_disp["product_category"] = cross_disp["product_category"].map(
            lambda c: CATEGORY_LABELS.get(c, c))
        cross_disp = cross_disp.rename(columns={
            "product_category": "상품카테고리", "area": "권역",
            "dispute_type": "분쟁유형", "dispute_count": "건수"})
        st.dataframe(cross_disp, use_container_width=True, hide_index=True)
        st.caption("'여ㆍ수신' 유형은 예·적금/대출 5개 카테고리에 1:N으로 매핑되므로 카테고리 간 건수가 중복 집계됩니다. "
                   "'미매칭'은 수집한 finlife 카테고리에 대응 상품이 없는 유형입니다(억지 매칭 대신 명시적 미매칭 처리).")

    st.divider()

    # ---------- 2. 상품카테고리별 평균 금리 vs 관련 분쟁 건수 ----------
    st.markdown("##### 상품카테고리별 평균 금리 vs 관련 분쟁 건수")

    rates = load_option_rates()
    if not cross.empty and not rates.empty:
        matched = cross[cross["product_category"] != "미매칭"]
        disp_by_cat = matched.groupby("product_category")["dispute_count"].sum().reset_index()

        rate_by_cat = rates.groupby("category")["rate"].mean().reset_index()
        merged = disp_by_cat.merge(rate_by_cat, left_on="product_category", right_on="category", how="left")
        merged["카테고리"] = merged["product_category"].map(lambda c: CATEGORY_LABELS.get(c, c))
        merged = merged.rename(columns={"dispute_count": "관련 분쟁 건수", "rate": "평균 금리 (%)"})

        fig = px.scatter(merged, x="평균 금리 (%)", y="관련 분쟁 건수",
                         text="카테고리", size="관련 분쟁 건수",
                         color="카테고리", color_discrete_sequence=CHART_COLORS)
        fig.update_traces(textposition="top center")
        fig.update_layout(showlegend=False)
        st.plotly_chart(style_fig(fig, height=420), use_container_width=True)
        st.caption("탐색적 지표입니다. 매핑이 포괄 유형('여ㆍ수신') 기반이라 카테고리별 건수가 동일하게 나타날 수 있으며, "
                   "이는 원본 데이터에 상품-분쟁 공유 코드가 없는 구조적 한계입니다.")
    else:
        st.info("교차 분석에 필요한 데이터가 부족합니다.")

    st.divider()

    # ---------- 3. 머신러닝 분석 ----------
    st.markdown("##### 머신러닝 분석")

    tab_ml1, tab_ml2 = st.tabs(["분쟁사례 텍스트 군집화 (TF-IDF + SVD)", "예금 금리 예측 회귀분석"])

    with tab_ml1:
        df_dispute = run_query("""
            SELECT area, dispute_type, complaint_text
            FROM dispute_cases
            WHERE complaint_text IS NOT NULL AND complaint_text != ''
        """)

        if not df_dispute.empty:
            tfidf = TfidfVectorizer(max_features=300)
            X_tfidf = tfidf.fit_transform(df_dispute['complaint_text'])

            svd = TruncatedSVD(n_components=2, random_state=42)
            X_svd = svd.fit_transform(X_tfidf)

            df_dispute['SVD 차원 1'] = X_svd[:, 0]
            df_dispute['SVD 차원 2'] = X_svd[:, 1]

            fig1 = px.scatter(
                df_dispute, x='SVD 차원 1', y='SVD 차원 2',
                color='area',
                hover_data=['dispute_type'],
                opacity=0.8,
                color_discrete_sequence=CHART_COLORS,
            )
            st.plotly_chart(style_fig(fig1), use_container_width=True)
            st.caption("전문 용어가 뚜렷한 보험 사례는 군집이 구분되는 반면, 범용 어휘를 공유하는 은행권 사례는 "
                       "단일 군집으로 혼재 — 형태소 분석 등 도메인 특화 전처리 고도화가 다음 개선 타겟입니다.")
        else:
            st.info("분쟁사례 텍스트 데이터가 부족하여 군집화를 수행할 수 없습니다.")

    with tab_ml2:
        df_deposit = run_query("""
            SELECT save_trm, intr_rate
            FROM product_deposit_option
            WHERE save_trm IS NOT NULL AND intr_rate IS NOT NULL
        """)

        if not df_deposit.empty:
            X = df_deposit[['save_trm']]
            y = df_deposit['intr_rate']

            model = LinearRegression()
            model.fit(X, y)
            df_deposit['예측 금리 (%)'] = model.predict(X)
            df_deposit['실제 금리 (%)'] = y

            fig2 = px.scatter(df_deposit, x='실제 금리 (%)', y='예측 금리 (%)', opacity=0.7,
                              color_discrete_sequence=CHART_COLORS)

            min_val = min(df_deposit['실제 금리 (%)'].min(), df_deposit['예측 금리 (%)'].min())
            max_val = max(df_deposit['실제 금리 (%)'].max(), df_deposit['예측 금리 (%)'].max())
            fig2.add_shape(type="line", x0=min_val, y0=min_val, x1=max_val, y1=max_val,
                           line=dict(color="gray", dash="dash"))

            st.plotly_chart(style_fig(fig2), use_container_width=True)
            st.caption("가입기간 단일 변수로는 평균적인 금리 대역만 예측 — 예측선을 크게 벗어나는 잔차는 "
                       "특판/우대조건 상품일 가능성이 높아, 이상치 탐지 관점의 확장 여지가 있습니다.")
        else:
            st.info("금리 분석을 위한 상품 데이터가 부족합니다.")


# ============================================================
# main
# ============================================================

def main():
    tabs = st.tabs(["🏠 홈 대시보드", "📊 금융상품 EDA", "⚖️ 분쟁사례 EDA", "💡 교차 인사이트"])
    with tabs[0]: render_home()
    with tabs[1]: render_product_eda()
    with tabs[2]: render_dispute_eda()
    with tabs[3]: render_insight()


if __name__ == "__main__":
    main()
