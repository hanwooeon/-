import os
import json
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드 (프로젝트 루트에서)
PROJECT_ROOT = Path(__file__).parent.parent  # config의 상위 디렉토리
ENV_PATH = PROJECT_ROOT / '.env'
load_dotenv(ENV_PATH)

# 현재 디렉토리 경로
CONFIG_DIR = Path(__file__).parent

# 크롤링 설정
CRAWL_TIMEOUT = int(os.getenv('CRAWL_TIMEOUT', '30'))
CRAWL_DELAY = float(os.getenv('CRAWL_DELAY', '1.0'))
MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_BYTES', '1000000'))  # 1MB

# 데이터베이스 설정 (PostgreSQL)
DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'port': os.getenv('DB_PORT', '5432')
}

def load_json_config(filename: str) -> dict:
    """JSON 설정 파일을 로드하는 헬퍼 함수"""
    config_path = CONFIG_DIR / filename
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"설정 파일을 찾을 수 없습니다: {config_path}")
        return {}
    except json.JSONDecodeError as e:
        print(f"JSON 파일 파싱 오류: {e}")
        return {}

# 키워드 로딩 방식 선택 (DB 우선, JSON 대체)
def load_keywords_from_db():
    """데이터베이스에서 키워드 로드"""
    try:
        from database.connection import DatabaseManager
        db_manager = DatabaseManager()
        keywords_data = db_manager.get_keywords()
        
        illegal_keywords = {}
        for keyword_row in keywords_data:
            if len(keyword_row) >= 3:
                # id, category, keyword (3개 컬럼)
                _, category, keyword = keyword_row
                if category not in illegal_keywords:
                    illegal_keywords[category] = []
                illegal_keywords[category].append(keyword)
        
        return illegal_keywords
    except Exception as e:
        print(f" DB에서 키워드 로드 실패: {e}")
        return {}

def initialize_keywords_from_json():
    """JSON 파일의 키워드를 DB로 초기화"""
    try:
        from database.connection import DatabaseManager
        _keywords_filename = os.getenv('ILLEGAL_KEYWORDS_FILE', 'illegal_keywords.json')
        _illegal_keywords_config = load_json_config(_keywords_filename)
        
        if _illegal_keywords_config:
            db_manager = DatabaseManager()
            keywords_data = _illegal_keywords_config.get('illegal_keywords', {})
            
            db_manager.insert_keywords(keywords_data)
            print("JSON 키워드가 DB로 초기화되었습니다")
            return True
    except Exception as e:
        print(f"SON 키워드 DB 초기화 실패: {e}")
    return False

# 키워드 로딩 (DB 우선, JSON과 동기화 체크)
ILLEGAL_KEYWORDS = load_keywords_from_db()
if not ILLEGAL_KEYWORDS:
    print("DB에 키워드가 없습니다. JSON에서 초기화합니다...")
    if initialize_keywords_from_json():
        ILLEGAL_KEYWORDS = load_keywords_from_db()
else:
    # DB에 키워드가 있어도 JSON과 동기화 체크
    try:
        import json
        config_path = CONFIG_DIR / 'illegal_keywords.json'
        with open(config_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
            json_keywords = json_data.get('illegal_keywords', {})
            
            # JSON 키워드 수와 DB 키워드 수 비교로 간단히 체크
            json_count = sum(len(keywords) for keywords in json_keywords.values())
            db_count = sum(len(keywords) for keywords in ILLEGAL_KEYWORDS.values())
            
            if json_count != db_count:
                print(f"키워드 개수 불일치 감지 (JSON:{json_count}, DB:{db_count}). 동기화 실행...")
                from database.connection import DatabaseManager
                db_manager = DatabaseManager()
                db_manager.insert_keywords(json_keywords)
                ILLEGAL_KEYWORDS = load_keywords_from_db()
                print("JSON-DB 키워드 동기화 완료")
    except Exception as e:
        print(f"JSON-DB 동기화 체크 중 오류: {e}")

# 설정 검증 함수
def validate_config():
    """필수 설정값들이 제대로 로드되었는지 확인"""
    missing_configs = []
    
    if not ILLEGAL_KEYWORDS:
        missing_configs.append("불법 키워드 설정")
    
    if missing_configs:
        print("누락된 설정:")
        for config in missing_configs:
            print(f"  - {config}")
        return False
    
    print("모든 설정이 정상적으로 로드되었습니다.")
    return True

# 설정 요약 출력 함수
def print_config_summary():
    """현재 로드된 설정 요약 출력"""
    print("\n설정 요약:")
    print(f"- 불법 키워드 카테고리: {len(ILLEGAL_KEYWORDS)}개")
    print(f"- 크롤링 타임아웃: {CRAWL_TIMEOUT}초")
    print(f"- 크롤링 지연시간: {CRAWL_DELAY}초")
    print(f"- 데이터베이스: {DATABASE_CONFIG['database']}")

# 모듈 로드 시 자동 검증
if __name__ == "__main__":
    validate_config()
    print_config_summary()