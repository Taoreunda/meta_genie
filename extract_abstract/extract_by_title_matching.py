#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
제목 기반 Abstract 추출 스크립트

meta_article_data.csv의 Title을 기준으로 abstract-depression-set.txt에서 
해당하는 abstract를 찾아서 매칭합니다.
"""

import csv
import os
import re
from datetime import datetime
from difflib import SequenceMatcher

def normalize_title(title):
    """제목 정규화 함수"""
    if not title:
        return ""
    
    # 소문자 변환
    normalized = title.lower()
    
    # 특수문자 및 구두점 제거/정규화
    normalized = re.sub(r'[^\w\s]', ' ', normalized)
    
    # 연속된 공백을 하나로 변환
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # 앞뒤 공백 제거
    normalized = normalized.strip()
    
    return normalized

def extract_keywords(title, min_length=4):
    """제목에서 핵심 키워드 추출"""
    if not title:
        return []
    
    # 일반적인 stopwords 제거
    stopwords = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
        'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
        'before', 'after', 'above', 'below', 'between', 'among', 'is', 'are',
        'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does',
        'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can',
        'using', 'based', 'study', 'research', 'analysis', 'trial', 'systematic',
        'review', 'meta'
    }
    
    normalized = normalize_title(title)
    words = normalized.split()
    
    # stopwords가 아니고 최소 길이 이상인 단어들만 추출
    keywords = [word for word in words if word not in stopwords and len(word) >= min_length]
    
    return keywords

def calculate_similarity(title1, title2):
    """두 제목 간의 유사도 계산"""
    # 정규화된 제목으로 직접 비교
    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)
    
    # 완전 일치
    if norm1 == norm2:
        return 1.0
    
    # 시퀀스 매처로 유사도 계산
    similarity = SequenceMatcher(None, norm1, norm2).ratio()
    
    # 키워드 기반 유사도도 계산
    keywords1 = set(extract_keywords(title1))
    keywords2 = set(extract_keywords(title2))
    
    if keywords1 and keywords2:
        keyword_similarity = len(keywords1.intersection(keywords2)) / len(keywords1.union(keywords2))
        # 전체 유사도와 키워드 유사도의 가중 평균
        similarity = (similarity * 0.6) + (keyword_similarity * 0.4)
    
    return similarity

def parse_single_record_v2(record_text, number):
    """
    extract_abstract_v2.py의 파싱 로직 재사용
    단일 레코드 파싱
    """
    lines = record_text.split('\n')
    
    # 초기화
    title = None
    abstract = None
    doi = None
    
    # 1. DOI 추출 - 첫 줄과 두 번째 줄에서 찾기
    first_line = lines[0] if lines else ""
    doi_match = re.search(r'doi:\s*(10\.\d{4,9}/[^\s]+)', first_line, re.IGNORECASE)
    if doi_match:
        doi = doi_match.group(1).strip().rstrip('.')
    else:
        # 두 번째 줄에서 DOI 찾기
        if len(lines) > 1 and 'doi:' in first_line.lower():
            second_line = lines[1].strip()
            if re.match(r'^10\.\d{4,9}/[^\s]+\.?$', second_line):
                doi = second_line.rstrip('.')
    
    # 2. 제목 찾기 - Author information 이전까지
    author_info_idx = -1
    for idx, line in enumerate(lines):
        if 'Author information:' in line:
            author_info_idx = idx
            break
    
    if author_info_idx != -1:
        # Author information 이전까지의 텍스트에서 제목 추출
        title_part = record_text[:record_text.find('Author information:')]
        temp_lines = title_part.split('\n')
        title_lines = []
        skip_empty_lines = 0
        
        for i, line in enumerate(temp_lines[1:], 1):
            line = line.strip()
            
            # 건너뛸 줄들 (DOI, 년도, Epub 등)
            if (re.search(r'^10\.\d{4,9}/[^\s]+\.?$', line) or  # DOI 패턴
                re.search(r'10\.\d{4,9}/[^\s]+\.?\s*Epub', line) or  # DOI + Epub 패턴
                re.search(r'^\d{4}|^Epub|^pp\.', line) or  # 년도, Epub, 페이지
                len(line) < 10):  # 짧은 줄
                continue
                
            # 빈 줄 처리
            if not line:
                skip_empty_lines += 1
                if skip_empty_lines >= 2:
                    break
                continue
            else:
                skip_empty_lines = 0
            
            # 저자명 패턴 감지
            if re.search(r'[A-Z][a-z]+\s+[A-Z]{2,}\(\d+\)', line):
                break
            
            # 저자 참조 번호 패턴 감지 ((1), (2) 등)
            if re.search(r'\(\d+\)', line):
                break
            
            # 제목에 추가
            title_lines.append(line)
        
        if title_lines:
            title = ' '.join(title_lines).strip()
            # 후처리: 제목 끝의 마침표 제거
            if title and title.endswith('.'):
                title = title.rstrip('.')
    
    # 3. Abstract 추출 - Author information 이후
    abstract_lines = []
    if author_info_idx != -1:
        abstract_started = False
        in_author_block = True
        
        for i in range(author_info_idx + 1, len(lines)):
            line = lines[i].strip()
            
            # 종료 조건 확인
            if (line.startswith('©') or 
                line.startswith('Copyright') or 
                line.startswith('DOI:') or 
                line.startswith('PMID:') or
                line.startswith('PMCID:') or
                line.startswith('Conflict of interest')):
                break
            
            if in_author_block:
                # Author 정보 블록 건너뛰기
                if (line.startswith('(') and ')' in line) or '@' in line or '.edu' in line or '.org' in line:
                    continue
                elif not line:
                    in_author_block = False
                    continue
                elif any(keyword in line.upper() for keyword in ['INTRODUCTION:', 'BACKGROUND:', 'OBJECTIVE:', 'PURPOSE:', 'METHODS:']):
                    in_author_block = False
                    abstract_started = True
                    abstract_lines.append(line)
                else:
                    continue
            else:
                if not abstract_started and line:
                    abstract_started = True
                    abstract_lines.append(line)
                elif abstract_started and line:
                    abstract_lines.append(line)
        
        abstract = ' '.join(abstract_lines).strip() if abstract_lines else None
    
    # 4. 백업 방법: INTRODUCTION 등 키워드로 abstract 찾기
    if not abstract:
        abstract_keywords = ['INTRODUCTION:', 'BACKGROUND:', 'IMPORTANCE:', 'PURPOSE:', 'OBJECTIVE:']
        
        for keyword in abstract_keywords:
            pattern = f'\\n{re.escape(keyword)}|^{re.escape(keyword)}'
            match = re.search(pattern, record_text, re.IGNORECASE | re.MULTILINE)
            if match:
                start_pos = match.start()
                if record_text[start_pos] == '\\n':
                    start_pos += 1
                
                # 종료 위치 찾기
                end_markers = ['©', 'Copyright', 'DOI:', 'PMID:', 'PMCID:', 'Conflict of interest']
                end_pos = len(record_text)
                
                for marker in end_markers:
                    marker_match = re.search(re.escape(marker), record_text[start_pos:], re.IGNORECASE)
                    if marker_match:
                        end_pos = start_pos + marker_match.start()
                        break
                
                raw_abstract = record_text[start_pos:end_pos].strip()
                abstract = re.sub(r'\s+', ' ', raw_abstract).strip()
                break
    
    return {
        'number': number,
        'title': title,
        'abstract': abstract,
        'doi': doi
    }

def load_abstracts_from_text(text_file_path):
    """abstract-depression-set.txt에서 모든 abstract 로드"""
    try:
        with open(text_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {text_file_path}: {e}")
        return {}
    
    print("📖 abstract-depression-set.txt에서 데이터 파싱 중...")
    
    # V2 파서와 동일한 로직으로 레코드 분할
    record_positions = []
    for match in re.finditer(r'^(\d+)\.\s+', content, re.MULTILINE):
        number = int(match.group(1))
        start_pos = match.start()
        record_positions.append((start_pos, number))
    
    # 순차적 번호만 필터링
    sequential_positions = []
    expected_num = 1
    
    for pos, num in record_positions:
        if num == expected_num:
            sequential_positions.append((pos, num))
            expected_num += 1
    
    print(f"✅ {len(sequential_positions)}개의 순차적 레코드 발견")
    
    # 각 레코드 파싱
    abstracts_dict = {}
    total_records = len(sequential_positions)
    
    for i, (start_pos, number) in enumerate(sequential_positions):
        # 진행 상황 표시 (100개마다)
        if (i + 1) % 100 == 0 or i == 0:
            progress = ((i + 1) / total_records) * 100
            print(f"  📊 Abstract 파싱 진행: {i + 1}/{total_records} ({progress:.1f}%)")
        
        try:
            # 레코드 끝 위치 결정
            if i < len(sequential_positions) - 1:
                end_pos = sequential_positions[i + 1][0]
            else:
                end_pos = len(content)
            
            record_text = content[start_pos:end_pos].strip()
            
            # 파싱 실행
            result = parse_single_record_v2(record_text, number)
            if result and result['title']:
                abstracts_dict[normalize_title(result['title'])] = result
                
        except Exception as e:
            print(f"Error parsing record {number}: {e}")
            continue
    
    print(f"📚 {len(abstracts_dict)}개의 제목-추상 매핑 생성")
    return abstracts_dict

def load_meta_data(csv_file_path):
    """meta_article_data.csv 로드"""
    try:
        with open(csv_file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            return list(reader)
    except Exception as e:
        print(f"Error reading {csv_file_path}: {e}")
        return []

def match_titles_and_extract(meta_data, abstracts_dict, similarity_threshold=0.7):
    """제목 매칭 및 Abstract 추출"""
    
    print(f"\\n🔍 제목 매칭 시작 (임계값: {similarity_threshold})")
    
    matches = {
        'exact': [],
        'fuzzy': [],
        'no_match': []
    }
    
    existing_abstracts = 0
    new_abstracts = 0
    
    total_rows = len(meta_data)
    
    for i, row in enumerate(meta_data):
        # 진행 상황 표시 (100개마다)
        if (i + 1) % 100 == 0 or i == 0:
            progress = ((i + 1) / total_rows) * 100
            print(f"  📊 진행 상황: {i + 1}/{total_rows} ({progress:.1f}%)")
        
        meta_title = row.get('Title', '').strip()
        existing_abstract = row.get('Abstract', '').strip()
        
        if existing_abstract:
            existing_abstracts += 1
            continue
        
        if not meta_title:
            matches['no_match'].append({'row': row, 'reason': 'Empty title'})
            continue
        
        normalized_meta_title = normalize_title(meta_title)
        
        # 1. 정확한 매칭 시도
        if normalized_meta_title in abstracts_dict:
            matched_data = abstracts_dict[normalized_meta_title]
            row['Abstract'] = matched_data['abstract']
            if not row.get('DOI') and matched_data.get('doi'):
                row['DOI'] = matched_data['doi']
            
            matches['exact'].append({
                'meta_title': meta_title,
                'matched_title': matched_data['title'],
                'similarity': 1.0
            })
            new_abstracts += 1
            continue
        
        # 2. 퍼지 매칭 시도
        best_match = None
        best_similarity = 0
        
        for abstract_title_norm, abstract_data in abstracts_dict.items():
            similarity = calculate_similarity(normalized_meta_title, abstract_title_norm)
            
            if similarity > best_similarity and similarity >= similarity_threshold:
                best_similarity = similarity
                best_match = abstract_data
        
        if best_match:
            row['Abstract'] = best_match['abstract']
            if not row.get('DOI') and best_match.get('doi'):
                row['DOI'] = best_match['doi']
            
            matches['fuzzy'].append({
                'meta_title': meta_title,
                'matched_title': best_match['title'],
                'similarity': best_similarity
            })
            new_abstracts += 1
        else:
            # 매칭 실패 시에도 가장 유사한 제목 기록 (검토용)
            closest_match = None
            closest_similarity = 0
            
            # 가장 유사한 제목 찾기 (임계값 미만이지만)
            for abstract_title_norm, abstract_data in abstracts_dict.items():
                similarity = calculate_similarity(normalized_meta_title, abstract_title_norm)
                if similarity > closest_similarity:
                    closest_similarity = similarity
                    closest_match = abstract_data
            
            matches['no_match'].append({
                'row': row, 
                'reason': f'No match above {similarity_threshold}',
                'closest_match_title': closest_match['title'] if closest_match else '',
                'closest_similarity': closest_similarity
            })
    
    # 통계 출력
    print(f"\\n📊 === 매칭 결과 통계 ===")
    print(f"📁 전체 메타 데이터: {len(meta_data)}")
    print(f"📈 기존 Abstract: {existing_abstracts}")
    print(f"✅ 정확한 매칭: {len(matches['exact'])}")
    print(f"🔍 퍼지 매칭: {len(matches['fuzzy'])}")
    print(f"❌ 매칭 실패: {len(matches['no_match'])}")
    print(f"🆕 새로 추가된 Abstract: {new_abstracts}")
    print(f"📊 최종 Abstract 수: {existing_abstracts + new_abstracts}")
    print(f"📈 최종 Abstract 비율: {(existing_abstracts + new_abstracts)/len(meta_data)*100:.1f}%")
    
    return matches

def save_results(meta_data, matches, output_dir):
    """결과 저장"""
    
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 1. 통합된 결과 CSV 파일 생성 (매칭 정보 포함)
    output_file = os.path.join(output_dir, f'title_matched_complete_{timestamp}.csv')
    
    if meta_data:
        # 기본 필드에 매칭 정보 추가
        base_fieldnames = list(meta_data[0].keys())
        extended_fieldnames = base_fieldnames + ['Matched_Title', 'Match_Type', 'Match_Similarity', 'Match_Status']
        
        # 매칭 정보를 딕셔너리로 변환
        exact_matches = {match['meta_title']: match for match in matches['exact']}
        fuzzy_matches = {match['meta_title']: match for match in matches['fuzzy']}
        no_matches = {item['row'].get('Title', ''): item for item in matches['no_match'] if 'row' in item}
        
        try:
            with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=extended_fieldnames, quoting=csv.QUOTE_ALL)
                writer.writeheader()
                
                for row in meta_data:
                    title = row.get('Title', '')
                    
                    # 원본 데이터를 복사하고 매칭 정보 추가
                    output_row = row.copy()
                    
                    # 데이터 검증 및 정리
                    for key, value in output_row.items():
                        if isinstance(value, str):
                            # 너무 긴 텍스트 필드 체크 (10000자 이상)
                            if len(value) > 10000:
                                print(f"⚠️  경고: 행 {meta_data.index(row)+1}, 필드 '{key}'가 비정상적으로 긺 ({len(value)}자)")
                                # 첫 5000자만 유지
                                output_row[key] = value[:5000] + "... [TRUNCATED]"
                            
                            # 개행 문자를 공백으로 변환
                            output_row[key] = value.replace('\n', ' ').replace('\r', ' ')
                    
                    if title in exact_matches:
                        output_row['Match_Type'] = 'Exact'
                        output_row['Match_Similarity'] = exact_matches[title]['similarity']
                        output_row['Match_Status'] = 'Success'
                        output_row['Matched_Title'] = exact_matches[title]['matched_title']
                    elif title in fuzzy_matches:
                        output_row['Match_Type'] = 'Fuzzy'
                        output_row['Match_Similarity'] = fuzzy_matches[title]['similarity']
                        output_row['Match_Status'] = 'Success'
                        output_row['Matched_Title'] = fuzzy_matches[title]['matched_title']
                    elif title in no_matches:
                        output_row['Match_Type'] = 'None'
                        output_row['Match_Similarity'] = 0.0
                        output_row['Match_Status'] = f"Failed: {no_matches[title]['reason']}"
                        output_row['Matched_Title'] = ''
                    else:
                        # 기존에 Abstract가 있었던 경우
                        output_row['Match_Type'] = 'Existing'
                        output_row['Match_Similarity'] = 1.0
                        output_row['Match_Status'] = 'Had Abstract'
                        output_row['Matched_Title'] = ''
                    
                    writer.writerow(output_row)
            
            print(f"\\n💾 통합된 결과 저장: {output_file}")
        except Exception as e:
            print(f"Error saving complete data: {e}")
    
    # 2. 실패한 항목들만 별도 CSV로 저장 (검토용)
    failed_file = os.path.join(output_dir, f'failed_matches_{timestamp}.csv')
    
    try:
        with open(failed_file, 'w', newline='', encoding='utf-8-sig') as f:
            if matches['no_match']:
                # 실패한 항목의 전체 정보 + 가장 유사한 제목 저장
                failed_fieldnames = list(meta_data[0].keys()) + ['Failure_Reason', 'Closest_Match_Title', 'Closest_Similarity']
                writer = csv.DictWriter(f, fieldnames=failed_fieldnames, quoting=csv.QUOTE_ALL)
                writer.writeheader()
                
                for item in matches['no_match']:
                    if 'row' in item:
                        failed_row = item['row'].copy()
                        
                        # 데이터 검증 및 정리
                        for key, value in failed_row.items():
                            if isinstance(value, str):
                                # 너무 긴 텍스트 필드 체크
                                if len(value) > 10000:
                                    failed_row[key] = value[:5000] + "... [TRUNCATED]"
                                # 개행 문자를 공백으로 변환
                                failed_row[key] = value.replace('\n', ' ').replace('\r', ' ')
                        
                        failed_row['Failure_Reason'] = item['reason']
                        failed_row['Closest_Match_Title'] = item.get('closest_match_title', '')
                        failed_row['Closest_Similarity'] = item.get('closest_similarity', 0.0)
                        writer.writerow(failed_row)
        
        print(f"💾 실패 항목 CSV 저장: {failed_file} ({len(matches['no_match'])}개)")
    except Exception as e:
        print(f"Error saving failed matches: {e}")
    
    return output_file, failed_file

def main():
    """메인 함수"""
    
    print("=== 제목 기반 Abstract 추출 시작 ===")
    
    # 파일 경로 설정
    script_dir = os.path.dirname(os.path.abspath(__file__))
    meta_csv_path = os.path.join(script_dir, '../data/meta_article_empty_abstract_data.csv')
    abstracts_txt_path = os.path.join(script_dir, 'abstract-depression-set.txt')
    output_dir = os.path.join(script_dir, 'output')
    
    # 파일 존재 확인
    if not os.path.exists(meta_csv_path):
        print(f"Error: {meta_csv_path} 파일을 찾을 수 없습니다.")
        return
    
    if not os.path.exists(abstracts_txt_path):
        print(f"Error: {abstracts_txt_path} 파일을 찾을 수 없습니다.")
        return
    
    # 1. 데이터 로드
    print("\\n📁 데이터 로딩...")
    meta_data = load_meta_data(meta_csv_path)
    if not meta_data:
        print("메타 데이터 로딩 실패")
        return
    print(f"✅ 메타 데이터: {len(meta_data)} rows")
    
    abstracts_dict = load_abstracts_from_text(abstracts_txt_path)
    if not abstracts_dict:
        print("Abstract 데이터 로딩 실패")
        return
    
    # 2. 제목 매칭 및 추출
    matches = match_titles_and_extract(meta_data, abstracts_dict, similarity_threshold=0.7)
    
    # 3. 결과 저장
    complete_file, failed_file = save_results(meta_data, matches, output_dir)
    
    print("\\n✅ 제목 기반 Abstract 추출 완료!")
    print(f"📄 통합 파일: {complete_file}")
    print(f"📄 실패 항목: {failed_file}")

if __name__ == "__main__":
    main()