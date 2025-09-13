# keyword_matcher.py

import re
import json
from typing import List, Dict, Tuple
from pathlib import Path
from database.connection import DatabaseManager
from .constants import (
    ALIAS_MAPPINGS, SEPARATOR_PATTERN, KEYWORD_SEPARATORS, 
    MEANINGFUL_PATTERNS, CATEGORY_PATTERNS, REQUIRED_INDICATORS,
    TRADE_INDICATORS, NEGATIVE_INDICATORS
)

class KeywordMatcher:
    """
    - JSON/DB에 정의된 키워드만 탐지(그 외 카테고리/키워드 없음)
    - '토토DB' / '토토 디비' / '토토 D B'처럼 변형 허용
    - 부분어('토토' 단독) 매칭 방지: 항상 '풀네임 정규화 문자열'로만 탐지
    """

    def __init__(self, db_manager: DatabaseManager = None, json_filename: str = "illegal_keywords.json", search_mode: str = "exact"):
        self.db_manager = db_manager or DatabaseManager()
        self.illegal_keywords: Dict[str, List[str]] = {}  # {category: [keyword, ...]}
        self.compiled_norms: Dict[str, List[Dict]] = {}    # {category: [{'norm': str, 'raw': str}]}
        self.false_positive: Dict[str, List[str]] = {}
        self.search_mode = search_mode  # "exact" = 전체 키워드 검색, "partial" = 부분 키워드 검색

        # constants에서 가져온 설정들
        self.aliases = ALIAS_MAPPINGS
        self.sep_re = re.compile(SEPARATOR_PATTERN)

        self._load_illegal_from_db()
        self._maybe_merge_illegal_from_json(json_filename)  # DB + JSON 병합 가능 (중복 자동 제거)
        self._maybe_load_false_positive_from_json(json_filename)
        self._compile_norms()

    # ---------- Load ----------
    def _load_illegal_from_db(self):
        rows = self.db_manager.get_keywords()  # expected columns: id, category, keyword, ...
        for row in rows:
            if len(row) >= 3:
                _, cat, kw = row[:3]
                self.illegal_keywords.setdefault(cat, []).append(kw)

    def _maybe_merge_illegal_from_json(self, filename: str):
        p_candidates = [
            Path(__file__).resolve().parent / filename,            # detector/illegal_keywords.json
            Path(__file__).resolve().parents[0] / filename,       # same dir fallback
            Path.cwd() / filename                                  # project root
        ]
        for p in p_candidates:
            if p.exists():
                data = json.loads(p.read_text(encoding='utf-8'))
                jk = data.get('illegal_keywords', {})
                for cat, kw_list in jk.items():
                    for kw in kw_list:
                        self.illegal_keywords.setdefault(cat, [])
                        if kw not in self.illegal_keywords[cat]:
                            self.illegal_keywords[cat].append(kw)
                break

    def _maybe_load_false_positive_from_json(self, filename: str):
        p_candidates = [
            Path(__file__).resolve().parent / filename,
            Path(__file__).resolve().parents[0] / filename,
            Path.cwd() / filename
        ]
        for p in p_candidates:
            if p.exists():
                data = json.loads(p.read_text(encoding='utf-8'))
                self.false_positive = data.get('false_positive_keywords', {}) or {}
                return
        self.false_positive = {}

    # ---------- Compile (Normalization-based) ----------
    def _compile_norms(self):
        self.compiled_norms.clear()
        for cat, klist in self.illegal_keywords.items():
            bucket = []
            seen = set()
            for raw_kw in klist:
                if self.search_mode == "exact":
                    # 전체 키워드 검색: 완전한 키워드만 사용
                    for variant in self._expand_alias_variants(raw_kw):
                        norm_v = self._normalize(variant)
                        if norm_v and norm_v not in seen:
                            seen.add(norm_v)
                            bucket.append({'norm': norm_v, 'raw': raw_kw})
                else:
                    # 부분 키워드 검색: 동적으로 추출된 부분 키워드 사용
                    partial_keywords = self._extract_partial_keywords(raw_kw)
                    for partial in partial_keywords:
                        for variant in self._expand_alias_variants(partial):
                            norm_v = self._normalize(variant)
                            if norm_v and norm_v not in seen and len(norm_v) >= 2:  # 최소 2글자 이상
                                seen.add(norm_v)
                                bucket.append({'norm': norm_v, 'raw': raw_kw})
            self.compiled_norms[cat] = bucket

    def _expand_alias_variants(self, s: str) -> List[str]:
        # DB/디비, ID/아이디 왕복 변형만 최소 생성
        variants = set([s])
        variants.add(re.sub(r'디\s*비', 'DB', s, flags=re.IGNORECASE))
        variants.add(re.sub(r'아이\s*디', 'ID', s, flags=re.IGNORECASE))
        variants.add(re.sub(r'D\s*B', '디비', s, flags=re.IGNORECASE))
        variants.add(re.sub(r'I\s*D', '아이디', s, flags=re.IGNORECASE))
        return list(variants)
    
    def _extract_partial_keywords(self, keyword: str) -> List[str]:
        """키워드에서 의미있는 부분 키워드들을 동적으로 추출"""
        partials = []
        
        # 1. 일반적인 구분자로 분리
        for sep_pattern in KEYWORD_SEPARATORS:
            parts = re.split(f'({sep_pattern})', keyword, flags=re.IGNORECASE)
            for part in parts:
                part = part.strip()
                if part and len(part) >= 2 and not re.match(r'^[0-9\W]+$', part):
                    partials.append(part)
        
        # 2. 의미있는 단어 패턴 추출
        for pattern in MEANINGFUL_PATTERNS:
            matches = re.findall(pattern, keyword, re.IGNORECASE)
            partials.extend(matches)
        
        # 3. 중복 제거 및 원본 키워드 포함
        unique_partials = list(set([keyword] + partials))
        
        return unique_partials

    def _normalize(self, s: str) -> str:
        if not s:
            return ''
        t = s
        for src, dst in self.aliases:
            t = re.sub(src, dst, t, flags=re.IGNORECASE)
        t = t.lower()
        t = self.sep_re.sub('', t)  # 공백/구분자 제거
        return t

    def _build_norm_map(self, text: str) -> Tuple[str, List[int]]:
        t = text
        for src, dst in self.aliases:
            t = re.sub(src, dst, t, flags=re.IGNORECASE)
        norm_chars, idx_map = [], []
        i = 0
        while i < len(t):
            ch = t[i]
            if self.sep_re.match(ch):
                i += 1
                continue
            norm_chars.append(ch.lower())
            idx_map.append(i)
            i += 1
        return ''.join(norm_chars), idx_map

    # ---------- Detect ----------
    def detect_keywords_in_text(self, text: str, enable_secondary_filter: bool = True, require_full_combination: bool = False) -> Dict[str, List[Dict]]:
        if not text:
            return {}
        
        # 조합 필터링: 부분 키워드로 검색하되 전체 키워드 조합이 있을 때만 반환
        if require_full_combination:
            detected = self._detect_with_combination_filter(text, enable_secondary_filter)
            return self._remove_duplicates(detected)
        
        # 기존 방식
        norm_text, idx_map = self._build_norm_map(text)
        detected: Dict[str, List[Dict]] = {}

        for cat, items in self.compiled_norms.items():
            hits = []
            for item in items:
                needle = item['norm']
                start = 0
                while True:
                    pos = norm_text.find(needle, start)
                    if pos == -1:
                        break
                    end_pos = pos + len(needle)
                    orig_start = idx_map[pos]
                    orig_end = idx_map[end_pos - 1] + 1
                    matched_text = text[orig_start:orig_end]
                    
                    # 2차 필터링 적용
                    if enable_secondary_filter:
                        if not self._passes_secondary_filter(item['raw'], matched_text, text, orig_start, orig_end, cat):
                            start = end_pos
                            continue
                    
                    hits.append({
                        'keyword': item['raw'],          # 원본 키워드로 기록
                        'matched_text': matched_text,    # 실제 매칭 문자열
                        'start_position': orig_start,
                        'end_position': orig_end,
                        'context': self._get_context(text, orig_start, orig_end)
                    })
                    start = end_pos

            # false positive 필터(선택)
            if hits and self.false_positive.get(cat):
                fp_norms = [self._normalize(x) for x in self.false_positive[cat] if x]
                filtered = []
                for h in hits:
                    ctx_norm = self._normalize(h['context'])
                    if any(fp in ctx_norm for fp in fp_norms):
                        continue
                    filtered.append(h)
                hits = filtered

            if hits:
                detected[cat] = hits
        
        # 중복 제거 적용
        return self._remove_duplicates(detected)
    
    def _detect_with_combination_filter(self, text: str, enable_secondary_filter: bool) -> Dict[str, List[Dict]]:
        """부분 키워드로 검색하되 전체 키워드 조합이 존재할 때만 반환"""
        detected: Dict[str, List[Dict]] = {}
        text_lower = text.lower()
        
        # 모든 원본 키워드에 대해 조합 확인
        for cat, klist in self.illegal_keywords.items():
            hits = []
            for original_keyword in klist:
                
                # 전체 키워드가 텍스트에 존재하는지 확인
                if self._check_full_keyword_presence(original_keyword, text):
                    # 전체 키워드 위치 찾기
                    positions = self._find_keyword_positions(original_keyword, text)
                    
                    for start_pos, end_pos, matched_text in positions:
                        # 2차 필터링 적용
                        if enable_secondary_filter:
                            if not self._passes_secondary_filter(original_keyword, matched_text, text, start_pos, end_pos, cat):
                                continue
                        
                        hits.append({
                            'keyword': original_keyword,
                            'matched_text': matched_text,
                            'start_position': start_pos,
                            'end_position': end_pos,
                            'context': self._get_context(text, start_pos, end_pos)
                        })
            
            if hits:
                detected[cat] = hits
        return detected
    
    def _check_full_keyword_presence(self, keyword: str, text: str) -> bool:
        """전체 키워드가 텍스트에 존재하는지 확인 (변형 포함)"""
        text_norm = self._normalize(text)
        
        # 키워드 변형들 생성
        variants = self._expand_alias_variants(keyword)
        
        for variant in variants:
            variant_norm = self._normalize(variant)
            if variant_norm in text_norm:
                return True
                
        return False
    
    def _find_keyword_positions(self, keyword: str, text: str) -> List[Tuple[int, int, str]]:
        """키워드의 모든 위치 찾기"""
        positions = []
        text_lower = text.lower()
        
        # 키워드 변형들에 대해 위치 찾기
        variants = self._expand_alias_variants(keyword)
        
        for variant in variants:
            # 정규식 패턴으로 변환 (공백, 특수문자 허용)
            pattern = self._create_flexible_pattern(variant)
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                start_pos = match.start()
                end_pos = match.end()
                matched_text = text[start_pos:end_pos]
                positions.append((start_pos, end_pos, matched_text))
        
        return positions
    
    def _create_flexible_pattern(self, keyword: str) -> str:
        """키워드를 유연한 정규식 패턴으로 변환 (간단한 방식)"""
        # 간단한 접근: 각 문자 사이에 선택적 공백 허용
        chars = []
        for char in keyword:
            if char.isalnum():
                chars.append(re.escape(char))
            else:
                chars.append(re.escape(char))
        
        # 문자 사이 선택적 공백 허용
        pattern = r'\s*'.join(chars)
        
        # DB/디비 변형 허용
        pattern = pattern.replace('D\\s*B', '(?:DB|디비|D\\.?B)')
        pattern = pattern.replace('디\\s*비', '(?:DB|디비|D\\.?B)')
        pattern = pattern.replace('I\\s*D', '(?:ID|아이디|I\\.?D)')
        pattern = pattern.replace('아\\s*이\\s*디', '(?:ID|아이디|I\\.?D)')
        
        return pattern
    
    def _remove_duplicates(self, detected: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        """중복된 키워드 탐지 결과 제거 (위치 기반 + 포함 관계 고려)"""
        if not detected:
            return detected
            
        cleaned_detected = {}
        
        for category, hits in detected.items():
            if not hits:
                continue
                
            # 위치별로 정렬
            hits_sorted = sorted(hits, key=lambda x: (x['start_position'], x['end_position']))
            
            unique_hits = []
            
            for current_hit in hits_sorted:
                should_add = True
                
                # 기존 결과들과 비교
                for existing_hit in unique_hits[:]:  # 복사본을 순회하여 안전하게 수정
                    # 1. 정확히 같은 위치인 경우
                    if (current_hit['start_position'] == existing_hit['start_position'] and 
                        current_hit['end_position'] == existing_hit['end_position']):
                        # 더 긴 키워드를 선택
                        if len(current_hit['keyword']) > len(existing_hit['keyword']):
                            unique_hits.remove(existing_hit)
                        else:
                            should_add = False
                            break
                    
                    # 2. 포함 관계 체크
                    elif self._is_overlapping_or_contained(current_hit, existing_hit):
                        # 더 긴 키워드를 선택
                        if len(current_hit['keyword']) > len(existing_hit['keyword']):
                            unique_hits.remove(existing_hit)
                        else:
                            should_add = False
                            break
                
                if should_add:
                    unique_hits.append(current_hit)
            
            if unique_hits:
                cleaned_detected[category] = unique_hits
        
        return cleaned_detected
    
    def _is_overlapping_or_contained(self, hit1: Dict, hit2: Dict) -> bool:
        """두 키워드 탐지 결과가 겹치거나 포함 관계인지 확인"""
        start1, end1 = hit1['start_position'], hit1['end_position']
        start2, end2 = hit2['start_position'], hit2['end_position']
        
        # 겹치거나 포함되는 경우
        return not (end1 <= start2 or end2 <= start1)
    
    def _create_unique_key(self, keyword: str, matched_text: str) -> str:
        """중복 체크를 위한 고유 키 생성"""
        # 키워드와 매칭된 텍스트를 정규화하여 고유 키 생성
        norm_keyword = self._normalize(keyword.lower())
        norm_matched = self._normalize(matched_text.lower())
        return f"{norm_keyword}:{norm_matched}"
    
    def _passes_secondary_filter(self, original_keyword: str, matched_text: str, full_text: str, start_pos: int, end_pos: int, category: str) -> bool:
        """2차 필터링: 정확한 키워드 매칭과 컨텍스트 분석"""
        
        # 1. 정확한 키워드 패턴 매칭
        if not self._is_exact_keyword_pattern(original_keyword, full_text, start_pos, end_pos, category):
            return False
            
        # 2. 컨텍스트 기반 유효성 검증
        context = self._get_context(full_text, start_pos, end_pos, context_size=150)
        if not self._is_valid_illegal_context(original_keyword, context, category):
            return False
            
        return True
    
    def _is_exact_keyword_pattern(self, original_keyword: str, text: str, start_pos: int, end_pos: int, category: str) -> bool:
        """카테고리별 정확한 키워드 패턴 매칭"""
        
        # 주변 텍스트 확장해서 정확한 매칭 확인
        extended_start = max(0, start_pos - 10)
        extended_end = min(len(text), end_pos + 10)
        extended_text = text[extended_start:extended_end]
        
        # constants에서 패턴 가져오기
        patterns = CATEGORY_PATTERNS.get(category, [])
        if not patterns:
            return True  # 패턴이 없는 카테고리는 기본 통과
            
        return self._match_category_pattern(original_keyword, extended_text, patterns)
    
    def _match_category_pattern(self, keyword: str, text: str, patterns: List[str]) -> bool:
        """카테고리 패턴들을 사용한 통합 매칭"""
        text_lower = text.lower()
        keyword_lower = keyword.lower()
        
        # 패턴 매칭 시도
        for pattern in patterns:
            if re.search(pattern, keyword_lower):
                if re.search(pattern, text_lower):
                    return self._check_word_boundaries_regex(text, pattern)
        
        # 백업: 정규화된 키워드가 텍스트에 포함되어 있으면 허용
        def simple_normalize(s):
            return s.lower().replace(' ', '').replace('-', '').replace('_', '')
        
        norm_keyword = simple_normalize(keyword)
        norm_text = simple_normalize(text)
        
        if norm_keyword in norm_text:
            return True
        
        return False
    
    def _check_word_boundaries_regex(self, text: str, pattern: str) -> bool:
        """정규식 패턴의 단어 경계 확인"""
        matches = list(re.finditer(pattern, text.lower()))
        if not matches:
            return False
            
        for match in matches:
            start, end = match.span()
            # 앞뒤 문자가 알파벳/숫자가 아니어야 함
            before_ok = start == 0 or not text[start-1].isalnum()
            after_ok = end == len(text) or not text[end].isalnum()
            if before_ok and after_ok:
                return True
                
        return False
    
    def _is_valid_illegal_context(self, keyword: str, context: str, category: str) -> bool:
        """컨텍스트 분석으로 실제 불법 활동인지 검증"""
        context_lower = context.lower()
        keyword_lower = keyword.lower()
        
        # DB/디비 키워드는 그 자체로 불법적이므로 별도 지표 불필요
        db_keywords = ['db', '디비', 'd.b', 'd b']
        if category == "personal_db" and any(db in keyword_lower for db in db_keywords):
            # 대출DB, 주식DB 등은 그 자체로 불법이므로 부정 지표만 체크
            has_negative = any(indicator in context_lower for indicator in NEGATIVE_INDICATORS)
            return not has_negative
        
        # 기존 로직: 다른 카테고리나 DB 키워드가 아닌 경우
        keyword_has_trade = any(indicator in keyword_lower for indicator in TRADE_INDICATORS)
        context_has_trade = any(indicator in context_lower for indicator in TRADE_INDICATORS)
        
        # 해당 카테고리의 필수 지표 확인
        category_required = REQUIRED_INDICATORS.get(category, [])
        has_required_in_context = any(indicator in context_lower for indicator in category_required)
        
        # 키워드 자체나 컨텍스트에 거래 의도가 있으면 통과
        if keyword_has_trade or context_has_trade:
            has_required = True  # 거래 의도가 명확하면 통과
        else:
            has_required = has_required_in_context
        
        # 부정 지표 확인
        has_negative = any(indicator in context_lower for indicator in NEGATIVE_INDICATORS)
        
        # 최종 판단: 필수 지표가 있고 부정 지표가 없어야 함
        return has_required and not has_negative

    # ---------- Score & Summary ----------
    def _get_context(self, text: str, start: int, end: int, context_size: int = 50) -> str:
        s = max(0, start - context_size)
        e = min(len(text), end + context_size)
        ctx = text[s:e]
        mid = text[start:end]
        return ctx.replace(mid, f"**{mid}**")


