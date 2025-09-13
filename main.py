# main.py

#!/usr/bin/env python3
import logging
from pathlib import Path

from database.connection import DatabaseManager
from crawler.manual_crawler import ManualCrawler
from detector.keyword_matcher import KeywordMatcher
from config.settings import ILLEGAL_KEYWORDS

Path('logs').mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('logs/app.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class URLKeywordDetectionSystem:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.keyword_matcher = KeywordMatcher(self.db_manager)
        self.crawler = ManualCrawler()
        self._initialize_keywords()

    def _initialize_keywords(self):
        try:
            if ILLEGAL_KEYWORDS:
                try:
                    self.db_manager.insert_keywords(ILLEGAL_KEYWORDS, ignore_duplicates=True)
                except TypeError:
                    self.db_manager.insert_keywords(ILLEGAL_KEYWORDS)
        except Exception as e:
            logger.error(f"키워드 로드 중 오류: {e}")

    def analyze_url(self, url: str, title: str = None, content: str = None, print_result: bool = True) -> dict:
        results = self.crawler.crawl_urls([url], skip_keyword_filter=True)  # 단일 URL 분석 시 키워드 필터 비활성화
        if results['success_count'] == 0:
            return {'status': 'failed', 'error': '크롤링 실패', 'url': url}

        crawl_data = results['crawled_data'][0]
        title = crawl_data.get('title', '제목 없음') if title is None else title
        content = crawl_data.get('content', '') if content is None else content

        detected_keywords = self.keyword_matcher.detect_keywords_in_text(
            f"{title} {content}", 
            enable_secondary_filter=True
        )
        if print_result and any(detected_keywords.values()):
            self._print_title_and_content(title, content, url)

        # DB 저장은 JSON/DB 키워드가 탐지된 경우에만
        result_id = None
        if any(detected_keywords.values()):
            result_id = self.db_manager.save_crawl_result(
                url=url, title=title, content=content,
                detected_keywords=detected_keywords
            )

        return {
            'status': 'success',
            'result_id': result_id,
            'url': url,
            'title': title,
            'content': content,
            'detected_keywords': detected_keywords
        }
    

    def analyze_board(self, board_url: str, max_pages: int = 5) -> dict:
        # 게시판 크롤링 (수동 키워드 방식)
        self.crawler.verbose = False
        post_urls = self.crawler.get_board_post_links(board_url, max_pages)
        outputs = []
        
        for i, post_info in enumerate(post_urls, 1):
            # post_info가 dict이면 URL과 제목 추출, 아니면 URL만
            if isinstance(post_info, dict):
                url = post_info['url']
                title = post_info['title']
                print(f"[{i}] 키워드 검사: {title}")
            else:
                url = post_info
                print(f"[{i}] 키워드 검사: {url}")
            
            # 단일 URL 분석
            result = self.analyze_url(url, print_result=False)
            
            if result['status'] == 'success' and any(result.get('detected_keywords', {}).values()):
                # DB 저장 (중복 체크는 DatabaseManager 내부에서 처리)
                result_id = self.db_manager.save_crawl_result(
                    url=url, 
                    title=result['title'], 
                    content=result['content'],
                    detected_keywords=result['detected_keywords']
                )
                
                if result_id == "duplicate_url":
                    print(" → 중복 스킵")
                elif result_id == "duplicate_content":
                    print(" → 중복 스킵")
                elif result_id:  # 숫자 ID가 반환되면 새로 저장된 것
                    print(" → 저장")
                    outputs.append({'url': url, 'title': result['title'], 'content': result['content']})
                else:
                    print(" → 오류")
            else:
                print(" → 키워드 없음")
        
        return {
            'status': 'success', 
            'board_url': board_url, 
            'count': len(outputs), 
            'items': outputs
        }



    def _print_title_and_content(self, title: str, content: str, url: str = ""):
        if url:
            print(f"URL: {url}")
        print(f"제목: {title}")
        print(f"본문: {content.strip()}")
        print("-" * 80)

def main():
    system = URLKeywordDetectionSystem()
    while True:
        print("\n" + "="*60)
        print("URL 키워드 탐지 시스템 ")
        print("="*60)
        print("1. 상세 페이지 분석 ")
        print("2. 게시판 전체 분석 ")
        print("3. 종료")
        print("="*60)
        choice = input("선택하세요 (1-3): ").strip()
        if choice == '1':
            test_url = input("분석할 상세 페이지 URL을 입력하세요: ").strip()
            system.analyze_url(test_url, print_result=True)
        elif choice == '2':
            board_url = input("분석할 게시판 URL을 입력하세요: ").strip()
            max_pages_input = input("최대 분석 페이지 수: ").strip()
            max_pages = int(max_pages_input) if max_pages_input.isdigit() else 5
            system.analyze_board(board_url, max_pages)
        elif choice == '3':
            print("종료합니다.")
            break
        else:
            print("1-3 중에서 선택해주세요.")

if __name__ == "__main__":
    main()
