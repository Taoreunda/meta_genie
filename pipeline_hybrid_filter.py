#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
하이브리드 키워드 필터링 파이프라인

규칙 기반 필터링과 LLM 기반 2차 검토를 결합한 통합 파이프라인
"""

import pandas as pd
import logging
import os
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path

from rule_based_filter import RuleBasedKeywordFilter
from llm_secondary_filter import LLMSecondaryFilter

class HybridFilterPipeline:
    def __init__(self, llm_model: str = "gpt-4o", debug: bool = False):
        """
        하이브리드 필터 파이프라인 초기화
        
        Args:
            llm_model: LLM 모델명
            debug: 디버그 모드 활성화
        """
        self.llm_model = llm_model
        self.debug = debug
        
        # 로그 설정
        os.makedirs("logs", exist_ok=True)
        log_filename = f"logs/hybrid_pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        self.logger = logging.getLogger(f"{__name__}_{id(self)}")
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.FileHandler(log_filename, encoding='utf-8')
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        # 필터 시스템 초기화
        self.rule_filter = RuleBasedKeywordFilter()
        self.llm_filter = LLMSecondaryFilter(model_name=llm_model, debug=debug)
        
        self.logger.info(f"HybridFilterPipeline 초기화 완료 - LLM 모델: {llm_model}")
    
    def run_pipeline(self, input_file: str, output_dir: str = "output") -> Dict:
        """
        하이브리드 필터링 파이프라인 실행
        
        Args:
            input_file: 입력 CSV 파일 경로
            output_dir: 출력 디렉토리
            
        Returns:
            결과 요약 딕셔너리
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 출력 디렉토리 생성
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs("rule_base_output", exist_ok=True)
        
        # 파일 경로 설정
        rule_output = f"rule_base_output/hybrid_rule_results_{timestamp}.csv"
        final_output = f"{output_dir}/hybrid_final_results_{timestamp}.csv"
        
        try:
            self.logger.info("=== 하이브리드 필터링 파이프라인 시작 ===")
            
            # 1단계: 원본 데이터 로드
            self.logger.info(f"1단계: 데이터 로드 - {input_file}")
            df = pd.read_csv(input_file, encoding='utf-8-sig')
            self.logger.info(f"총 {len(df)}개 논문 로드 완료")
            
            # 2단계: 규칙 기반 필터링
            self.logger.info("2단계: 규칙 기반 필터링 시작")
            rule_results = self.rule_filter.process_dataframe(df)
            rule_results.to_csv(rule_output, index=False, encoding='utf-8-sig')
            
            # 규칙 기반 결과 요약
            rule_include = sum(1 for _, row in rule_results.iterrows() if row['result'] == 'include')
            rule_exclude = len(rule_results) - rule_include
            
            self.logger.info(f"규칙 기반 결과: {rule_include}개 포함, {rule_exclude}개 제외")
            self.logger.info(f"규칙 기반 결과 저장: {rule_output}")
            
            # 3단계: LLM 2차 검토 (exclude된 논문들만)
            self.logger.info("3단계: LLM 2차 검토 시작")
            final_results = self.llm_filter.process_exclude_papers(rule_output, final_output)
            
            # 최종 결과 요약
            final_include = sum(1 for _, row in final_results.iterrows() if row['final_result'] == 'include')
            final_exclude = len(final_results) - final_include
            
            # LLM에 의해 include로 변경된 논문 수
            llm_rescued = sum(1 for _, row in final_results.iterrows() 
                            if row['rule_result'] == 'exclude' and row['final_result'] == 'include')
            
            self.logger.info(f"최종 결과: {final_include}개 포함, {final_exclude}개 제외")
            self.logger.info(f"LLM 2차 검토로 구제된 논문: {llm_rescued}개")
            self.logger.info(f"최종 결과 저장: {final_output}")
            
            # 4단계: 결과 분석 및 요약
            pipeline_summary = self._generate_pipeline_summary(
                rule_results, final_results, rule_include, rule_exclude, 
                final_include, final_exclude, llm_rescued
            )
            
            # 요약 저장
            summary_output = f"{output_dir}/hybrid_pipeline_summary_{timestamp}.json"
            import json
            with open(summary_output, 'w', encoding='utf-8') as f:
                json.dump(pipeline_summary, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"파이프라인 요약 저장: {summary_output}")
            self.logger.info("=== 하이브리드 필터링 파이프라인 완료 ===")
            
            return {
                'rule_output_file': rule_output,
                'final_output_file': final_output,
                'summary_file': summary_output,
                'pipeline_summary': pipeline_summary
            }
            
        except Exception as e:
            self.logger.error(f"파이프라인 실행 중 오류: {e}")
            raise
    
    def _generate_pipeline_summary(self, rule_results: pd.DataFrame, 
                                 final_results: pd.DataFrame,
                                 rule_include: int, rule_exclude: int,
                                 final_include: int, final_exclude: int,
                                 llm_rescued: int) -> Dict:
        """파이프라인 실행 요약 생성"""
        
        # LLM 검토 대상 논문들의 상세 분석
        llm_processed = final_results[final_results['rule_result'] == 'exclude']
        llm_include_papers = llm_processed[llm_processed['final_result'] == 'include']
        
        # 구제된 논문들의 키워드 분석
        rescued_keywords = {
            'depression': [],
            'mobile': [],
            'behavioral': []
        }
        
        for _, row in llm_include_papers.iterrows():
            if row['llm_depression_keywords']:
                rescued_keywords['depression'].extend(
                    [k.strip() for k in str(row['llm_depression_keywords']).split(',') if k.strip()]
                )
            if row['llm_mobile_keywords']:
                rescued_keywords['mobile'].extend(
                    [k.strip() for k in str(row['llm_mobile_keywords']).split(',') if k.strip()]
                )
            if row['llm_behavioral_keywords']:
                rescued_keywords['behavioral'].extend(
                    [k.strip() for k in str(row['llm_behavioral_keywords']).split(',') if k.strip()]
                )
        
        # 고유 키워드 집계
        for category in rescued_keywords:
            rescued_keywords[category] = list(set(rescued_keywords[category]))
        
        summary = {
            'pipeline_info': {
                'execution_time': datetime.now().isoformat(),
                'total_papers': len(rule_results),
                'llm_model': self.llm_model
            },
            'rule_based_results': {
                'include_count': rule_include,
                'exclude_count': rule_exclude,
                'include_rate': round(rule_include / len(rule_results) * 100, 2)
            },
            'llm_secondary_results': {
                'processed_count': len(llm_processed),
                'rescued_count': llm_rescued,
                'rescue_rate': round(llm_rescued / len(llm_processed) * 100, 2) if len(llm_processed) > 0 else 0
            },
            'final_results': {
                'include_count': final_include,
                'exclude_count': final_exclude,
                'include_rate': round(final_include / len(final_results) * 100, 2),
                'improvement_over_rule_based': round((final_include - rule_include) / len(rule_results) * 100, 2)
            },
            'rescued_papers_analysis': {
                'count': llm_rescued,
                'unique_keywords': rescued_keywords,
                'keyword_counts': {
                    'depression': len(rescued_keywords['depression']),
                    'mobile': len(rescued_keywords['mobile']),
                    'behavioral': len(rescued_keywords['behavioral'])
                }
            }
        }
        
        return summary
    
    def generate_comparison_report(self, results_file: str, output_dir: str = "output") -> str:
        """비교 분석 리포트 생성"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f"{output_dir}/hybrid_comparison_report_{timestamp}.md"
        
        # 결과 데이터 로드
        df = pd.read_csv(results_file, encoding='utf-8-sig')
        
        # 분석 수행
        total_papers = len(df)
        rule_include = sum(1 for _, row in df.iterrows() if row['rule_result'] == 'include')
        final_include = sum(1 for _, row in df.iterrows() if row['final_result'] == 'include')
        llm_rescued = sum(1 for _, row in df.iterrows() 
                         if row['rule_result'] == 'exclude' and row['final_result'] == 'include')
        
        # 구제된 논문들 분석
        rescued_papers = df[(df['rule_result'] == 'exclude') & (df['final_result'] == 'include')]
        
        # 리포트 작성
        report_content = f"""# 하이브리드 키워드 필터링 비교 분석 리포트

