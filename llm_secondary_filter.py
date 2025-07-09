#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 기반 2차 키워드 필터링 시스템

규칙 기반 필터링에서 exclude된 논문들을 LLM으로 재검토하여
잠재적 포함 대상을 식별하는 시스템
"""

import pandas as pd
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

# 환경변수 로드
load_dotenv()

# UTF-8 인코딩 설정
import sys
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

class LLMKeywordResult(BaseModel):
    """LLM 키워드 분석 결과 모델"""
    depression_keywords: str = Field(description="발견된 우울증 관련 키워드들 (쉼표로 구분)")
    mobile_keywords: str = Field(description="발견된 모바일/디지털 관련 키워드들 (쉼표로 구분)")
    behavioral_keywords: str = Field(description="발견된 행동활성화/치료 관련 키워드들 (쉼표로 구분)")
    result: str = Field(description="포함/제외 결정 (include 또는 exclude)")
    depression_highlight: str = Field(description="우울증 키워드가 발견된 원문 문장들")
    mobile_highlight: str = Field(description="모바일/디지털 키워드가 발견된 원문 문장들")
    behavioral_highlight: str = Field(description="행동활성화/치료 키워드가 발견된 원문 문장들")
    reason: str = Field(description="포함/제외 판단의 구체적인 이유 (한글로 작성)")

class LLMSecondaryFilter:
    def __init__(self, model_name: str = "gpt-4o", debug: bool = False):
        """
        LLM 2차 필터 초기화
        
        Args:
            model_name: 사용할 OpenAI 모델명
            debug: 디버그 모드 활성화
        """
        self.model_name = model_name
        self.debug = debug
        
        # 로그 폴더 및 파일 설정
        os.makedirs("logs", exist_ok=True)
        log_filename = f"logs/llm_secondary_filter_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        # 로깅 설정
        self.logger = logging.getLogger(f"{__name__}_{id(self)}")
        self.logger.setLevel(logging.INFO)
        
        # 핸들러가 중복 추가되지 않도록 확인
        if not self.logger.handlers:
            handler = logging.FileHandler(log_filename, encoding='utf-8')
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            
            # 콘솔 출력도 추가
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        # LangChain LLM 초기화
        self.llm = ChatOpenAI(
            model_name=model_name,
            temperature=0.0
        )
        
        # 출력 파서 초기화
        self.parser = PydanticOutputParser(pydantic_object=LLMKeywordResult)
        
        # 템플릿 로드 및 프롬프트 초기화
        self.template = self._load_template()
        self.prompt = self._create_prompt_template()
        
        self.logger.info(f"LLMSecondaryFilter 초기화 완료 - 모델: {model_name}")
    
    def _load_template(self) -> str:
        """템플릿 파일 로드"""
        template_path = Path("templates/keyword_template_en.md")
        
        if not template_path.exists():
            raise FileNotFoundError(f"템플릿 파일을 찾을 수 없습니다: {template_path}")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # 2차 필터용 추가 지시사항
        additional_instructions = """

## 2차 검토 추가 지시사항

**중요**: 이 논문은 이미 규칙 기반 필터링에서 제외되었으나, LLM의 유연한 해석으로 재검토되고 있습니다.

### 기존 규칙 기반 결과 참고사항
- 기존 우울증 키워드: {existing_depression_keywords}
- 기존 모바일/디지털 키워드: {existing_mobile_keywords}  
- 기존 행동활성화/치료 키워드: {existing_behavioral_keywords}

### 2차 검토 시 고려사항
1. **유연한 해석**: 규칙 기반에서 놓친 동의어, 관련 용어, 맥락적 의미를 고려
2. **의도 파악**: 연구의 전체적 맥락과 목적을 고려하여 판단
3. **보수적 접근**: 확실하지 않은 경우 exclude로 판단
4. **근거 제시**: 판단 이유를 명확히 한글로 기술

