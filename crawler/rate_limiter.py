# import time
# import json
# import os
# from datetime import datetime, timedelta
# from typing import Dict, Optional

# class RateLimiter:
#     """
#     API 요청 레이트 리미터 - 일일/시간별 할당량 관리
#     """
    
#     def __init__(self, quota_file: str = "api_quota.json"):
#         self.quota_file = quota_file
#         self.daily_limit = 100
#         self.hourly_limit = 10
#         self.load_quota_data()
        
#     def load_quota_data(self) -> None:
#         """할당량 데이터 로드"""
#         try:
#             if os.path.exists(self.quota_file):
#                 with open(self.quota_file, 'r') as f:
#                     self.quota_data = json.load(f)
#             else:
#                 self.quota_data = {
#                     'daily_count': 0,
#                     'hourly_count': 0,
#                     'last_reset_date': datetime.now().strftime('%Y-%m-%d'),
#                     'last_reset_hour': datetime.now().strftime('%Y-%m-%d %H')
#                 }
#         except Exception:
#             self.quota_data = {
#                 'daily_count': 0,
#                 'hourly_count': 0,
#                 'last_reset_date': datetime.now().strftime('%Y-%m-%d'),
#                 'last_reset_hour': datetime.now().strftime('%Y-%m-%d %H')
#             }
    
#     def save_quota_data(self) -> None:
#         """할당량 데이터 저장"""
#         try:
#             with open(self.quota_file, 'w') as f:
#                 json.dump(self.quota_data, f, indent=2)
#         except Exception as e:
#             print(f"할당량 데이터 저장 실패: {e}")
    
#     def reset_if_needed(self) -> None:
#         """필요시 할당량 리셋"""
#         now = datetime.now()
#         current_date = now.strftime('%Y-%m-%d')
#         current_hour = now.strftime('%Y-%m-%d %H')
        
#         # 일일 리셋
#         if self.quota_data['last_reset_date'] != current_date:
#             self.quota_data['daily_count'] = 0
#             self.quota_data['last_reset_date'] = current_date
            
#         # 시간별 리셋
#         if self.quota_data['last_reset_hour'] != current_hour:
#             self.quota_data['hourly_count'] = 0
#             self.quota_data['last_reset_hour'] = current_hour
    
#     def can_make_request(self) -> tuple[bool, str]:
#         """요청 가능 여부 확인"""
#         self.reset_if_needed()
        
#         if self.quota_data['daily_count'] >= self.daily_limit:
#             return False, "일일 할당량 초과"
            
#         if self.quota_data['hourly_count'] >= self.hourly_limit:
#             return False, "시간당 할당량 초과"
            
#         return True, "요청 가능"
    
#     def record_request(self) -> None:
#         """요청 기록"""
#         self.quota_data['daily_count'] += 1
#         self.quota_data['hourly_count'] += 1
#         self.save_quota_data()
    
#     def get_quota_status(self) -> Dict:
#         """현재 할당량 상태 반환"""
#         self.reset_if_needed()
#         return {
#             'daily_used': self.quota_data['daily_count'],
#             'daily_limit': self.daily_limit,
#             'daily_remaining': self.daily_limit - self.quota_data['daily_count'],
#             'hourly_used': self.quota_data['hourly_count'],
#             'hourly_limit': self.hourly_limit,
#             'hourly_remaining': self.hourly_limit - self.quota_data['hourly_count']
#         }

# class APIKeyManager:
#     """
#     API 키 관리 및 보안
#     """
    
#     @staticmethod
#     def validate_api_key(api_key: str) -> bool:
#         """API 키 유효성 검사"""
#         if not api_key or len(api_key) < 20:
#             return False
#         return True
    
#     @staticmethod
#     def mask_api_key(api_key: str) -> str:
#         """API 키 마스킹 (로그용)"""
#         if not api_key:
#             return "None"
#         return api_key[:8] + "*" * (len(api_key) - 12) + api_key[-4:] if len(api_key) > 12 else api_key[:4] + "*****"
    
#     @staticmethod
#     def check_api_credentials() -> tuple[bool, str]:
#         """API 자격증명 확인"""
#         from config.settings import GOOGLE_API_KEY, GOOGLE_CX
        
#         if not GOOGLE_API_KEY:
#             return False, "Google API Key가 설정되지 않음"
            
#         if not GOOGLE_CX:
#             return False, "Google Custom Search Engine ID가 설정되지 않음"
            
#         if not APIKeyManager.validate_api_key(GOOGLE_API_KEY):
#             return False, "유효하지 않은 API Key 형식"
            
#         return True, "API 자격증명 정상"