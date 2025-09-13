# manual_crawler.py

#!/usr/bin/env python3
import time
from datetime import datetime
from typing import List, Dict, Optional
import re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from .constants import (NOISE_CLASSES, NOISE_IDS, POST_LINK_SELECTORS, TITLE_SELECTORS, 
                          REMOVE_TAGS, NOISE_TEXT_PATTERNS, TITLE_NOISE_PATTERNS, 
                          ILLEGAL_AD_PATTERNS, SPAM_CHAR_PATTERNS)

class ManualCrawler:
    def __init__(self, headless: bool = True, browser_type: str = 'chromium', verbose: bool = False):
        self.headless = headless
        self.browser_type = browser_type
        self.verbose = verbose
        self.playwright = None
        self.browser = None
        self.context = None

    def _setup_browser(self):
        if self.playwright is None:
            self.playwright = sync_playwright().start()
        if self.browser is None:
            launcher = {'chromium': self.playwright.chromium,
                        'firefox': self.playwright.firefox,
                        'webkit': self.playwright.webkit}[self.browser_type]
            
            # 더 강력한 봇 탐지 우회를 위한 브라우저 설정
            launch_options = {
                'headless': self.headless,
                'args': [
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--disable-dev-shm-usage',
                    '--disable-extensions',
                    '--no-first-run',
                    '--no-default-browser-check',
                    '--disable-default-apps',
                    '--disable-popup-blocking',
                    '--disable-translate',
                    '--disable-background-timer-throttling',
                    '--disable-renderer-backgrounding',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-ipc-flooding-protection'
                ]
            }
            self.browser = launcher.launch(**launch_options)
        if self.context is None:
            # 브라우저별 User-Agent 설정
            if self.browser_type == 'firefox':
                user_agent_str = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0'
            else:
                user_agent_str = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
            
            self.context = self.browser.new_context(
                user_agent=user_agent_str,
                viewport={'width': 1920, 'height': 1080},
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Sec-Ch-Ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                    'Sec-Ch-Ua-Mobile': '?0',
                    'Sec-Ch-Ua-Platform': '"Windows"',
                    'Upgrade-Insecure-Requests': '1',
                    'Cache-Control': 'max-age=0'
                },
                java_script_enabled=True,
                ignore_https_errors=True,
                # 봇 탐지 우회를 위한 추가 설정
                permissions=['geolocation'],
                geolocation={'latitude': 37.5665, 'longitude': 126.9780}  # 서울 좌표
            )
        # 초기화 완료

    def _cleanup_browser(self):
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        finally:
            self.context = self.browser = self.playwright = None

    # --- 게시판에서 키워드 포함(제목) 링크만 수집 ---
    def get_board_post_links(self, board_url: str, max_pages: int = 5) -> List[str]:
        if self.verbose:
            print(f'게시판 링크 수집 시작: {board_url} (최대 {max_pages}페이지)')
        post_links: List[str] = []
        try:
            self._setup_browser()
            
            # 페이지 파라미터 자동 감지
            import re
            page_patterns = [
                r'pageid=(\d+)',    # K-Board 계열
                r'page=(\d+)',      # 그누보드, 일반적
                r'p=(\d+)',         # 워드프레스 등
                r'pg=(\d+)',        # 일부 게시판
                r'paged=(\d+)',     # 일부 CMS
            ]
            
            # 기존 URL에서 페이지 파라미터 찾기
            current_page_param = None
            start_page = 1
            for pattern in page_patterns:
                match = re.search(pattern, board_url)
                if match:
                    current_page_param = pattern.split('=')[0] + '='
                    start_page = int(match.group(1))
                    break
            
            for i in range(max_pages):
                page_num = start_page + i
                if self.verbose:
                    print(f'[{i+1}/{max_pages}] 페이지 {page_num} 수집 중...')
                
                # 범용 페이지 URL 생성
                if current_page_param:
                    # 기존 페이지 파라미터 교체
                    pattern = current_page_param.replace('=', r'=\d+')
                    page_url = re.sub(pattern, f'{current_page_param}{page_num}', board_url)
                else:
                    # 페이지 파라미터가 없으면 일반적인 형태로 추가
                    if '?' in board_url:
                        page_url = f"{board_url}&page={page_num}"
                    else:
                        page_url = f"{board_url}?page={page_num}"
                
                # 페이지 로드
                page = self.context.new_page()
                page.set_default_timeout(15000)
                
                try:
                    import random
                    
                    # 다양한 User-Agent 헤더
                    user_agents = [
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
                        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0'
                    ]
                    
                    # 랜덤 헤더 설정
                    random_ua = random.choice(user_agents)
                    random_headers = {
                        'User-Agent': random_ua,
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                        'Accept-Language': random.choice(['ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7', 'ko,en-US;q=0.8,en;q=0.6']),
                        'Accept-Encoding': 'gzip, deflate, br',
                        'DNT': '1',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': random.choice(['none', 'same-origin', 'cross-site']),
                        'Sec-Fetch-User': '?1',
                        'Cache-Control': random.choice(['no-cache', 'max-age=0']),
                        'Pragma': 'no-cache'
                    }
                    
                    # 페이지별 헤더 적용
                    page.set_extra_http_headers(random_headers)
                    
                    # 자연스러운 지연
                    time.sleep(random.uniform(2.0, 4.0))
                    
                    resp = page.goto(page_url, wait_until='domcontentloaded', timeout=15000)
                    
                    if not resp or (resp.status and resp.status >= 400):
                        if self.verbose:
                            print(f"❌ 페이지 {page_num} 로드 실패")
                        page.close()
                        continue
                    
                    # 페이지 로드 완료 대기 및 자연스러운 행동 시뮬레이션
                    try:
                        page.wait_for_load_state('networkidle', timeout=8000)
                        
                        # 실제 사용자처럼 페이지 확인하는 동작
                        time.sleep(random.uniform(1.0, 2.5))
                        
                        # 스크롤 시뮬레이션 (자연스러운 읽기 패턴)
                        page.evaluate(f"window.scrollTo(0, {random.randint(100, 500)})")
                        time.sleep(random.uniform(0.5, 1.0))
                        
                        # 마우스 움직임 시뮬레이션
                        page.mouse.move(random.randint(200, 800), random.randint(150, 400))
                        time.sleep(random.uniform(0.3, 0.8))
                        
                    except:
                        pass
                    
                    soup = BeautifulSoup(page.content(), 'html.parser')
                    base_url = f"{urlparse(page_url).scheme}://{urlparse(page_url).netloc}"
                    
                    # 게시글 링크 수집
                    page_links = []
                    for selector in POST_LINK_SELECTORS:
                        links = soup.select(selector)
                        for link in links:
                            href = link.get('href')
                            if href:
                                full_url = urljoin(base_url, href)
                                title = link.get_text(strip=True)
                                
                                if self._is_meaningful_post_title(title):
                                    page_links.append({'url': full_url, 'title': title})
                    
                    # 중복 제거
                    found_count = 0
                    for link_info in page_links:
                        if link_info['url'] not in [link['url'] if isinstance(link, dict) else link for link in post_links]:
                            post_links.append(link_info)  # URL만이 아니라 dict 전체 저장
                            found_count += 1
                            print(f"  수집된 제목{found_count}: {link_info['title']}")
                    
                    if self.verbose:
                        print(f"  페이지 {page_num}: {found_count}개 링크 수집")
                        
                finally:
                    page.close()
            
            if self.verbose:
                print(f'총 {len(post_links)}개 게시글 링크 수집 완료')
            return post_links
        finally:
            self._cleanup_browser()

    
    def _is_meaningful_post_title(self, title: str) -> bool:
        """의미있는 게시글 제목인지 확인"""
        if not title or len(title.strip()) < 3:
            return False
        
        title = title.strip()
        
        # 숫자만 있는 제목 제외
        if title.isdigit():
            return False
        
        # 페이지네이션 관련 제목 제외
        pagination_words = ['다음', '이전', '페이지', '목록', '처음', '마지막', '«', '»', '<', '>', '→', '←']
        if any(word in title for word in pagination_words):
            return False
        
        # 네비게이션/메뉴 제목 제외
        nav_words = [
            '로그인', 'login', '회원가입', 'signup', '메뉴', 'menu', 'home', '홈',
            'my page', '마이페이지', '포럼', '업무', '회원사', '교육', '행사', '자료',
            '콘텐츠로 건너뛰기', '목록보기', 'ci', '소개', '인사말', '연혁', '조직도', '소식', '자료실',
            '자유게시판', '게시판', '공지사항', '문의사항', 'q&a', 'faq'
        ]
        if any(word in title.lower() for word in nav_words):
            return False
        
        # 너무 짧은 기호들 제외
        if len(title) <= 2 and not any(c.isalnum() for c in title):
            return False
        
        # 의미있는 내용이 포함되어야 함 (한글, 영문, 숫자 조합)
        meaningful_chars = len(re.findall(r'[가-힣a-zA-Z0-9]', title))
        if meaningful_chars < 3:
            return False
        
        return True

    # --- URL 리스트 크롤 ---
    def crawl_urls(self, urls: List[str], delay: float = 0.8, skip_keyword_filter: bool = False) -> Dict[str, any]:
        crawled_data: List[Dict] = []
        failed_urls: List[Dict] = []
        try:
            self._setup_browser()
            for i, url in enumerate(urls, 1):
                try:
                    data = self._crawl_single_url(url, skip_keyword_filter=skip_keyword_filter)
                    if data and data.get('content'):
                        crawled_data.append(data)
                    else:
                        failed_urls.append({'url': url, 'error': 'No content', 'timestamp': datetime.now()})
                except Exception as e:
                    failed_urls.append({'url': url, 'error': str(e), 'timestamp': datetime.now()})
                if i < len(urls):
                    # 랜덤 지연으로 봇 탐지 우회
                    import random
                    random_delay = delay + random.uniform(0.5, 2.0)
                    time.sleep(random_delay)
        finally:
            self._cleanup_browser()
        return {
            'success_count': len(crawled_data),
            'failed_count': len(failed_urls),
            'crawled_data': crawled_data,
            'failed_urls': failed_urls
        }

    # --- 단일 페이지 ---
    def _crawl_single_url(self, url: str, skip_keyword_filter: bool = False) -> Optional[Dict]:
        page = None
        try:
            import random
            time.sleep(random.uniform(0.6, 1.5))
            page = self.context.new_page()
            page.set_default_timeout(30000)
            try:
                resp = page.goto(url, wait_until='domcontentloaded', timeout=30000)
                
                # 봇 탐지 우회를 위한 인간적인 동작 시뮬레이션
                import random
                time.sleep(random.uniform(0.5, 1.5))  # 페이지 로딩 후 잠시 대기
                
                # 마우스 움직임 시뮬레이션
                page.mouse.move(random.randint(100, 500), random.randint(100, 400))
                time.sleep(random.uniform(0.1, 0.3))
                
                # 스크롤 시뮬레이션 (게시판 구조 확인용)
                page.evaluate("window.scrollTo(0, Math.floor(Math.random() * 300))")
                time.sleep(random.uniform(0.2, 0.5))
                
                # 응답 확인
                page.wait_for_load_state('networkidle', timeout=10000)
            except TimeoutError:
                pass
            time.sleep(1.0)
            soup = BeautifulSoup(page.content(), 'html.parser')

            # 사전 키워드 필터링 비활성화 (기존 방식으로 복구)
            # 모든 게시글을 크롤링한 후 키워드 탐지하는 방식으로 변경

            return self._extract_content(soup, url)
        finally:
            if page:
                try: page.close()
                except: pass

    # --- 추출 ---
    def _extract_content(self, soup: BeautifulSoup, url: str) -> Dict:
        # body 태그만 추출해서 작업
        body = soup.find('body')
        if not body:
            return {
                'url': url, 
                'title': "제목 없음", 
                'content': "", 
                'crawl_timestamp': datetime.now().isoformat()
            }
        
        # 1차: body에서 제목 추출
        title = self._extract_title_from_body(body, soup)
        
        # 2차: body에서 본문 추출
        content = self._extract_content_from_body(body)
        
        return {
            'url': url, 
            'title': title, 
            'content': self._clean_text(content), 
            'crawl_timestamp': datetime.now().isoformat()
        }

    def _extract_title_from_body(self, body: BeautifulSoup, soup: BeautifulSoup) -> str:
        # 1. 최우선: <title> 태그에서 실제 게시글 제목 추출
        ttag = soup.find('title')
        if ttag:
            t = ttag.get_text(strip=True)
            # 사이트명 제거 패턴들
            if ' - ' in t:
                title_part = t.split(' - ')[0].strip()
            elif ' | ' in t:
                title_part = t.split(' | ')[0].strip()
            else:
                title_part = t
            
            # 게시판명 제거 (Q&A 등)
            if ' Q&A' in title_part:
                title_part = title_part.replace(' Q&A', '').strip()
            
            # 유효한 제목인지 확인
            if (title_part and len(title_part) > 5 and len(title_part) < 300):
                return title_part
        
        # 2. og:title 시도
        og = soup.find('meta', property='og:title')
        if og and og.get('content'):
            t = og.get('content').strip()
            if t and len(t) > 5 and len(t) < 200:
                return t
                
        # 3. body에서 제목 찾기
        title_selectors = TITLE_SELECTORS
        
        for sel in title_selectors:
            el = body.select_one(sel)
            if el:
                title_text = el.get_text(strip=True)
                if (title_text and len(title_text) > 5 and len(title_text) < 200 and
                    not any(noise in title_text for noise in TITLE_NOISE_PATTERNS)):
                    return title_text
        
        # 4. 백업: body에서 첫 번째 적절한 라인을 제목으로 사용
        full_text = body.get_text(separator='\n', strip=True)
        lines = full_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if (len(line) > 10 and len(line) < 200 and
                not any(noise in line for noise in TITLE_NOISE_PATTERNS) and
                len([c for c in line if c.isalnum()]) > len(line) * 0.3):
                return line
                
        return "제목 없음"

    def _extract_content_from_body(self, body: BeautifulSoup) -> str:
        # body를 복사해서 작업 (원본 손상 방지)
        body_copy = body.__copy__()
        
        # 1. 불필요한 태그 제거
        for tag in body_copy(REMOVE_TAGS):
            tag.decompose()
            
        # 2. 노이즈 클래스 제거
        for cls in NOISE_CLASSES:
            for x in body_copy.select(f'.{cls}'):
                x.decompose()
                
        # 3. 노이즈 ID 제거
        for nid in NOISE_IDS:
            el = body_copy.find(id=nid)
            if el:
                el.decompose()
        
        # 4. 본문 영역 우선 탐지
        content_candidates = [
            body_copy.select_one('div.board-content'),
            body_copy.select_one('div.view-content'),
            body_copy.select_one('td.content'),
            body_copy.select_one('.post-content'),
            body_copy.select_one('.article-content'),
            body_copy.select_one('div[class*="content"]'),
            body_copy.select_one('main'),
            body_copy.select_one('.detail'),
            body_copy.select_one('tbody td'),
        ]
        
        # 본문 영역이 발견되면 해당 영역만 사용
        for candidate in content_candidates:
            if candidate:
                content_text = candidate.get_text(separator='\n', strip=True)
                if 30 <= len(content_text) <= 5000:
                    return self._filter_content_lines(content_text)
        
        # 백업: body 전체에서 추출 (하지만 필터링 강화)
        full_text = body_copy.get_text(separator='\n', strip=True)
        return self._filter_content_lines(full_text)
    
    def _filter_content_lines(self, text: str) -> str:
        """본문에서 의미있는 라인만 필터링"""
        if not text:
            return ""
            
        lines = text.split('\n')
        content_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 기본 필터링
            if (len(line) >= 10 and  # 최소 길이
                not line.isdigit() and  # 숫자만 있는 라인 제외
                not any(noise in line.lower() for noise in NOISE_TEXT_PATTERNS) and  # 노이즈 패턴 제외
                len([c for c in line if c.isalnum()]) > len(line) * 0.3):  # 의미있는 문자 비율
                content_lines.append(line)
            
            # 적당한 길이에서 중단
            if len('\n'.join(content_lines)) > 3000:
                break
        
        return '\n'.join(content_lines)

    def _clean_text(self, text: str) -> str:
        if not text: return ""
        
        # 1. 동적 노이즈 패턴 감지 및 제거
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 동적 노이즈 감지
            is_noise = False
            
            # 1. 불법 광고성 키워드 체크 (강력 필터링)
            if any(illegal_word in line for illegal_word in ILLEGAL_AD_PATTERNS):
                is_noise = True
            
            # 2. 스팸성 특수문자 다수 포함 체크
            spam_char_count = sum(1 for char in SPAM_CHAR_PATTERNS if char in line)
            if spam_char_count >= 3:  # 3개 이상의 스팸 특수문자
                is_noise = True
            
            # 3. 반복되는 단어가 많은 라인 (메뉴, 네비게이션)
            words = line.split()
            if len(words) > 3:
                word_freq = {}
                for word in words:
                    word_freq[word] = word_freq.get(word, 0) + 1
                max_freq = max(word_freq.values()) if word_freq else 0
                if max_freq > len(words) * 0.4:  # 40% 이상이 반복 단어
                    is_noise = True
            
            # 4. 전화번호 패턴
            if re.search(r'\d{2,4}-\d{3,4}-\d{4}', line):
                is_noise = True
            
            # 5. 시간 패턴 (운영시간 등)
            if re.search(r'\d{1,2}:\d{2}.*?\d{1,2}:\d{2}', line):
                is_noise = True
            
            # 6. 저작권/회사정보 패턴
            if re.search(r'(copyright|rights|reserved|사업자|등록번호)', line, re.IGNORECASE):
                is_noise = True
            
            # 7. 너무 짧거나 의미없는 라인
            if len(line) < 5 or line.isdigit():
                is_noise = True
                
            if not is_noise:
                cleaned_lines.append(line)
        
        text = '\n'.join(cleaned_lines)
        
        # 2. 의미있는 라인만 최종 선별
        lines = text.split('\n')
        final_lines = []
        
        for line in lines:
            line = line.strip()
            if (len(line) >= 10 and  # 최소 길이
                not line.isdigit() and  # 숫자만 있는 라인 제외
                len(line.split()) >= 2):  # 최소 2개 단어 이상
                final_lines.append(line)
        
        # 3. 재조합 및 기본 정제
        text = '\n'.join(final_lines)
        text = re.sub(r'\n\s*\n', '\n\n', text)  # 빈 줄 정리
        text = re.sub(r' +', ' ', text)          # 다중 공백 정리
        
        return text.strip()

