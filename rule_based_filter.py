#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
규칙 기반 키워드 필터링 시스템

기존 LLM 결과와 비교하기 위한 규칙 기반 키워드 매칭
"""

import pandas as pd
import re
from typing import List, Dict, Tuple, Set
import os
from datetime import datetime

class RuleBasedKeywordFilter:
    def __init__(self):
        """규칙 기반 키워드 필터 초기화"""
        # 템플릿에 따른 정확한 키워드 목록
        self.depression_keywords = [
            "depression",
            "depressive symptoms", 
            "depressive disorder"
        ]
        
        self.mobile_keywords = [
            "mobile application",
            "smartphone application", 
            "mobile",
            "smartphone",
            "iphone",
            "android",
            "app",
            "digital",
            "digital therapeutic",
            "digital therapeutics",  # 복수형 추가
            "mhealth"
        ]
        
        # 행동활성화/치료 키워드 (와일드카드 패턴 포함)
        self.behavioral_base_keywords = [
            "behavioral activation",
            "behavioural activation"
        ]
        
        # 와일드카드 패턴들
        self.behavioral_patterns = [
            r"\bactivity schedul\w*",  # activity schedule*
            r"\bbehavio\w*\s+interven\w*",  # behavio* interven*
            r"\bbehavio\w*\s+therap\w*"  # behavio* therap*
        ]
    
    def find_keywords_in_text(self, text: str, keywords: List[str]) -> Tuple[List[str], List[str]]:
        """텍스트에서 일반 키워드 찾기 (정확한 단어 매칭)"""
        if not text or pd.isna(text):
            return [], []
        
        text_lower = str(text).lower()
        found_keywords = []
        found_sentences = []
        
        # 문장 단위로 분리
        sentences = re.split(r'[.!?]+', text)
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            
            # 단어 경계를 고려한 매칭
            if len(keyword.split()) == 1:
                # 단일 단어의 경우 단어 경계 확인
                pattern = r'\b' + re.escape(keyword_lower) + r'\b'
                if re.search(pattern, text_lower):
                    found_keywords.append(keyword)
                    # 키워드가 포함된 문장 찾기
                    for sentence in sentences:
                        if re.search(pattern, sentence.lower()):
                            found_sentences.append(sentence.strip())
                            break
            else:
                # 구문의 경우 전체 매칭
                if keyword_lower in text_lower:
                    found_keywords.append(keyword)
                    # 키워드가 포함된 문장 찾기
                    for sentence in sentences:
                        if keyword_lower in sentence.lower():
                            found_sentences.append(sentence.strip())
                            break
        
        return found_keywords, found_sentences
    
    def find_behavioral_keywords_in_text(self, text: str) -> Tuple[List[str], List[str]]:
        """행동활성화/치료 키워드 찾기 (와일드카드 패턴 포함)"""
        if not text or pd.isna(text):
            return [], []
        
        text_lower = str(text).lower()
        found_keywords = []
        found_sentences = []
        
        # 문장 단위로 분리
        sentences = re.split(r'[.!?]+', text)
        
        # 1. 기본 키워드 검색
        base_found, base_sentences = self.find_keywords_in_text(text, self.behavioral_base_keywords)
        found_keywords.extend(base_found)
        found_sentences.extend(base_sentences)
        
        # 2. 와일드카드 패턴 검색
        for pattern in self.behavioral_patterns:
            matches = re.finditer(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                matched_text = match.group(0)
                if matched_text not in [k.lower() for k in found_keywords]:
                    found_keywords.append(matched_text)
                    
                    # 매칭된 텍스트가 포함된 문장 찾기
                    for sentence in sentences:
                        if matched_text in sentence.lower():
                            found_sentences.append(sentence.strip())
                            break
        
        return found_keywords, found_sentences
    
    def evaluate_single_paper(self, title: str, abstract: str) -> Dict:
        """단일 논문 평가"""
        # 제목과 초록 결합
        full_text = f"{title} {abstract}"
        
        # 각 카테고리별 키워드 검색
        depression_found, depression_sentences = self.find_keywords_in_text(full_text, self.depression_keywords)
        mobile_found, mobile_sentences = self.find_keywords_in_text(full_text, self.mobile_keywords)  
        behavioral_found, behavioral_sentences = self.find_behavioral_keywords_in_text(full_text)
        
        # 포함/제외 결정
        has_depression = len(depression_found) > 0
        has_mobile = len(mobile_found) > 0
        has_behavioral = len(behavioral_found) > 0
        
        result = "include" if (has_depression and has_mobile and has_behavioral) else "exclude"
        
        # 이유 생성
        missing_categories = []
        if not has_depression:
            missing_categories.append("우울증")
        if not has_mobile:
            missing_categories.append("모바일/디지털")
        if not has_behavioral:
            missing_categories.append("행동활성화/치료")
        
        if missing_categories:
            reason = f"다음 카테고리에서 키워드가 발견되지 않음: {', '.join(missing_categories)}"
        else:
            reason = "모든 카테고리에서 키워드 발견됨"
        
        return {
            'depression_keywords': ', '.join(depression_found),
            'mobile_keywords': ', '.join(mobile_found),
            'behavioral_keywords': ', '.join(behavioral_found),
            'result': result
        }
    
    def process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """DataFrame 전체 처리"""
        results = []
        
        for idx, row in df.iterrows():
            title = str(row.get('Title', ''))
            abstract = str(row.get('Abstract', ''))
            
            if title == 'nan':
                title = ''
            if abstract == 'nan':
                abstract = ''
            
            if not title and not abstract:
                # 제목과 초록이 모두 없는 경우
                result = {
                    'DOI': row.get('DOI', ''),
                    'Title': title,
                    'Authors': row.get('Authors', ''),
                    'Journal/Book': row.get('Journal/Book', ''),
                    'Publication Year': row.get('Publication Year', ''),
                    'Abstract': abstract,
                    'depression_keywords': '',
                    'mobile_keywords': '',
                    'behavioral_keywords': '',
                    'result': 'exclude'
                }
            else:
                # 키워드 매칭 수행
                rule_result = self.evaluate_single_paper(title, abstract)
                
                # 원본 데이터와 결과 병합
                result = {
                    'DOI': row.get('DOI', ''),
                    'Title': title,
                    'Authors': row.get('Authors', ''),
                    'Journal/Book': row.get('Journal/Book', ''),
                    'Publication Year': row.get('Publication Year', ''),
                    'Abstract': abstract,
                    'depression_keywords': rule_result['depression_keywords'],
                    'mobile_keywords': rule_result['mobile_keywords'],
                    'behavioral_keywords': rule_result['behavioral_keywords'],
                    'result': rule_result['result']
                }
            
            results.append(result)
            print(f"처리 완료 {idx+1}/{len(df)}: {title[:50]}... -> {result['result']}")
        
        return pd.DataFrame(results)

def compare_results(llm_df: pd.DataFrame, rule_df: pd.DataFrame) -> Dict:
    """LLM과 규칙 기반 결과 비교"""
    total_papers = len(llm_df)
    
    # 결과 일치도 비교
    result_matches = 0
    keyword_matches = {'depression': 0, 'mobile': 0, 'behavioral': 0}
    
    detailed_comparison = []
    
    for idx in range(total_papers):
        llm_row = llm_df.iloc[idx]
        rule_row = rule_df.iloc[idx]
        
        # 결과 일치 확인
        llm_result = llm_row.get('result', '').lower()
        rule_result = rule_row.get('result', '').lower()
        
        result_match = llm_result == rule_result
        if result_match:
            result_matches += 1
        
        # 키워드 일치도 확인 (간단한 비교)
        for category in ['depression', 'mobile', 'behavioral']:
            llm_keywords = str(llm_row.get(f'{category}_keywords', '')).lower()
            rule_keywords = str(rule_row.get(f'{category}_keywords', '')).lower()
            
            # 빈 문자열 처리
            if not llm_keywords and not rule_keywords:
                keyword_matches[category] += 1
            elif llm_keywords and rule_keywords:
                # 둘 다 키워드가 있는 경우 - 간단한 포함 관계 확인
                llm_set = set(k.strip() for k in llm_keywords.split(',') if k.strip())
                rule_set = set(k.strip() for k in rule_keywords.split(',') if k.strip())
                if llm_set & rule_set:  # 교집합이 있으면 부분 일치로 간주
                    keyword_matches[category] += 1
        
        detailed_comparison.append({
            'index': idx,
            'title': llm_row.get('Title', '')[:50],
            'llm_result': llm_result,
            'rule_result': rule_result,
            'result_match': result_match,
            'llm_depression': llm_row.get('depression_keywords', ''),
            'rule_depression': rule_row.get('depression_keywords', ''),
            'llm_mobile': llm_row.get('mobile_keywords', ''),
            'rule_mobile': rule_row.get('mobile_keywords', ''),
            'llm_behavioral': llm_row.get('behavioral_keywords', ''),
            'rule_behavioral': rule_row.get('behavioral_keywords', '')
        })
    
    comparison_stats = {
        'total_papers': total_papers,
        'result_matches': result_matches,
        'result_accuracy': result_matches / total_papers * 100,
        'keyword_accuracy': {
            'depression': keyword_matches['depression'] / total_papers * 100,
            'mobile': keyword_matches['mobile'] / total_papers * 100,
            'behavioral': keyword_matches['behavioral'] / total_papers * 100
        },
        'detailed_comparison': detailed_comparison
    }
    
    return comparison_stats

def main():
    """메인 실행 함수"""
    # 입력 파일
    input_file = "data/meta_article_data.csv"
    
    # 출력 파일
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    rule_output = f"rule_base_output/rule_based_results_{timestamp}.csv"
    comparison_output = f"rule_base_output/comparison_results_{timestamp}.csv"
    
    # 출력 디렉토리 생성
    os.makedirs("rule_base_output", exist_ok=True)
    
    try:
        # 원본 데이터 로드
        print(f"데이터 로드: {input_file}")
        df = pd.read_csv(input_file, encoding='utf-8-sig')
        print(f"{len(df)}개 논문 로드 완료")
        
        # 규칙 기반 필터링 실행
        print("\n규칙 기반 필터링 시작...")
        filter_system = RuleBasedKeywordFilter()
        rule_results = filter_system.process_dataframe(df)
        
        # 규칙 기반 결과 저장
        rule_results.to_csv(rule_output, index=False, encoding='utf-8-sig')
        print(f"규칙 기반 결과 저장: {rule_output}")
        
        # 요약 통계
        include_count = sum(1 for _, row in rule_results.iterrows() if row['result'] == 'include')
        exclude_count = len(rule_results) - include_count
        print(f"규칙 기반 결과: {include_count}개 포함, {exclude_count}개 제외")
        
        # LLM 결과와 비교 (기존 결과 파일이 있는 경우)
        llm_files = [f for f in os.listdir("output") if f.startswith("keyword_labeling_results_") and f.endswith(".csv")]
        
        if llm_files:
            # 가장 최근 LLM 결과 파일 사용
            llm_file = max(llm_files, key=lambda x: os.path.getctime(f"output/{x}"))
            llm_file_path = f"output/{llm_file}"
            
            print(f"\nLLM 결과와 비교: {llm_file_path}")
            llm_results = pd.read_csv(llm_file_path, encoding='utf-8-sig')
            
            # 비교 수행
            comparison = compare_results(llm_results, rule_results)
            
            # 비교 결과 출력
            print(f"\n=== 비교 결과 ===")
            print(f"전체 논문 수: {comparison['total_papers']}")
            print(f"결과 일치도: {comparison['result_matches']}/{comparison['total_papers']} ({comparison['result_accuracy']:.1f}%)")
            print(f"키워드 일치도:")
            print(f"  - 우울증: {comparison['keyword_accuracy']['depression']:.1f}%")
            print(f"  - 모바일/디지털: {comparison['keyword_accuracy']['mobile']:.1f}%")
            print(f"  - 행동활성화/치료: {comparison['keyword_accuracy']['behavioral']:.1f}%")
            
            # 상세 비교 결과 저장
            comparison_df = pd.DataFrame(comparison['detailed_comparison'])
            comparison_df.to_csv(comparison_output, index=False, encoding='utf-8-sig')
            print(f"상세 비교 결과 저장: {comparison_output}")
            
            # 불일치 사례 출력
            mismatches = [item for item in comparison['detailed_comparison'] if not item['result_match']]
            if mismatches:
                print(f"\n=== 불일치 사례 ({len(mismatches)}개) ===")
                for mismatch in mismatches[:5]:  # 처음 5개만 출력
                    print(f"#{mismatch['index']+1}: {mismatch['title']}...")
                    print(f"  LLM: {mismatch['llm_result']} vs 규칙: {mismatch['rule_result']}")
        else:
            print("\nLLM 결과 파일을 찾을 수 없어 비교를 수행하지 않습니다.")
        
        print("\n규칙 기반 필터링 완료!")
        
    except Exception as e:
        print(f"오류 발생: {e}")
        raise

if __name__ == "__main__":
    main()