import os
from dotenv import load_dotenv
from supabase import create_client
from openai import OpenAI

load_dotenv()

supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def check_similarity(query):
    """검색어와 모든 데이터의 유사도 확인"""
    
    print("=" * 70)
    print(f"검색어: {query}")
    print("=" * 70)
    
    # 1. 모든 데이터 가져오기
    print("\n1. 데이터베이스에서 데이터 가져오는 중...")
    result = supabase.table('government_projects').select('*').execute()
    
    if not result.data:
        print("데이터가 없습니다!")
        return
    
    print(f"   총 {len(result.data)}개 데이터 발견")
    
    # 2. 검색어 임베딩 생성
    print(f"\n2. '{query}' 임베딩 생성 중...")
    try:
        query_embedding = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=query
        ).data[0].embedding
        print(f"   임베딩 생성 완료 (차원: {len(query_embedding)})")
    except Exception as e:
        print(f"   오류: {e}")
        return
    
    # 3. 벡터 검색으로 유사도 확인
    print("\n3. 유사도 계산 중...")
    try:
        search_result = supabase.rpc(
            'match_government_projects',
            {
                'query_embedding': query_embedding,
                'match_threshold': 0.0,  # 모든 결과 반환
                'match_count': 1000  # 전체 조회
            }
        ).execute()
        
        if not search_result.data:
            print("\n⚠️ 검색 결과가 없습니다!")
            print("\n가능한 원인:")
            print("1. embedding 컬럼에 데이터가 없음")
            print("2. match_government_projects 함수에 문제가 있음")
            
            # embedding 확인
            print("\n4. embedding 컬럼 확인...")
            for idx, item in enumerate(result.data[:3], 1):
                has_embedding = item.get('embedding') is not None
                print(f"   {idx}. {item['title'][:50]}...")
                print(f"      embedding: {'있음' if has_embedding else '❌ 없음'}")
            
            return
        
        # 4. 유사도 순으로 정렬 및 출력
        print(f"\n총 {len(search_result.data)}개 결과")
        print("\n유사도 분포:")
        print("-" * 70)
        
        # 유사도 범위별 분류
        ranges = {
            '0.9 이상': 0,
            '0.8~0.9': 0,
            '0.7~0.8': 0,
            '0.6~0.7': 0,
            '0.5~0.6': 0,
            '0.5 미만': 0
        }
        
        for item in search_result.data:
            sim = item['similarity']
            if sim >= 0.9:
                ranges['0.9 이상'] += 1
            elif sim >= 0.8:
                ranges['0.8~0.9'] += 1
            elif sim >= 0.7:
                ranges['0.7~0.8'] += 1
            elif sim >= 0.6:
                ranges['0.6~0.7'] += 1
            elif sim >= 0.5:
                ranges['0.5~0.6'] += 1
            else:
                ranges['0.5 미만'] += 1
        
        for range_name, count in ranges.items():
            bar = '█' * int(count / len(search_result.data) * 50)
            print(f"{range_name}: {count:3d}개 {bar}")
        
        # 5. 상위 10개 결과 상세 출력
        print("\n\n상위 10개 과제:")
        print("=" * 70)
        
        for idx, item in enumerate(search_result.data[:10], 1):
            print(f"\n{idx}. 제목: {item['title']}")
            print(f"   기관: {item['organization']}")
            print(f"   유사도: {item['similarity']:.4f}")
            print(f"   태그: {item['tags']}")
            print(f"   설명: {item['description'][:80] if item['description'] else '없음'}...")
        
        # 6. 최하위 3개도 출력 (비교용)
        print("\n\n최하위 3개 과제 (비교용):")
        print("=" * 70)
        
        for idx, item in enumerate(search_result.data[-3:], 1):
            print(f"\n{idx}. 제목: {item['title']}")
            print(f"   유사도: {item['similarity']:.4f}")
        
        # 7. 권장 임계값 제안
        print("\n\n권장 설정:")
        print("=" * 70)
        
        if search_result.data:
            max_sim = search_result.data[0]['similarity']
            avg_sim = sum(item['similarity'] for item in search_result.data) / len(search_result.data)
            
            print(f"최고 유사도: {max_sim:.4f}")
            print(f"평균 유사도: {avg_sim:.4f}")
            
            if max_sim < 0.5:
                print(f"\n⚠️ 최고 유사도가 0.5 미만입니다!")
                print(f"권장 임계값: 0.2 ~ 0.3")
                print(f"\n가능한 원인:")
                print(f"- 검색어 '{query}'와 관련된 과제가 DB에 없음")
                print(f"- PDF 텍스트가 제대로 추출되지 않았음")
            elif max_sim < 0.7:
                print(f"\n권장 임계값: 0.3 ~ 0.4")
            else:
                print(f"\n권장 임계값: 0.5 ~ 0.6")
        
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 여러 검색어로 테스트
    queries = ["인공지능", "소상공인", "R&D", "지원사업"]
    
    for query in queries:
        check_similarity(query)
        print("\n" + "=" * 70)
        print()
        input("엔터를 눌러 다음 검색어로 계속...")