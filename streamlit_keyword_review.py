#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
키워드 라벨링 검토 Streamlit 앱

규칙 기반 키워드 필터링 결과를 사람이 검토하고 수정할 수 있는 인터페이스
"""

import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime

# 와이드 모드 설정
st.set_page_config(page_title="키워드 라벨링 검토", layout="wide")

# CSS 스타일 정의
st.markdown("""
<style>
    /* 하이라이트 색상 정의 */
    .highlight-depression {
        background-color: #e74c3c;
        color: white;
        padding: 2px 4px;
        border-radius: 3px;
        font-weight: bold;
    }
    .highlight-mobile {
        background-color: #3498db;
        color: white;
        padding: 2px 4px;
        border-radius: 3px;
        font-weight: bold;
    }
    .highlight-behavioral {
        background-color: #2ecc71;
        color: white;
        padding: 2px 4px;
        border-radius: 3px;
        font-weight: bold;
    }
    
    /* 키워드 버튼 스타일 */
    .keyword-button {
        display: inline-block;
        margin: 2px;
        padding: 4px 8px;
        border-radius: 15px;
        cursor: pointer;
        font-size: 0.9em;
        border: 1px solid #ddd;
    }
    .keyword-button-depression {
        background-color: #e74c3c;
        color: white;
    }
    .keyword-button-mobile {
        background-color: #3498db;
        color: white;
    }
    .keyword-button-behavioral {
        background-color: #2ecc71;
        color: white;
    }
    .keyword-button:hover {
        opacity: 0.8;
    }
    
    /* 논문 카드 스타일 */
    .paper-card {
        background: transparent;
        padding: 20px;
        margin: 10px 0;
        border: 2px solid #e0e0e0;
        border-radius: 8px;
        font-size: 1.1em;
        line-height: 1.6;
    }
    
    /* 결과 버튼 스타일 */
    .result-include {
        background-color: #28a745 !important;
        color: white !important;
    }
    .result-exclude {
        background-color: #dc3545 !important;
        color: white !important;
    }
    
    /* 범례 스타일 */
    .legend {
        display: flex;
        gap: 20px;
        margin: 10px 0;
        padding: 10px;
        background-color: transparent;
        border: 1px solid #e0e0e0;
        border-radius: 5px;
        justify-content: center;
    }
    .legend-item {
        display: flex;
        align-items: center;
        gap: 5px;
    }
    
    /* 데이터 목록 테이블 스타일 */
    .data-table-header {
        background-color: #f8f9fa;
        padding: 8px;
        font-weight: bold;
        border-bottom: 2px solid #dee2e6;
        border-top: 1px solid #dee2e6;
        border-left: 1px solid #dee2e6;
        border-right: 1px solid #dee2e6;
        border-radius: 8px 8px 0 0;
        text-align: center;
        font-size: 0.9em;
    }
    .data-table-cell {
        padding: 8px;
        border-bottom: 1px solid #dee2e6;
        background-color: white;
        height: 45px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .data-table-cell-left {
        justify-content: flex-start;
    }
</style>
""", unsafe_allow_html=True)

# 세션 상태 초기화
if 'current_idx' not in st.session_state:
    st.session_state.current_idx = 0
if 'df' not in st.session_state:
    st.session_state.df = None
if 'file_name' not in st.session_state:
    st.session_state.file_name = None
if 'changes_made' not in st.session_state:
    st.session_state.changes_made = False
if 'reviewer_name' not in st.session_state:
    st.session_state.reviewer_name = ""
if 'selected_keywords' not in st.session_state:
    st.session_state.selected_keywords = {'depression': set(), 'mobile': set(), 'behavioral': set()}
if 'use_word_boundary' not in st.session_state:
    st.session_state.use_word_boundary = True

def load_csv(file_path):
    """CSV 파일 로드 (로컬 버전용)"""
    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        return process_loaded_df(df)
    except Exception as e:
        st.error(f"파일 로드 오류: {e}")
        return None

def load_csv_from_upload(uploaded_file):
    """업로드된 CSV 파일 로드 (클라우드 버전용)"""
    try:
        df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
        return process_loaded_df(df)
    except Exception as e:
        st.error(f"파일 로드 오류: {e}")
        return None

def process_loaded_df(df):
    """로드된 DataFrame 처리"""
    # 하이브리드 결과 파일인지 확인
    is_hybrid = all(col in df.columns for col in ['rule_result', 'llm_result', 'final_result'])
    
    if is_hybrid:
        # 하이브리드 파일의 경우 호환성을 위해 컬럼 매핑
        if 'depression_keywords' not in df.columns:
            df['depression_keywords'] = df.get('rule_depression_keywords', '')
        if 'mobile_keywords' not in df.columns:
            df['mobile_keywords'] = df.get('rule_mobile_keywords', '')
        if 'behavioral_keywords' not in df.columns:
            df['behavioral_keywords'] = df.get('rule_behavioral_keywords', '')
        if 'result' not in df.columns:
            df['result'] = df.get('rule_result', '')
    
    # 필수 컬럼 확인
    required_columns = ['Title', 'Abstract', 'depression_keywords', 'mobile_keywords', 
                       'behavioral_keywords', 'result']
    
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        st.error(f"필수 컬럼이 없습니다: {missing_columns}")
        return None
    
    # 인간 검토 컬럼 추가 (없으면)
    review_columns = {
        'human_depression_keywords': '',
        'human_mobile_keywords': '',
        'human_behavioral_keywords': '',
        'human_result': '',
        'reviewer_name': '',
        'review_status': '미완료',
        'review_date': None
    }
    
    for col, default_val in review_columns.items():
        if col not in df.columns:
            df[col] = default_val
    
    return df

# save_csv 함수 제거 - 클라우드 버전에서는 메모리 기반 작업만 수행

def parse_keywords(keywords_str):
    """키워드 문자열 파싱"""
    if pd.isna(keywords_str) or not str(keywords_str).strip():
        return []
    
    # 쉼표, 세미콜론, 파이프로 분리
    keywords = re.split(r'[,;|]', str(keywords_str))
    return [k.strip() for k in keywords if k.strip()]

def convert_wildcard_to_regex(keyword):
    """와일드카드 키워드를 정규식 패턴으로 변환"""
    # activity schedul* -> activity schedul\w*
    # behavio* interven* -> behavio\w*\s+interven\w*
    # behavio* therap* -> behavio\w*\s+therap\w*
    
    if '*' in keyword:
        # *를 \w*로 변환하고, 공백은 \s+로 변환
        regex_pattern = keyword.replace('*', r'\w*')
        regex_pattern = re.sub(r'\s+', r'\\s+', regex_pattern)
        return r'\b' + regex_pattern + r'\b'
    else:
        return None

def highlight_all_keywords(text, all_selected_keywords):
    """모든 선택된 키워드들을 텍스트에서 한번에 하이라이트"""
    if not text:
        return text
    
    highlighted_text = str(text)
    
    # 모든 키워드와 그 매칭 패턴을 수집
    all_matches = []
    
    for category, keywords in all_selected_keywords.items():
        if not keywords:
            continue
            
        class_name = f"highlight-{category}"
        
        for keyword in keywords:
            # 와일드카드 패턴 처리
            wildcard_pattern = convert_wildcard_to_regex(keyword)
            
            if wildcard_pattern:
                # 와일드카드 패턴 사용
                pattern = re.compile(wildcard_pattern, re.IGNORECASE)
            else:
                # 일반 키워드 처리
                if st.session_state.use_word_boundary:
                    # 단어 경계를 사용한 정확한 매칭
                    if len(keyword.split()) == 1:
                        # 단일 단어의 경우 단어 경계 확인
                        pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
                    else:
                        # 구문의 경우 전체 매칭
                        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
                else:
                    # 부분 문자열 매칭 (기존 방식)
                    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            
            # 모든 매칭 찾기
            for match in pattern.finditer(highlighted_text):
                all_matches.append({
                    'start': match.start(),
                    'end': match.end(),
                    'text': match.group(0),
                    'class': class_name
                })
    
    # 매칭된 위치 기준으로 정렬 (뒤에서부터 처리하기 위해 역순)
    all_matches.sort(key=lambda x: x['start'], reverse=True)
    
    # 겹치는 매칭 제거 (더 긴 매칭을 우선)
    filtered_matches = []
    for match in all_matches:
        is_overlap = False
        for existing in filtered_matches:
            if (match['start'] < existing['end'] and match['end'] > existing['start']):
                is_overlap = True
                break
        if not is_overlap:
            filtered_matches.append(match)
    
    # 뒤에서부터 하이라이트 적용 (인덱스 변경 방지)
    for match in filtered_matches:
        highlighted_text = (
            highlighted_text[:match['start']] +
            f'<span class="{match["class"]}">{match["text"]}</span>' +
            highlighted_text[match['end']:]
        )
    
    return highlighted_text

def toggle_keyword_selection(category, keyword):
    """키워드 선택 토글"""
    if keyword in st.session_state.selected_keywords[category]:
        st.session_state.selected_keywords[category].remove(keyword)
    else:
        st.session_state.selected_keywords[category].add(keyword)

def update_paper_data():
    """현재 논문 데이터 업데이트"""
    idx = st.session_state.current_idx
    
    # 선택된 키워드들을 문자열로 변환
    human_depression = ', '.join(sorted(st.session_state.selected_keywords['depression']))
    human_mobile = ', '.join(sorted(st.session_state.selected_keywords['mobile']))
    human_behavioral = ', '.join(sorted(st.session_state.selected_keywords['behavioral']))
    
    # 결과 결정 (모든 카테고리에 키워드가 있으면 include)
    has_all_categories = (
        len(st.session_state.selected_keywords['depression']) > 0 and
        len(st.session_state.selected_keywords['mobile']) > 0 and
        len(st.session_state.selected_keywords['behavioral']) > 0
    )
    human_result = 'include' if has_all_categories else 'exclude'
    
    # DataFrame 업데이트
    st.session_state.df.at[idx, 'human_depression_keywords'] = human_depression
    st.session_state.df.at[idx, 'human_mobile_keywords'] = human_mobile
    st.session_state.df.at[idx, 'human_behavioral_keywords'] = human_behavioral
    st.session_state.df.at[idx, 'human_result'] = human_result
    st.session_state.df.at[idx, 'reviewer_name'] = st.session_state.reviewer_name
    st.session_state.df.at[idx, 'review_status'] = '완료'
    st.session_state.df.at[idx, 'review_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    st.session_state.changes_made = True

def load_current_paper_keywords():
    """현재 논문의 키워드 로드 - segmented_control options와 일치하는 키워드만 활성화"""
    # segmented_control에서 사용하는 옵션과 정확히 일치시키기
    depression_keywords = {
        "depression", "depressive symptoms", "depressive disorder"
    }
    
    mobile_keywords = {
        "mobile application", "smartphone application", "mobile", "smartphone",
        "iphone", "android", "app", "digital", "digital therapeutic", "mhealth"
    }
    
    behavioral_keywords = {
        "behavioral activation", "behavioural activation", "activity schedul*", 
        "behavio* interven*", "behavio* therap*"
    }
    
    st.session_state.selected_keywords = {
        'depression': depression_keywords,
        'mobile': mobile_keywords,
        'behavioral': behavioral_keywords
    }

def render_sidebar():
    """사이드바 렌더링"""
    with st.sidebar:
        st.divider()
        st.header("📁 파일 관리")
        
        # 파일 로드 방식 선택
        load_method = st.radio(
            "파일 로드 방식",
            ["로컬 파일 선택", "파일 업로드"],
            key="load_method"
        )
        
        if load_method == "로컬 파일 선택":
            # 로컬 파일 선택 섹션
            output_files = []
            if os.path.exists("output"):
                for file in os.listdir("output"):
                    # 규칙 기반, LLM 2차, 하이브리드 결과 파일 모두 포함
                    if ((file.startswith("rule_based_labeling_") or 
                         file.startswith("llm_secondary_results_") or
                         file.startswith("hybrid_final_results_")) and 
                        file.endswith(".csv")):
                        full_path = os.path.join("output", file)
                        output_files.append(full_path)
            
            # rule_base_output 디렉토리도 확인
            if os.path.exists("rule_base_output"):
                for file in os.listdir("rule_base_output"):
                    if file.startswith("rule_based_results_") and file.endswith(".csv"):
                        full_path = os.path.join("rule_base_output", file)
                        output_files.append(full_path)
            
            if output_files:
                # 가장 최근 파일이 먼저 오도록 정렬
                output_files.sort(key=lambda x: os.path.getctime(x), reverse=True)
                
                selected_file = st.selectbox(
                    "파일 선택",
                    output_files,
                    format_func=lambda x: os.path.basename(x),
                    index=0
                )
                
                if st.button("로컬 파일 로드", use_container_width=True):
                    df = load_csv(selected_file)
                    if df is not None:
                        st.session_state.df = df
                        st.session_state.file_name = os.path.basename(selected_file)
                        st.session_state.current_idx = 0
                        load_current_paper_keywords()
                        st.success(f"파일 '{os.path.basename(selected_file)}'이 성공적으로 로드되었습니다!")
                        st.rerun()
            else:
                st.warning("분석 결과 파일을 찾을 수 없습니다.")
                st.info("먼저 다음 중 하나를 실행하세요:")
                st.code("python pipeline_runner_rule.py  # 규칙 기반 필터링")
                st.code("python llm_secondary_filter.py  # LLM 2차 필터링")
                st.code("python pipeline_hybrid_filter.py  # 하이브리드 필터링")
        
        else:  # 파일 업로드
            uploaded_file = st.file_uploader(
                "CSV 파일 업로드",
                type=['csv'],
                help="검토할 CSV 파일을 업로드하세요. 규칙 기반, LLM 2차, 하이브리드 결과 파일을 지원합니다.",
                key="csv_uploader"
            )
            
            if uploaded_file is not None:
                if st.button("업로드 파일 로드", use_container_width=True):
                    df = load_csv_from_upload(uploaded_file)
                    if df is not None:
                        st.session_state.df = df
                        st.session_state.file_name = uploaded_file.name  # 파일명만 저장
                        st.session_state.current_idx = 0
                        load_current_paper_keywords()
                        st.success(f"파일 '{uploaded_file.name}'이 성공적으로 로드되었습니다!")
                        st.rerun()
            else:
                st.info("📁 CSV 파일을 업로드하여 검토를 시작하세요.")
                st.markdown("**지원 파일:**")
                st.markdown("- 규칙 기반 필터링 결과")
                st.markdown("- LLM 2차 필터링 결과")
                st.markdown("- 하이브리드 필터링 결과")
                st.markdown("- 이전 검토 작업 파일")
        
        # 키워드 매칭 설정
        if st.session_state.df is not None:
            st.divider()
            st.header("⚙️ 매칭 설정")
            
            word_boundary_enabled = st.toggle(
                "정확한 단어 매칭",
                value=st.session_state.use_word_boundary,
                help="켜기: 'app'이 'apply'에서 매칭되지 않음 (정확)\n끄기: 'app'이 'apply'에서도 매칭됨 (포괄적)",
                key="word_boundary_toggle"
            )
            st.session_state.use_word_boundary = word_boundary_enabled
            
            if word_boundary_enabled:
                st.caption("🎯 정확한 단어 매칭 활성화")
                st.caption("예: 'app' ≠ 'apply', 'application'")
            else:
                st.caption("🔍 포괄적 부분 매칭 활성화")
                st.caption("예: 'app' = 'apply', 'application' 포함")
        
        # 검토자 정보
        if st.session_state.df is not None:
            st.divider()
            st.header("👤 검토자 정보")
            
            reviewers = ["황가네", "이가네", "김가네", "이방인"]
            
            current_index = None
            if st.session_state.reviewer_name in reviewers:
                current_index = reviewers.index(st.session_state.reviewer_name)
            
            selected_reviewer = st.radio(
                "검토자를 선택하세요:",
                reviewers,
                index=current_index,
                key="reviewer_radio"
            )
            
            if selected_reviewer == "기타":
                custom_name = st.text_input(
                    "검토자 이름 입력:",
                    value=st.session_state.reviewer_name if st.session_state.reviewer_name not in reviewers[:-1] else "",
                    key="custom_reviewer_input"
                )
                st.session_state.reviewer_name = custom_name
            else:
                st.session_state.reviewer_name = selected_reviewer
            
            if not st.session_state.reviewer_name:
                st.warning("검토자를 선택하거나 입력해주세요")
        
        # 다운로드 섹션
        if st.session_state.df is not None:
            st.divider()
            st.header("📥 결과 다운로드")
            
            # 진행 상황 표시
            total = len(st.session_state.df)
            completed = (st.session_state.df['review_status'] != '미완료').sum()
            progress = completed / total if total > 0 else 0
            
            st.metric(
                label="검토 진행률",
                value=f"{completed}/{total}",
                delta=f"{progress*100:.1f}%"
            )
            
            # 변경사항 표시
            if st.session_state.changes_made:
                st.warning("💾 저장되지 않은 변경사항이 있습니다.")
            else:
                st.success("✅ 모든 변경사항이 메모리에 저장되었습니다.")
            
            # 다운로드 버튼
            csv_data = st.session_state.df.to_csv(index=False, encoding='utf-8-sig')
            current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"reviewed_results_{current_time}.csv"
            
            st.download_button(
                label="📥 검토 결과 다운로드",
                data=csv_data,
                file_name=filename,
                mime="text/csv",
                use_container_width=True,
                help="현재 검토 상태를 CSV 파일로 다운로드합니다. 다운로드 후 파일을 다시 업로드하여 작업을 이어갈 수 있습니다."
            )
            
            st.caption("💡 **팁**: 다운로드한 파일을 다시 업로드하여 작업을 이어갈 수 있습니다.")

def render_data_navigation():
    """데이터 목록 네비게이션"""
    st.markdown("## 📋 논문 목록")
    
    # 하이브리드 파일인지 확인
    is_hybrid_file = 'final_result' in st.session_state.df.columns
    
    # 필터링된 데이터 초기화
    df = st.session_state.df.copy()
    
    # 필터링 옵션
    if is_hybrid_file:
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.selectbox(
                "상태 필터",
                ["전체", "미완료", "완료"],
                key="status_filter"
            )
        
        with col2:
            # Publication Year 필터
            all_years = sorted(df['Publication Year'].dropna().unique()) if 'Publication Year' in df.columns else []
            year_filter = st.multiselect(
                "출간연도 필터",
                options=all_years,
                default=[],
                key="year_filter"
            )
            
        with col3:
            final_filter = st.selectbox(
                "최종 결과 필터",
                ["전체", "Include", "Exclude", "불일치"],
                key="final_filter"
            )
    else:
        col1, col2 = st.columns(2)
        with col1:
            status_filter = st.selectbox(
                "상태 필터",
                ["전체", "미완료", "완료"],
                key="status_filter"
            )
        
        with col2:
            # Publication Year 필터
            all_years = sorted(df['Publication Year'].dropna().unique()) if 'Publication Year' in df.columns else []
            year_filter = st.multiselect(
                "출간연도 필터",
                options=all_years,
                default=[],
                key="year_filter"
            )
            final_filter = "전체"
    
    if status_filter != "전체":
        if status_filter == "완료":
            df = df[df['review_status'].isin(['완료', 'include', 'exclude'])]
        else:
            df = df[df['review_status'] == '미완료']
    
    # Publication Year 필터링
    if year_filter:
        df = df[df['Publication Year'].isin(year_filter)]
    
    if is_hybrid_file and final_filter != "전체":
        if final_filter == "Include":
            df = df[df['final_result'] == 'include']
        elif final_filter == "Exclude":
            df = df[df['final_result'] == 'exclude']
        elif final_filter == "불일치":
            # rule_result와 final_result가 다른 경우
            rule_col = 'rule_result' if 'rule_result' in df.columns else 'result'
            df = df[df[rule_col] != df['final_result']]
    
    # 페이지네이션
    items_per_page = 10
    total_items = len(df)
    total_pages = (total_items + items_per_page - 1) // items_per_page
    
    if 'data_page' not in st.session_state:
        st.session_state.data_page = 0
    
    # 현재 페이지가 범위를 벗어나면 조정
    if st.session_state.data_page >= total_pages:
        st.session_state.data_page = max(0, total_pages - 1)
    
    # 테이블 헤더
    if is_hybrid_file:
        header_cols = st.columns([0.06, 0.06, 0.22, 0.08, 0.11, 0.11, 0.11, 0.11, 0.11])
        headers = ["선택", "번호", "제목", "출간연도", "최종결과", "검토결과", "검토자", "검토상태", "변경"]
    else:
        header_cols = st.columns([0.08, 0.08, 0.28, 0.10, 0.14, 0.14, 0.14])
        headers = ["선택", "번호", "제목", "출간연도", "검토결과", "검토자", "검토상태"]
    
    for col, header in zip(header_cols, headers):
        with col:
            st.markdown(f'<div class="data-table-header">{header}</div>', unsafe_allow_html=True)
    
    # 현재 페이지 데이터
    start_idx = st.session_state.data_page * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)
    page_data = df.iloc[start_idx:end_idx]
    
    # 데이터 행들
    for row_idx, row_data in page_data.iterrows():
        is_current = (row_idx == st.session_state.current_idx)
        
        if is_hybrid_file:
            cols = st.columns([0.06, 0.06, 0.22, 0.08, 0.11, 0.11, 0.11, 0.11, 0.11])
        else:
            cols = st.columns([0.08, 0.08, 0.28, 0.10, 0.14, 0.14, 0.14])
        
        with cols[0]:
            if st.button(
                "●" if is_current else "○",
                key=f"select_{row_idx}",
                use_container_width=True,
                type="primary" if is_current else "secondary"
            ):
                st.session_state.current_idx = row_idx
                load_current_paper_keywords()
                st.rerun()
        
        with cols[1]:
            st.markdown(f'<div class="data-table-cell"><strong>#{row_idx + 1}</strong></div>', unsafe_allow_html=True)
        
        with cols[2]:
            title_len = 30 if is_hybrid_file else 40
            title = str(row_data.get('Title', ''))[:title_len] + "..." if len(str(row_data.get('Title', ''))) > title_len else str(row_data.get('Title', ''))
            st.markdown(f'<div class="data-table-cell data-table-cell-left">{title}</div>', unsafe_allow_html=True)
        
        with cols[3]:
            # Publication Year 표시
            pub_year = row_data.get('Publication Year', '')
            if pd.isna(pub_year) or pub_year == '':
                pub_year = '-'
            else:
                pub_year = str(int(pub_year)) if isinstance(pub_year, (int, float)) else str(pub_year)
            st.markdown(f'<div class="data-table-cell">{pub_year}</div>', unsafe_allow_html=True)
        
        # 하이브리드 파일인 경우 최종 결과 표시
        if is_hybrid_file:
            with cols[4]:
                final_result = row_data.get('final_result', '')
                final_color = "🟢" if final_result == "include" else "🔴"
                # 규칙 결과와 최종 결과가 다르면 강조 표시
                rule_col = row_data.get('rule_result') if 'rule_result' in row_data else row_data.get('result', '')
                if rule_col != final_result:
                    st.markdown(f'<div class="data-table-cell"><strong>{final_color} {final_result}</strong></div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="data-table-cell">{final_color} {final_result}</div>', unsafe_allow_html=True)
            col_offset = 1
        else:
            col_offset = 0
        
        with cols[4 + col_offset]:
            # 검토자 결과 표시
            human_result = row_data.get('human_result', '')
            if human_result == "include":
                human_result_color = "🟢"
                human_result_text = "include"
            elif human_result == "exclude":
                human_result_color = "🔴"
                human_result_text = "exclude"
            else:
                human_result_color = "⚪"
                human_result_text = "-"
            st.markdown(f'<div class="data-table-cell">{human_result_color} {human_result_text}</div>', unsafe_allow_html=True)
        
        with cols[5 + col_offset]:
            # 검토자 표시
            reviewer = row_data.get('reviewer_name', '')
            reviewer_text = reviewer[:8] + "..." if len(reviewer) > 8 else reviewer if reviewer else "-"
            st.markdown(f'<div class="data-table-cell">{reviewer_text}</div>', unsafe_allow_html=True)
        
        with cols[6 + col_offset]:
            status = row_data.get('review_status', '미완료')
            if status == "완료" or status == "include" or status == "exclude":
                status_color = "🟢"
                status_text = "완료"
            else:
                status_color = "⚪"
                status_text = "미완료"
            st.markdown(f'<div class="data-table-cell">{status_color} {status_text}</div>', unsafe_allow_html=True)
        
        # 하이브리드 파일인 경우 변경 표시
        if is_hybrid_file:
            with cols[7 + col_offset]:
                rule_col = row_data.get('rule_result') if 'rule_result' in row_data else row_data.get('result', '')
                final_result = row_data.get('final_result', '')
                if rule_col != final_result:
                    if final_result == "include":
                        change_icon = "⬆️"  # 구제됨
                    else:
                        change_icon = "⬇️"  # 제외됨
                else:
                    change_icon = "-"
                st.markdown(f'<div class="data-table-cell">{change_icon}</div>', unsafe_allow_html=True)
    
    # 페이지 네비게이션
    if total_pages > 1:
        st.markdown("---")
        # 직접 페이지 입력 가능 (중앙 배치)
        target_page = st.number_input(
            f"페이지 (총 {total_pages}페이지)",
            min_value=1,
            max_value=total_pages,
            value=st.session_state.data_page + 1,
            step=1,
            key="page_input",
            help="±버튼 클릭하거나 숫자 입력 후 Enter로 페이지 이동"
        )
        # 페이지 변경 감지
        if target_page - 1 != st.session_state.data_page:
            st.session_state.data_page = target_page - 1
            st.rerun()
    
    # 진행률 (사이드바에서 표시하므로 중복 제거)
    
    # 검토 버튼들
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ INCLUDE", use_container_width=True):
            # INCLUDE로 설정
            st.session_state.selected_keywords = {
                'depression': {"depression"},
                'mobile': {"mobile"},
                'behavioral': {"behavioral activation"}
            }
            current_idx = st.session_state.current_idx
            st.session_state.df.at[current_idx, 'human_depression_keywords'] = 'depression'
            st.session_state.df.at[current_idx, 'human_mobile_keywords'] = 'mobile'
            st.session_state.df.at[current_idx, 'human_behavioral_keywords'] = 'behavioral activation'
            st.session_state.df.at[current_idx, 'human_result'] = 'include'
            st.session_state.df.at[current_idx, 'reviewer_name'] = st.session_state.reviewer_name
            st.session_state.df.at[current_idx, 'review_status'] = 'include'
            st.session_state.df.at[current_idx, 'review_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            st.session_state.changes_made = True
            
            # 메모리에서만 작업 (자동 저장 제거)
            
            # 다음 순서로 이동 (인덱스+1)
            if current_idx + 1 < len(st.session_state.df):
                st.session_state.current_idx = current_idx + 1
                load_current_paper_keywords()
                
                # 페이지 자동 이동 (10개 단위)
                items_per_page = 10
                new_page = st.session_state.current_idx // items_per_page
                if new_page != st.session_state.data_page:
                    st.session_state.data_page = new_page
            
            st.success("INCLUDE로 저장 완료!")
            st.rerun()
    
    with col2:
        if st.button("❌ EXCLUDE", use_container_width=True):
            # EXCLUDE로 설정
            st.session_state.selected_keywords = {
                'depression': set(),
                'mobile': set(),
                'behavioral': set()
            }
            current_idx = st.session_state.current_idx
            st.session_state.df.at[current_idx, 'human_depression_keywords'] = ''
            st.session_state.df.at[current_idx, 'human_mobile_keywords'] = ''
            st.session_state.df.at[current_idx, 'human_behavioral_keywords'] = ''
            st.session_state.df.at[current_idx, 'human_result'] = 'exclude'
            st.session_state.df.at[current_idx, 'reviewer_name'] = st.session_state.reviewer_name
            st.session_state.df.at[current_idx, 'review_status'] = 'exclude'
            st.session_state.df.at[current_idx, 'review_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            st.session_state.changes_made = True
            
            # 메모리에서만 작업 (자동 저장 제거)
            
            # 다음 순서로 이동 (인덱스+1)
            if current_idx + 1 < len(st.session_state.df):
                st.session_state.current_idx = current_idx + 1
                load_current_paper_keywords()
                
                # 페이지 자동 이동 (10개 단위)
                items_per_page = 10
                new_page = st.session_state.current_idx // items_per_page
                if new_page != st.session_state.data_page:
                    st.session_state.data_page = new_page
            
            st.success("EXCLUDE로 저장 완료!")
            st.rerun()
    
    # 재설정 버튼
    if st.button("🔄 재설정", use_container_width=True, help="현재 논문의 검토 상태를 미완료로 되돌립니다"):
        current_idx = st.session_state.current_idx
        st.session_state.df.at[current_idx, 'human_depression_keywords'] = ''
        st.session_state.df.at[current_idx, 'human_mobile_keywords'] = ''
        st.session_state.df.at[current_idx, 'human_behavioral_keywords'] = ''
        st.session_state.df.at[current_idx, 'human_result'] = ''
        st.session_state.df.at[current_idx, 'review_status'] = '미완료'
        st.session_state.df.at[current_idx, 'review_date'] = None
        st.session_state.changes_made = True
        
        # 키워드도 재설정
        load_current_paper_keywords()
        
        # 메모리에서만 작업 (자동 저장 제거)
        
        st.success("재설정 완료!")
        st.rerun()

def render_main_content():
    """메인 컨텐츠 렌더링"""
    idx = st.session_state.current_idx
    row = st.session_state.df.iloc[idx]
    
    
    # 하이브리드 파일인지 확인
    is_hybrid = 'final_result' in row and pd.notna(row.get('final_result'))
    
    # 논문 정보와 결과 헤더
    if is_hybrid:
        col_title, col_rule, col_llm, col_final = st.columns([2, 1, 1, 1])
        with col_title:
            st.markdown(f"## 📄 논문 #{idx + 1}")
        with col_rule:
            rule_result = row.get('rule_result', '')
            rule_color = "#28a745" if rule_result == 'include' else "#dc3545"
            st.markdown(f"""
            <div style="padding: 6px 12px; background-color: {rule_color}; color: white; border-radius: 15px; text-align: center; font-weight: bold; font-size: 0.8em;">
                규칙: {rule_result}
            </div>
            """, unsafe_allow_html=True)
        with col_llm:
            llm_result = row.get('llm_result', 'not_processed')
            if llm_result == 'not_processed':
                llm_color = "#6c757d"
                llm_text = "처리안됨"
            else:
                llm_color = "#28a745" if llm_result == 'include' else "#dc3545"
                llm_text = llm_result
            st.markdown(f"""
            <div style="padding: 6px 12px; background-color: {llm_color}; color: white; border-radius: 15px; text-align: center; font-weight: bold; font-size: 0.8em;">
                LLM: {llm_text}
            </div>
            """, unsafe_allow_html=True)
        with col_final:
            final_result = row.get('final_result', row.get('result', ''))
            final_color = "#28a745" if final_result == 'include' else "#dc3545"
            st.markdown(f"""
            <div style="padding: 6px 12px; background-color: {final_color}; color: white; border-radius: 15px; text-align: center; font-weight: bold; font-size: 0.8em;">
                최종: {final_result}
            </div>
            """, unsafe_allow_html=True)
    else:
        col_title, col_result = st.columns([3, 1])
        with col_title:
            st.markdown(f"## 📄 논문 #{idx + 1}")
        with col_result:
            result_color = "#28a745" if row.get('result', '') == 'include' else "#dc3545"
            st.markdown(f"""
            <div style="padding: 8px 16px; background-color: {result_color}; color: white; border-radius: 20px; text-align: center; font-weight: bold; margin-top: 10px;">
                {row.get('result', '')}
            </div>
            """, unsafe_allow_html=True)
    
    # 제목과 기본 정보
    st.markdown(f"### 제목: {row.get('Title', '')}")
    # DOI 링크
    if row.get('DOI'):
        doi = str(row.get('DOI', ''))
        if doi.startswith('http'):
            st.markdown(f"**DOI:** [{doi}]({doi})")
        else:
            st.markdown(f"**DOI:** [https://doi.org/{doi}](https://doi.org/{doi})")
    
    st.divider()
    
    # 하이브리드 결과인 경우 LLM 분석 정보 표시
    if is_hybrid and row.get('llm_result') not in ['not_processed', None, '']:
        with st.expander("🤖 LLM 분석 결과", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**LLM 키워드:**")
                st.markdown(f"- 우울증: `{row.get('llm_depression_keywords', '')}`")
                st.markdown(f"- 모바일/디지털: `{row.get('llm_mobile_keywords', '')}`")
                st.markdown(f"- 행동치료: `{row.get('llm_behavioral_keywords', '')}`")
                
            with col2:
                st.markdown("**LLM 판단 이유:**")
                llm_reason = row.get('llm_reason', '')
                if llm_reason:
                    st.markdown(f"*{llm_reason}*")
                else:
                    st.markdown("*이유가 기록되지 않음*")
            
            # LLM 하이라이트 정보 (있는 경우)
            highlights = []
            if row.get('llm_depression_highlight'):
                highlights.append(f"**우울증:** {row.get('llm_depression_highlight')}")
            if row.get('llm_mobile_highlight'):
                highlights.append(f"**모바일:** {row.get('llm_mobile_highlight')}")
            if row.get('llm_behavioral_highlight'):
                highlights.append(f"**행동치료:** {row.get('llm_behavioral_highlight')}")
            
            if highlights:
                st.markdown("**LLM이 발견한 문장들:**")
                for highlight in highlights:
                    st.markdown(f"- {highlight}")
    
    # 제목과 초록을 함께 하이라이트
    title = str(row.get('Title', ''))
    abstract = str(row.get('Abstract', ''))
    full_text = f"{title}\n\n{abstract}"

    # 포함 기준 키워드 표시 (interactive segmented controls)
    with st.expander("🎯 포함 기준 키워드", expanded=False):
        st.markdown("### 활성화된 키워드 기준")
        
        # 우울증 키워드
        depression_options = ["depression", "depressive symptoms", "depressive disorder"]
        # options에 포함된 것만 default로 사용
        current_depression = st.session_state.selected_keywords.get('depression', set())
        valid_depression_defaults = [k for k in depression_options if k in current_depression]
        selected_depression = st.segmented_control(
            "우울증 키워드", depression_options, selection_mode="multi",
            default=valid_depression_defaults,
            key=f"depression_control_{idx}"
        )
        # 변경사항이 있으면 즉시 업데이트하고 리렌더링
        new_depression_set = set(selected_depression) if selected_depression else set()
        if new_depression_set != st.session_state.selected_keywords.get('depression', set()):
            st.session_state.selected_keywords['depression'] = new_depression_set
            st.rerun()
        
        # 모바일/디지털 키워드
        mobile_options = ["mobile application", "smartphone application", "mobile", "smartphone", "iphone", "android", "app", "digital", "digital therapeutic", "mhealth"]
        # options에 포함된 것만 default로 사용
        current_mobile = st.session_state.selected_keywords.get('mobile', set())
        valid_mobile_defaults = [k for k in mobile_options if k in current_mobile]
        selected_mobile = st.segmented_control(
            "모바일/디지털 키워드", mobile_options, selection_mode="multi",
            default=valid_mobile_defaults,
            key=f"mobile_control_{idx}"
        )
        # 변경사항이 있으면 즉시 업데이트하고 리렌더링
        new_mobile_set = set(selected_mobile) if selected_mobile else set()
        if new_mobile_set != st.session_state.selected_keywords.get('mobile', set()):
            st.session_state.selected_keywords['mobile'] = new_mobile_set
            st.rerun()
        
        # 행동활성화/치료 키워드
        behavioral_options = ["behavioral activation", "behavioural activation", "activity schedul*", "behavio* interven*", "behavio* therap*"]
        # options에 포함된 것만 default로 사용
        current_behavioral = st.session_state.selected_keywords.get('behavioral', set())
        valid_behavioral_defaults = [k for k in behavioral_options if k in current_behavioral]
        selected_behavioral = st.segmented_control(
            "행동활성화/치료 키워드", behavioral_options, selection_mode="multi",
            default=valid_behavioral_defaults,
            key=f"behavioral_control_{idx}"
        )
        # 변경사항이 있으면 즉시 업데이트하고 리렌더링
        new_behavioral_set = set(selected_behavioral) if selected_behavioral else set()
        if new_behavioral_set != st.session_state.selected_keywords.get('behavioral', set()):
            st.session_state.selected_keywords['behavioral'] = new_behavioral_set
            st.rerun()

    
    # 선택된 키워드로 하이라이트된 전체 텍스트
    highlighted_text = highlight_all_keywords(full_text, st.session_state.selected_keywords)
    
    with st.expander("📝 제목 + 초록 (키워드 하이라이트)", expanded=True):
        st.markdown(
            f'<div class="paper-card">{highlighted_text}</div>',
            unsafe_allow_html=True
        )
    

# 사이드바 렌더링
render_sidebar()

# 메인 컨텐츠
if st.session_state.df is not None:
    col_left, col_right = st.columns([0.45, 0.55], gap="large")
    
    with col_left:
        render_data_navigation()
    
    with col_right:
        render_main_content()
else:
    st.info("👈 왼쪽 사이드바에서 CSV 파일을 선택하여 시작하세요.")