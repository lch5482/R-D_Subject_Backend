import requests
import json

BASE_URL = "http://localhost:8000"

def test_search(query):
    """검색 테스트"""
    print(f"\n{'='*70}")
    print(f"검색어: {query}")
    print('='*70)
    
    response = requests.get(
        f"{BASE_URL}/api/search",
        params={"q": query, "limit": 5}
    )
    
    if response.status_code == 200:
        results = response.json()
        print(f"\n찾은 과제: {len(results)}개\n")
        
        for idx, project in enumerate(results, 1):
            print(f"{idx}. {project['title']}")
            print(f"   기관: {project['organization']}")
            print(f"   마감: {project['deadline']}")
            print(f"   유사도: {project['similarity']:.3f}")
            print(f"   태그: {', '.join(project['tags'])}")
            print(f"   설명: {project['description'][:100]}..." if project['description'] else "   설명: 없음")
            print()
    else:
        print(f"오류: {response.status_code}")
        print(response.text)

def test_project_detail(project_id):
    """상세 정보 테스트"""
    print(f"\n{'='*70}")
    print(f"과제 상세 정보 (ID: {project_id})")
    print('='*70)
    
    response = requests.get(f"{BASE_URL}/api/project/{project_id}")
    
    if response.status_code == 200:
        project = response.json()
        
        print(f"\n제목: {project['title']}")
        print(f"기관: {project['organization']}")
        print(f"마감일: {project['deadline']}")
        print(f"상태: {project['status']}")
        print(f"\n개요:\n{project['overview']}")
        print(f"\n목표:")
        for obj in project['objectives']:
            print(f"  - {obj}")
        print(f"\n지원 대상: {project['eligibility_target']}")
        print(f"\n지원 금액: {project['support_amount']}")
        print(f"\n지원 내역:")
        for detail in project['support_details']:
            print(f"  - {detail}")
    else:
        print(f"오류: {response.status_code}")
        print(response.text)

def test_recent_projects():
    """최근 과제 테스트"""
    print(f"\n{'='*70}")
    print("최근 공고된 과제")
    print('='*70)
    
    response = requests.get(f"{BASE_URL}/api/projects/recent", params={"limit": 5})
    
    if response.status_code == 200:
        projects = response.json()
        print(f"\n총 {len(projects)}개\n")
        
        for idx, project in enumerate(projects, 1):
            print(f"{idx}. {project['title']}")
            print(f"   기관: {project['organization']}")
            print(f"   마감: {project['deadline']}")
            print()
    else:
        print(f"오류: {response.status_code}")

def test_filter():
    """필터링 테스트"""
    print(f"\n{'='*70}")
    print("필터링 검색 (조건: 과학기술정보통신부)")
    print('='*70)
    
    response = requests.get(
        f"{BASE_URL}/api/projects/filter",
        params={"organization": "과학기술정보통신부", "limit": 5}
    )
    
    if response.status_code == 200:
        projects = response.json()
        print(f"\n총 {len(projects)}개\n")
        
        for idx, project in enumerate(projects, 1):
            print(f"{idx}. {project['title']}")
            print(f"   기관: {project['organization']}")
            print()
    else:
        print(f"오류: {response.status_code}")

def test_stats():
    """통계 테스트"""
    print(f"\n{'='*70}")
    print("전체 통계")
    print('='*70)
    
    response = requests.get(f"{BASE_URL}/api/stats")
    
    if response.status_code == 200:
        stats = response.json()
        print(f"\n총 과제 수: {stats['total_projects']}")
        print(f"기관 수: {stats['organizations']}")
        print(f"\n상위 기관:")
        for org, count in stats['top_organizations']:
            print(f"  {org}: {count}개")
    else:
        print(f"오류: {response.status_code}")

if __name__ == "__main__":
    print("=" * 70)
    print("Government Projects Search API 테스트")
    print("=" * 70)
    
    # 1. 검색 테스트
    test_search("인공지능")
    test_search("소상공인 지원")
    
    # 2. 최근 과제
    test_recent_projects()
    
    # 3. 상세 정보 (첫 번째 과제 ID 사용)
    test_project_detail(1)
    
    # 4. 필터링
    test_filter()
    
    # 5. 통계
    test_stats()