## 실행 정보
- 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 전체 논문 수: {total_papers}개
- LLM 모델: {self.llm_model}

## 필터링 결과 비교

### 규칙 기반 필터링 결과
- 포함: {rule_include}개 ({rule_include/total_papers*100:.1f}%)
- 제외: {total_papers-rule_include}개 ({(total_papers-rule_include)/total_papers*100:.1f}%)

### 하이브리드 필터링 최종 결과
- 포함: {final_include}개 ({final_include/total_papers*100:.1f}%)
- 제외: {total_papers-final_include}개 ({(total_papers-final_include)/total_papers*100:.1f}%)

### LLM 2차 검토 효과
- 구제된 논문: {llm_rescued}개
- 구제율: {llm_rescued/(total_papers-rule_include)*100:.1f}% (제외된 논문 중)
- 전체 개선도: {(final_include-rule_include)/total_papers*100:.1f}%

## 구제된 논문 분석

### 구제된 논문 수: {len(rescued_papers)}개

"""
        
        if len(rescued_papers) > 0:
            report_content += "### 구제된 논문 예시\n\n"
            for idx, (_, row) in enumerate(rescued_papers.head(5).iterrows()):
                report_content += f"**{idx+1}. {row['Title'][:100]}...**\n"
                report_content += f"- LLM 우울증 키워드: {row['llm_depression_keywords']}\n"
                report_content += f"- LLM 모바일 키워드: {row['llm_mobile_keywords']}\n"
                report_content += f"- LLM 행동치료 키워드: {row['llm_behavioral_keywords']}\n"
                report_content += f"- LLM 판단 이유: {row['llm_reason']}\n\n"
        
        report_content += f"""
## 결론

하이브리드 접근법을 통해 총 {llm_rescued}개의 논문이 추가로 포함되었습니다.
이는 전체 논문의 {(final_include-rule_include)/total_papers*100:.1f}%에 해당하며,
규칙 기반 필터링만으로는 놓칠 수 있는 중요한 연구들을 식별했습니다.

생성 시간: {datetime.now().isoformat()}
"""
        
        # 리포트 저장
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        self.logger.info(f"비교 분석 리포트 생성: {report_file}")
        return report_file

def main():
    """메인 실행 함수"""
    # 설정
    input_file = "data/meta_article_data.csv"
    output_dir = "output"
    
    try:
        # 파이프라인 실행
        pipeline = HybridFilterPipeline(llm_model="gpt-4o", debug=True)
        results = pipeline.run_pipeline(input_file, output_dir)
        
        # 비교 분석 리포트 생성
        report_file = pipeline.generate_comparison_report(
            results['final_output_file'], output_dir
        )
        
        print(f"\n=== 하이브리드 필터링 완료 ===")
        print(f"최종 결과: {results['final_output_file']}")
        print(f"요약 파일: {results['summary_file']}")
        print(f"분석 리포트: {report_file}")
        
    except Exception as e:
        print(f"파이프라인 실행 중 오류: {e}")
        raise

if __name__ == "__main__":
    main()