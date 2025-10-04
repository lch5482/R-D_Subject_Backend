import requests
from bs4 import BeautifulSoup
import os
import time
from datetime import datetime
from urllib.parse import urljoin
import re

class MSSCrawler:
    """중소벤처기업부 공고 크롤러 (페이지네이션 포함)"""
    
    def __init__(self, download_dir='downloads'):
        self.base_url = "https://www.mss.go.kr"
        self.list_url = "https://www.mss.go.kr/site/smba/ex/bbs/List.do"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.mss.go.kr/'
        }
        self.session = requests.Session()
        self.download_dir = download_dir
        
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
    
    def get_page(self, page_num=1, year='2025', month='00'):
        """특정 페이지 가져오기"""
        params = {
            'cbIdx': '310',
            'year': year,
            'month': month,
            'pageIndex': page_num
        }
        
        try:
            response = self.session.get(
                self.list_url,
                params=params,
                headers=self.headers,
                timeout=15
            )
            response.encoding = 'utf-8'
            return response.text
        except Exception as e:
            print(f"페이지 {page_num} 가져오기 오류: {e}")
            return None
    
    def get_total_pages(self, html):
        """전체 페이지 수 확인"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # "현재 페이지 : 1/184" 패턴 찾기
        list_info = soup.select_one('.list_info')
        if list_info:
            match = re.search(r'(\d+)/(\d+)', list_info.text)
            if match:
                return int(match.group(2))
        
        # 페이지네이션 링크에서 찾기
        pagination = soup.select('.pagination a.page-link')
        if pagination:
            last_page = 1
            for link in pagination:
                text = link.text.strip()
                if text.isdigit():
                    last_page = max(last_page, int(text))
            return last_page
        
        return 1
    
    def get_notice_list_with_files(self, html):
        """HTML에서 공고 목록과 첨부파일 정보 추출"""
        soup = BeautifulSoup(html, 'html.parser')
        notices = []
        
        rows = soup.select('table tbody tr')
        
        for row in rows:
            try:
                notice = {}
                
                # 번호
                num_td = row.select_one('td:nth-child(1)')
                notice['number'] = num_td.text.strip() if num_td else ''
                
                # 제목
                title_td = row.select_one('td.subject')
                if title_td:
                    title_link = title_td.select_one('a.pc-detail')
                    if title_link:
                        notice['title'] = title_link.text.strip()
                
                # 첨부파일 추출
                notice['attachments'] = []
                file_td = row.select_one('td.attached-files')
                if file_td:
                    file_spans = file_td.select('span.single-file')
                    for file_span in file_spans:
                        file_url = file_span.get('data-href')
                        if file_url:
                            if not file_url.startswith('http'):
                                file_url = self.base_url + file_url
                            
                            file_name = file_url.split('streFileNm=')[-1] if 'streFileNm=' in file_url else f'file_{len(notice["attachments"])}'
                            
                            notice['attachments'].append({
                                'name': file_name,
                                'url': file_url
                            })
                
                # 날짜
                date_td = row.select_one('td:nth-child(4)')
                notice['date'] = date_td.text.strip() if date_td else ''
                
                # 조회수
                view_td = row.select_one('td:nth-child(5)')
                notice['views'] = view_td.text.strip() if view_td else '0'
                
                notices.append(notice)
                
            except Exception as e:
                print(f"항목 파싱 오류: {e}")
                continue
        
        return notices
    
    def download_file(self, file_url, file_name, notice_folder):
        """파일 다운로드"""
        try:
            safe_filename = re.sub(r'[<>:"/\\|?*]', '_', file_name).strip()
            
            if '.' in safe_filename:
                base_name, ext = os.path.splitext(safe_filename)
            else:
                if '.hwp' in file_url:
                    ext = '.hwp'
                elif '.pdf' in file_url:
                    ext = '.pdf'
                elif '.xlsx' in file_url:
                    ext = '.xlsx'
                elif '.docx' in file_url:
                    ext = '.docx'
                elif '.hwpx' in file_url:
                    ext = '.hwpx'
                else:
                    ext = ''
                base_name = safe_filename
                safe_filename = base_name + ext
            
            file_path = os.path.join(notice_folder, safe_filename)
            
            if os.path.exists(file_path):
                print(f"    ⏭ 이미 존재: {safe_filename}")
                return file_path
            
            print(f"    ⬇ 다운로드 중: {safe_filename}")
            
            response = self.session.get(file_url, headers=self.headers, timeout=30, stream=True)
            
            content_disposition = response.headers.get('Content-Disposition', '')
            if content_disposition:
                if "filename*=" in content_disposition:
                    match = re.search(r"filename\*=UTF-8''(.+)", content_disposition)
                    if match:
                        from urllib.parse import unquote
                        real_filename = unquote(match.group(1))
                        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', real_filename).strip()
                        file_path = os.path.join(notice_folder, safe_filename)
                elif 'filename=' in content_disposition:
                    match = re.search(r'filename[^;=\n]*=["\']?([^"\';]+)', content_disposition)
                    if match:
                        from urllib.parse import unquote
                        real_filename = unquote(match.group(1))
                        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', real_filename).strip()
                        file_path = os.path.join(notice_folder, safe_filename)
            
            response.raise_for_status()
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(file_path)
            print(f"    ✓ 완료: {safe_filename} ({file_size:,} bytes)")
            
            return file_path
            
        except Exception as e:
            print(f"    ❌ 다운로드 실패: {e}")
            return None
    
    def crawl_and_download(self, max_pages=3, max_items_per_page=10, year='2025', month='00'):
        """페이지네이션 크롤링 및 다운로드"""
        print("=" * 70)
        print("중소벤처기업부 공고 크롤러 시작 (페이지네이션)")
        print("=" * 70)
        
        # 첫 페이지 가져오기
        html = self.get_page(1, year, month)
        if not html:
            print("첫 페이지를 가져올 수 없습니다.")
            return []
        
        # 전체 페이지 수 확인
        total_pages = self.get_total_pages(html)
        print(f"\n전체 페이지 수: {total_pages}")
        
        if max_pages:
            total_pages = min(total_pages, max_pages)
            print(f"크롤링할 페이지: {total_pages}페이지\n")
        
        all_notices = []
        
        # 각 페이지 크롤링
        for page_num in range(1, total_pages + 1):
            print(f"\n{'='*70}")
            print(f"[페이지 {page_num}/{total_pages}] 크롤링 중...")
            print('='*70)
            
            if page_num == 1:
                page_html = html
            else:
                page_html = self.get_page(page_num, year, month)
                time.sleep(1)
            
            if not page_html:
                print(f"⚠ 페이지 {page_num} 가져오기 실패")
                continue
            
            # 공고 목록 추출
            notices = self.get_notice_list_with_files(page_html)
            
            # 최대 개수 제한
            if max_items_per_page:
                notices = notices[:max_items_per_page]
            
            print(f"\n발견된 공고: {len(notices)}개\n")
            
            # 각 공고 처리
            for idx, notice in enumerate(notices, 1):
                print(f"[{idx}/{len(notices)}] {notice['title']}")
                print(f"  날짜: {notice['date']} | 조회: {notice['views']}")
                print(f"  첨부파일: {len(notice['attachments'])}개")
                
                if notice['attachments']:
                    # 폴더 생성
                    safe_title = re.sub(r'[<>:"/\\|?*]', '_', notice['title'])[:50]
                    notice_folder = os.path.join(
                        self.download_dir,
                        f"{notice['number']}_{safe_title}"
                    )
                    
                    if not os.path.exists(notice_folder):
                        os.makedirs(notice_folder)
                    
                    print(f"  💾 저장: {notice_folder}")
                    
                    # 파일 다운로드
                    for attachment in notice['attachments']:
                        self.download_file(
                            attachment['url'],
                            attachment['name'],
                            notice_folder
                        )
                        time.sleep(0.5)
                else:
                    print(f"  ℹ 첨부파일 없음")
                
                print()
            
            all_notices.extend(notices)
        
        print("\n" + "=" * 70)
        print(f"✅ 크롤링 완료!")
        print(f"총 {len(all_notices)}개 공고 처리")
        print(f"첨부파일 있는 공고: {len([n for n in all_notices if n['attachments']])}개")
        print(f"📁 다운로드 위치: {os.path.abspath(self.download_dir)}")
        print("=" * 70)
        
        return all_notices


if __name__ == "__main__":
    crawler = MSSCrawler(download_dir='mss_downloads')
    
    # 옵션 1: 최근 3페이지, 각 페이지당 5개 공고만
    results = crawler.crawl_and_download(
        max_pages=5,
        max_items_per_page=10,
        year='2025',
        month='00'
    )
    
    # 옵션 2: 전체 페이지, 각 페이지 전체 공고
    # results = crawler.crawl_and_download(
    #     max_pages=None,
    #     max_items_per_page=None,
    #     year='2025',
    #     month='00'
    # )