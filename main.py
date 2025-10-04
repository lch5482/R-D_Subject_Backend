from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
from openai import OpenAI
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime, date

# 환경변수 로드
load_dotenv()

# FastAPI 앱 생성
app = FastAPI(title="Government Projects Search API")

# CORS 설정 (프론트엔드에서 접근 가능하도록)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "https://your-app.vercel.app"],  # 프로덕션에서는 구체적인 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 클라이언트 초기화
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
supabase: Client = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_KEY')
)

# 응답 모델
class ProjectSearchResult(BaseModel):
    id: int
    title: str
    organization: str
    deadline: Optional[date]
    description: Optional[str]
    tags: List[str]
    similarity: float
    
class ProjectDetail(BaseModel):
    id: int
    title: str
    organization: str
    deadline: Optional[date]
    full_deadline: Optional[str]
    status: Optional[str]
    announcement_date: Optional[date]
    description: Optional[str]
    tags: List[str]
    overview: Optional[str]
    objectives: List[str]
    eligibility_target: Optional[str]
    eligibility_requirements: List[str]
    eligibility_restrictions: List[str]
    support_amount: Optional[str]
    support_details: List[str]
    source_file: Optional[str]

class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    threshold: float = 0.1

# 검색 함수
def create_embedding(text: str):
    """텍스트를 임베딩 벡터로 변환"""
    try:
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"임베딩 생성 오류: {e}")
        return None

# API 엔드포인트
@app.get("/")
def read_root():
    return {
        "message": "Government Projects Search API",
        "version": "1.0",
        "endpoints": {
            "search": "/api/search?q=검색어",
            "project": "/api/project/{id}",
            "recent": "/api/projects/recent"
        }
    }

@app.get("/api/search", response_model=List[ProjectSearchResult])
async def search_projects(
    q: str = Query(..., description="검색 쿼리"),
    limit: int = Query(10, ge=1, le=50, description="결과 개수"),
    threshold: float = Query(0.2, ge=0.0, le=1.0, description="유사도 임계값")
):
    try:
        query_embedding = create_embedding(q)
        if not query_embedding:
            raise HTTPException(status_code=500, detail="임베딩 생성 실패")
        
        result = supabase.rpc(
            'hybrid_search_projects',
            {
                'query_text': q,
                'query_embedding': query_embedding,
                'match_threshold': threshold,  # 이 줄 추가됨
                'match_count': limit
            }
        ).execute()
        
        filtered_results = [
            ProjectSearchResult(**item) 
            for item in result.data
        ]
        
        return filtered_results
        
    except Exception as e:
        print(f"검색 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/project/{project_id}", response_model=ProjectDetail)
async def get_project_detail(project_id: int):
    """
    특정 과제의 상세 정보 조회
    
    - **project_id**: 과제 ID
    """
    try:
        result = supabase.table('government_projects')\
            .select('*')\
            .eq('id', project_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="과제를 찾을 수 없습니다")
        
        # 배열 필드가 None일 경우 빈 배열로 변환
        project = result.data[0]
        project['tags'] = project.get('tags') or []
        project['objectives'] = project.get('objectives') or []
        project['eligibility_requirements'] = project.get('eligibility_requirements') or []
        project['eligibility_restrictions'] = project.get('eligibility_restrictions') or []
        project['support_details'] = project.get('support_details') or []
        
        return ProjectDetail(**project)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"상세 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/projects/recent", response_model=List[ProjectSearchResult])
async def get_recent_projects(limit: int = Query(10, ge=1, le=50)):
    """
    최근 공고된 과제 목록
    
    - **limit**: 반환할 결과 수
    """
    try:
        result = supabase.table('government_projects')\
            .select('id, title, organization, deadline, description, tags')\
            .order('created_at', desc=True)\
            .limit(limit)\
            .execute()
        
        # similarity 필드 추가 (최근 과제이므로 1.0)
        projects = []
        for item in result.data:
            item['similarity'] = 1.0
            item['tags'] = item.get('tags') or []
            projects.append(ProjectSearchResult(**item))
        
        return projects
        
    except Exception as e:
        print(f"최근 과제 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/projects/filter")
async def filter_projects(
    organization: Optional[str] = None,
    tag: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(20, ge=1, le=50)
):
    """
    필터링 검색
    
    - **organization**: 기관명
    - **tag**: 태그
    - **status**: 상태
    """
    try:
        query = supabase.table('government_projects')\
            .select('id, title, organization, deadline, description, tags, status')
        
        if organization:
            query = query.ilike('organization', f'%{organization}%')
        
        if status:
            query = query.eq('status', status)
        
        if tag:
            query = query.contains('tags', [tag])
        
        result = query.order('created_at', desc=True).limit(limit).execute()
        
        projects = []
        for item in result.data:
            item['similarity'] = 1.0
            item['tags'] = item.get('tags') or []
            projects.append(ProjectSearchResult(**item))
        
        return projects
        
    except Exception as e:
        print(f"필터링 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_stats():
    """전체 통계"""
    try:
        # 전체 과제 수
        total = supabase.table('government_projects').select('id', count='exact').execute()
        
        # 기관별 통계
        orgs = supabase.table('government_projects')\
            .select('organization')\
            .execute()
        
        org_count = {}
        for item in orgs.data:
            org = item['organization']
            org_count[org] = org_count.get(org, 0) + 1
        
        return {
            "total_projects": total.count,
            "organizations": len(org_count),
            "top_organizations": sorted(org_count.items(), key=lambda x: x[1], reverse=True)[:5]
        }
        
    except Exception as e:
        print(f"통계 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 서버 실행
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)