"""
Constants used across the crawler module.
"""

# CSS 클래스 기반 노이즈 요소들
NOISE_CLASSES = [
    'sidebar', 'breadcrumbs', 'advert', 'ad', 'ads', 'tags', 'share', 'social',
    'menu', 'navigation', 'nav-menu', 'header-menu', 'footer-menu',
    'user-menu', 'my-shop', 'cart', 'order', 'login', 'signup',
    'company-info', 'contact-info', 'footer-info', 'copyright',
    'bank-info', 'customer-center', 'follow', 'sns',
    'pagination', 'paging', 'prev', 'next',
    'comment', 'reply', 'form', 'input-form', 'search-form',
    'footer', 'footer-wrap', 'footer-content', 'footer-area', 'site-footer',
    'page-footer', 'main-footer', 'bottom-footer', 'footer-section'
]

# ID 기반 노이즈 요소들
NOISE_IDS = ['header', 'footer', 'sidebar', 'navigation', 'menu', 'ads']

# 게시글 링크 선택자들 (범용)
POST_LINK_SELECTORS = [
    # K-Board 전용 선택자 (최우선)
    'td.kboard-list-title a',            # K-Board 제목 링크 (가장 정확)
    '.kboard-list-title a',              # K-Board 제목 링크 (백업)
    
    # 테이블 기반 게시판 구조
    'td.td_subject .bo_tit a',           # 그누보드 계열
    'td.subject.left.txtBreak a',        # 카페24 쇼핑몰 구조
    'td.subject a', '.title a', '.subject a',  # 일반적인 제목 구조
    
    # URL 패턴 기반 (더 구체적으로)
    'a[href*="mod=document"]',           # K-Board document 링크
    'a[href*="/article/"]',              # 아티클 링크
    'td a[href*="/article/"]',           # 테이블 내 아티클 링크
    'a[href*="view"]', 'a[href*="read"]', 'a[href*="detail"]', 'a[href*="post"]',
    
    # 백업 선택자 (페이지네이션 제외)
    'tbody a[href*="document"]',         # tbody 내 document 링크만
    'table a[href*="uid="]'              # uid 파라미터 포함 링크만
]

# 제목 추출 선택자들
TITLE_SELECTORS = [
    '.board-content .title',  # 게시판 제목 영역
    '.post-title',            # 게시글 제목
    '.article-title',         # 기사 제목
    'h1.subject',             # 제목 헤더
    '.subject',               # 제목 클래스
    'h1',                     # 일반 헤더
    'h2.title',               # 보조 제목
]


# 제거할 HTML 태그들
REMOVE_TAGS = ['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'noscript']

# 노이즈 텍스트 패턴들 (UI/시스템 관련만)
NOISE_TEXT_PATTERNS = [
    '로그인', '회원가입', '장바구니', '주문조회', '마이페이지',
    '사업자등록번호', '통신판매업신고번호', '개인정보보호책임자',
    'Customer Center', 'Bank Info', 'Follow',
    '평일 09:00', '점심 12:00', '토, 일, 공휴일 휴무',
    '결제완료 후 자동으로', '결제 진행 중에', '주문이 되지 않으니',
    '비밀번호', '확인', '취소', '댓글달기', '스팸신고', '스팸해제'
]

# 제목에서 제외할 노이즈 패턴들
TITLE_NOISE_PATTERNS = ['로그인', '회원가입', 'Q&A', 'notice']


# 불법 광고성 키워드 패턴들 (강력 필터링)
ILLEGAL_AD_PATTERNS = [
    '콜걸', '출장', '모텔', '조건', '애인대행', '마사지', '아가씨', '후불제',
    '만남', '외국인', '라인', 'xv999', '텔레그램', '카톡', '카카오톡'
]

# 반복되는 특수문자 패턴 (광고성 텍스트 특징)
SPAM_CHAR_PATTERNS = [
    'ㅣ', '〃', '＃', 'ヲ', 'U', '♥', '★', '☆', '♡', '◆', '◇', '■', '□'
]