**재검토 목표**: 규칙 기반에서 제외되었지만 실제로는 포함되어야 할 중요한 연구를 찾아내기
"""
        
        return template_content + additional_instructions
    
    def _create_prompt_template(self) -> PromptTemplate:
        """프롬프트 템플릿 생성"""
        return PromptTemplate(
            template=self.template,
            input_variables=[
                "title", "abstract", 
                "existing_depression_keywords", 
                "existing_mobile_keywords", 
                "existing_behavioral_keywords"
            ],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
    
    def process_single_article(self, title: str, abstract: str, 
                             existing_depression: str = "",
                             existing_mobile: str = "",
                             existing_behavioral: str = "") -> Optional[Dict]:
        """단일 논문 처리"""
        try:
            if self.debug:
                self.logger.info(f"논문 2차 검토 중: {title[:50]}...")
            
            # LangChain 체인 실행
            chain = self.prompt | self.llm | self.parser
            result = chain.invoke({
                "title": title, 
                "abstract": abstract,
                "existing_depression_keywords": existing_depression,
                "existing_mobile_keywords": existing_mobile,
                "existing_behavioral_keywords": existing_behavioral
            })
            
            if self.debug:
                self.logger.info(f"LLM 원본 응답: {result}")
            
            # Pydantic 모델을 dict로 변환
            result_dict = result.dict()
            
            self.logger.info(f"2차 검토 완료: {title[:50]}... -> {result_dict.get('result', 'unknown')}")
            return result_dict
                
        except Exception as e:
            self.logger.error(f"논문 2차 검토 중 오류 발생 '{title[:50]}...': {e}")
            
            # 파싱 실패 시 직접 LLM 호출로 재시도
            try:
                formatted_prompt = self.prompt.format(
                    title=title, 
                    abstract=abstract,
                    existing_depression_keywords=existing_depression,
                    existing_mobile_keywords=existing_mobile,
                    existing_behavioral_keywords=existing_behavioral
                )
                response = self.llm.invoke([HumanMessage(content=formatted_prompt)])
                
                # JSON 응답 파싱 시도
                response_text = response.content
                result_dict = self._parse_fallback_response(response_text)
                
                if result_dict:
                    self.logger.info(f"재시도 성공: {title[:50]}... -> {result_dict.get('result', 'unknown')}")
                    return result_dict
                
            except Exception as e2:
                self.logger.error(f"재시도도 실패: {e2}")
            
            return None
    
    def _parse_fallback_response(self, response_text: str) -> Optional[Dict]:
        """응답 파싱 실패 시 백업 파싱 함수"""
        try:
            # JSON 블록 추출
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                # JSON 형태 텍스트 찾기
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                if json_start != -1 and json_end != 0:
                    json_text = response_text[json_start:json_end]
                else:
                    json_text = response_text
            
            return json.loads(json_text)
        
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.error(f"백업 파싱 실패: {e}")
            self.logger.error(f"응답 텍스트: {response_text}")
            return None
    
    def process_exclude_papers(self, input_file: str, output_file: str, 
                             checkpoint_interval: int = 5) -> pd.DataFrame:
        """exclude된 논문들만 LLM으로 재검토"""
        # 입력 데이터 로드
        self.logger.info(f"규칙 기반 결과 파일 로드: {input_file}")
        df = pd.read_csv(input_file, encoding='utf-8-sig')
        
        # exclude된 논문들만 필터링
        exclude_df = df[df['result'] == 'exclude'].copy()
        include_df = df[df['result'] == 'include'].copy()
        
        self.logger.info(f"전체 논문 수: {len(df)}")
        self.logger.info(f"기존 include 논문 수: {len(include_df)}")
        self.logger.info(f"LLM 재검토 대상(exclude) 논문 수: {len(exclude_df)}")
        
        if len(exclude_df) == 0:
            self.logger.info("재검토 대상 논문이 없습니다.")
            return df
        
        results = []
        checkpoint_path = f"{output_file}.checkpoint"
        
        # 체크포인트 로드
        start_idx = 0
        if os.path.exists(checkpoint_path):
            try:
                checkpoint_df = pd.read_csv(checkpoint_path, encoding='utf-8-sig')
                results = checkpoint_df.to_dict('records')
                start_idx = len(results)
                self.logger.info(f"체크포인트에서 재개: {start_idx}개 논문 처리 완료")
            except Exception as e:
                self.logger.warning(f"체크포인트 로드 실패: {e}")
        
        total_exclude = len(exclude_df)
        self.logger.info(f"{total_exclude - start_idx}개 논문 LLM 재검토 시작 (인덱스 {start_idx}부터)")
        
        # exclude된 논문들 처리
        for idx in range(start_idx, total_exclude):
            row = exclude_df.iloc[idx]
            title = str(row.get('Title', ''))
            abstract = str(row.get('Abstract', ''))
            
            existing_depression = str(row.get('depression_keywords', ''))
            existing_mobile = str(row.get('mobile_keywords', ''))
            existing_behavioral = str(row.get('behavioral_keywords', ''))
            
            if not title or not abstract or title == 'nan' or abstract == 'nan':
                self.logger.warning(f"제목 또는 초록 누락 - 행 {idx}")
                result = {
                    'DOI': row.get('DOI', ''),
                    'Title': title,
                    'Authors': row.get('Authors', ''),
                    'Journal/Book': row.get('Journal/Book', ''),
                    'Publication Year': row.get('Publication Year', ''),
                    'Abstract': abstract,
                    'rule_depression_keywords': existing_depression,
                    'rule_mobile_keywords': existing_mobile,
                    'rule_behavioral_keywords': existing_behavioral,
                    'rule_result': 'exclude',
                    'llm_depression_keywords': '',
                    'llm_mobile_keywords': '',
                    'llm_behavioral_keywords': '',
                    'llm_result': 'exclude',
                    'llm_depression_highlight': '',
                    'llm_mobile_highlight': '',
                    'llm_behavioral_highlight': '',
                    'llm_reason': '제목 또는 초록 누락',
                    'final_result': 'exclude'
                }
            else:
                # LLM 처리
                llm_result = self.process_single_article(
                    title, abstract, 
                    existing_depression, existing_mobile, existing_behavioral
                )
                
                if llm_result:
                    # 원본 데이터와 결과 병합
                    result = {
                        'DOI': row.get('DOI', ''),
                        'Title': title,
                        'Authors': row.get('Authors', ''),
                        'Journal/Book': row.get('Journal/Book', ''),
                        'Publication Year': row.get('Publication Year', ''),
                        'Abstract': abstract,
                        'rule_depression_keywords': existing_depression,
                        'rule_mobile_keywords': existing_mobile,
                        'rule_behavioral_keywords': existing_behavioral,
                        'rule_result': 'exclude',
                        'llm_depression_keywords': llm_result.get('depression_keywords', ''),
                        'llm_mobile_keywords': llm_result.get('mobile_keywords', ''),
                        'llm_behavioral_keywords': llm_result.get('behavioral_keywords', ''),
                        'llm_result': llm_result.get('result', 'exclude'),
                        'llm_depression_highlight': llm_result.get('depression_highlight', ''),
                        'llm_mobile_highlight': llm_result.get('mobile_highlight', ''),
                        'llm_behavioral_highlight': llm_result.get('behavioral_highlight', ''),
                        'llm_reason': llm_result.get('reason', ''),
                        'final_result': llm_result.get('result', 'exclude')
                    }
                else:
                    result = {
                        'DOI': row.get('DOI', ''),
                        'Title': title,
                        'Authors': row.get('Authors', ''),
                        'Journal/Book': row.get('Journal/Book', ''),
                        'Publication Year': row.get('Publication Year', ''),
                        'Abstract': abstract,
                        'rule_depression_keywords': existing_depression,
                        'rule_mobile_keywords': existing_mobile,
                        'rule_behavioral_keywords': existing_behavioral,
                        'rule_result': 'exclude',
                        'llm_depression_keywords': '',
                        'llm_mobile_keywords': '',
                        'llm_behavioral_keywords': '',
                        'llm_result': 'exclude',
                        'llm_depression_highlight': '',
                        'llm_mobile_highlight': '',
                        'llm_behavioral_highlight': '',
                        'llm_reason': 'LLM 처리 실패',
                        'final_result': 'exclude'
                    }
            
            results.append(result)
            
            # 체크포인트 저장
            if (idx + 1) % checkpoint_interval == 0:
                checkpoint_df = pd.DataFrame(results)
                checkpoint_df.to_csv(checkpoint_path, index=False, encoding='utf-8-sig')
                self.logger.info(f"체크포인트 저장: {idx + 1}/{total_exclude}개 논문 처리 완료")
        
        # 처리된 exclude 논문들과 기존 include 논문들 병합
        exclude_results_df = pd.DataFrame(results)
        
        # include 논문들을 위한 컬럼 추가
        include_with_llm = include_df.copy()
        include_with_llm['rule_depression_keywords'] = include_with_llm['depression_keywords']
        include_with_llm['rule_mobile_keywords'] = include_with_llm['mobile_keywords']
        include_with_llm['rule_behavioral_keywords'] = include_with_llm['behavioral_keywords']
        include_with_llm['rule_result'] = include_with_llm['result']
        include_with_llm['llm_depression_keywords'] = ''
        include_with_llm['llm_mobile_keywords'] = ''
        include_with_llm['llm_behavioral_keywords'] = ''
        include_with_llm['llm_result'] = 'not_processed'
        include_with_llm['llm_depression_highlight'] = ''
        include_with_llm['llm_mobile_highlight'] = ''
        include_with_llm['llm_behavioral_highlight'] = ''
        include_with_llm['llm_reason'] = '이미 규칙 기반에서 포함됨'
        include_with_llm['final_result'] = 'include'
        
        # 최종 결과 병합
        final_df = pd.concat([include_with_llm, exclude_results_df], ignore_index=True)
        
        # 최종 결과 저장
        final_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        
        # 체크포인트 파일 정리
        if os.path.exists(checkpoint_path):
            os.remove(checkpoint_path)
        
        self.logger.info(f"LLM 2차 검토 완료. 결과 저장: {output_file}")
        
        # 요약 통계
        llm_include_count = sum(1 for r in results if r['final_result'] == 'include')
        llm_exclude_count = len(results) - llm_include_count
        total_include = len(include_df) + llm_include_count
        total_exclude = llm_exclude_count
        
        self.logger.info(f"=== LLM 2차 검토 요약 ===")
        self.logger.info(f"기존 규칙 기반 include: {len(include_df)}개")
        self.logger.info(f"LLM 2차 검토에서 include로 변경: {llm_include_count}개")
        self.logger.info(f"LLM 2차 검토에서도 exclude: {llm_exclude_count}개")
        self.logger.info(f"최종 include: {total_include}개")
        self.logger.info(f"최종 exclude: {total_exclude}개")
        
        return final_df

def main():
    """메인 실행 함수"""
    # 입력/출력 파일 경로
    input_file = "rule_base_output/rule_based_results_20250702_081407.csv"
    output_file = f"output/llm_secondary_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    # 출력 디렉토리 생성
    os.makedirs("output", exist_ok=True)
    
    try:
        # 프로세서 초기화
        filter_system = LLMSecondaryFilter(debug=True)
        
        # LLM 2차 검토 실행
        results_df = filter_system.process_exclude_papers(input_file, output_file)
        
        filter_system.logger.info("LLM 2차 키워드 필터링 완료!")
        return results_df
        
    except Exception as e:
        print(f"메인 실행 중 오류: {e}")
        raise

if __name__ == "__main__":
    main()