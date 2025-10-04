import os
import json
from openai import OpenAI
from supabase import create_client, Client
import PyPDF2
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv



class SupabaseVectorStorage:
    """PDF를 임베딩하여 Supabase에 저장"""
    
    def __init__(self, openai_api_key, supabase_url, supabase_key):
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.supabase: Client = create_client(supabase_url, supabase_key)
    
    def extract_text_from_pdf(self, pdf_path):
        """PDF에서 텍스트 추출"""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text.strip()
        except Exception as e:
            print(f"PDF 읽기 오류: {e}")
            return None
    
    def extract_metadata(self, pdf_text, pdf_filename):
        """OpenAI API로 메타데이터 추출"""
        
        prompt = f"""
다음은 정부 과제 공고문입니다. 이 내용을 분석하여 JSON 형식으로 메타데이터를 추출해주세요.

공고문 내용:
{pdf_text[:15000]}

다음 JSON 형식으로 추출해주세요:

{{
  "title": "과제명",
  "organization": "주관기관명",
  "deadline": "접수 마감일 (YYYY-MM-DD 형식)",
  "fullDeadline": "전체 사업기간",
  "status": "접수중",
  "date": "공고일 (YYYY-MM-DD 형식)",
  "description": "과제 한줄 설명 (100자 이내)",
  "tags": ["태그1", "태그2", "태그3"],
  "overview": "사업 개요 (300자 이내)",
  "objectives": ["목표1", "목표2"],
  "eligibility_target": "지원 대상",
  "eligibility_requirements": ["자격요건1", "자격요건2"],
  "eligibility_restrictions": ["제외대상1"],
  "support_amount": "지원금액 요약",
  "support_details": ["지원내역1", "지원내역2"]
}}

중요:
- 문서에 없는 정보는 null로 표시
- 날짜는 YYYY-MM-DD 형식
- tags는 #없이 키워드만 (예: "인공지능", "R&D")
- 유효한 JSON만 응답
"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # 비용 절감
                messages=[
                    {
                        "role": "system", 
                        "content": "정부 과제 공고문을 분석하여 구조화된 메타데이터를 추출합니다. 반드시 유효한 JSON만 응답하세요."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            metadata = json.loads(response.choices[0].message.content)
            metadata['source_file'] = pdf_filename
            
            return metadata
            
        except Exception as e:
            print(f"메타데이터 추출 오류: {e}")
            return None
    
    def create_embedding(self, text):
        """텍스트를 임베딩 벡터로 변환"""
        try:
            # 텍스트가 너무 길면 잘라냄 (8000자)
            text = text[:8000]
            
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            print(f"임베딩 생성 오류: {e}")
            return None
    
    def store_to_supabase(self, text, metadata, embedding):
        """Supabase에 저장"""
        try:
            # 메타데이터를 평탄화하여 개별 컬럼으로 저장
            data = {
                'content': text[:5000],  # 원본 텍스트 일부
                'embedding': embedding,
                'title': metadata.get('title'),
                'organization': metadata.get('organization'),
                'deadline': metadata.get('deadline'),
                'full_deadline': metadata.get('fullDeadline'),
                'status': metadata.get('status'),
                'announcement_date': metadata.get('date'),
                'description': metadata.get('description'),
                'tags': metadata.get('tags', []),
                'overview': metadata.get('overview'),
                'objectives': metadata.get('objectives', []),
                'eligibility_target': metadata.get('eligibility_target'),
                'eligibility_requirements': metadata.get('eligibility_requirements', []),
                'eligibility_restrictions': metadata.get('eligibility_restrictions', []),
                'support_amount': metadata.get('support_amount'),
                'support_details': metadata.get('support_details', []),
                'source_file': metadata.get('source_file'),
                'created_at': datetime.now().isoformat()
            }
            
            result = self.supabase.table('government_projects').insert(data).execute()
            
            return result.data[0] if result.data else None
            
        except Exception as e:
            print(f"Supabase 저장 오류: {e}")
            return None
    
    def process_pdf_file(self, pdf_path):
        """PDF 파일 하나를 처리하여 Supabase에 저장"""
        print(f"\n처리 중: {os.path.basename(pdf_path)}")
        
        # 1. PDF에서 텍스트 추출
        text = self.extract_text_from_pdf(pdf_path)
        if not text:
            print("  ❌ 텍스트 추출 실패")
            return None
        
        print(f"  ✓ 텍스트 추출 완료 ({len(text)} 글자)")
        
        # 2. 메타데이터 추출
        filename = os.path.basename(pdf_path)
        metadata = self.extract_metadata(text, filename)
        
        if not metadata:
            print("  ❌ 메타데이터 추출 실패")
            return None
        
        print(f"  ✓ 메타데이터 추출 완료")
        print(f"    제목: {metadata.get('title', 'N/A')[:50]}...")
        
        # 3. 임베딩 생성
        embedding = self.create_embedding(text)
        
        if not embedding:
            print("  ❌ 임베딩 생성 실패")
            return None
        
        print(f"  ✓ 임베딩 생성 완료 (차원: {len(embedding)})")
        
        # 4. Supabase에 저장
        result = self.store_to_supabase(text, metadata, embedding)
        
        if result:
            print(f"  ✅ Supabase 저장 완료 (ID: {result.get('id')})")
            return result
        else:
            print("  ❌ Supabase 저장 실패")
            return None
    
    def process_directory(self, directory_path):
        """폴더 내의 모든 PDF 파일 처리"""
        print("=" * 70)
        print("PDF 벡터화 및 Supabase 저장 시작")
        print("=" * 70)
        
        pdf_files = []
        
        # 모든 PDF 파일 찾기
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if file.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(root, file))
        
        print(f"\n총 {len(pdf_files)}개의 PDF 파일 발견\n")
        
        success_count = 0
        
        # 각 PDF 파일 처리
        for idx, pdf_path in enumerate(pdf_files, 1):
            print(f"[{idx}/{len(pdf_files)}]")
            
            result = self.process_pdf_file(pdf_path)
            
            if result:
                success_count += 1
            
            print()
        
        print("=" * 70)
        print(f"완료! {success_count}/{len(pdf_files)}개 파일 처리 성공")
        print("=" * 70)
        
        return success_count


def main():
    """메인 실행 함수"""
    load_dotenv()  # .env 파일에서 환경변수 로드
    
    # API 키 설정
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    
    # 스토리지 생성
    storage = SupabaseVectorStorage(
        openai_api_key=OPENAI_API_KEY,
        supabase_url=SUPABASE_URL,
        supabase_key=SUPABASE_KEY
    )
    
    # 다운로드 폴더 경로
    download_dir = 'mss_downloads'
    
    if not os.path.exists(download_dir):
        print(f"❌ 폴더를 찾을 수 없습니다: {download_dir}")
        return
    
    # PDF 파일 처리 및 저장
    storage.process_directory(download_dir)


if __name__ == "__main__":
    main()