import streamlit as st
from google import genai
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import isodate 
import socket
import re

# ==========================================
# [버전 정보] V8.9 - 영상 지식 정보 기반 포스팅 강화 및 출처 분리
# ==========================================
VERSION = "V8.9"

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
YOUTUBE_API_KEY = st.secrets["YOUTUBE_API_KEY"]

socket.setdefaulttimeout(30)

st.set_page_config(page_title=f"AI 유튜브 작가 {VERSION}", layout="wide")

st.title("📹 유튜브 기반 지식 정보 블로그 생성기")
st.write(f"**Version: {VERSION} (지식 정보 요약 강화)**")

if 'search_results' not in st.session_state:
    st.session_state.search_results = []

st.markdown("### ⚙️ 1단계: 검색 설정")
col_opt1, col_opt2, col_opt3 = st.columns([1, 1, 1])
with col_opt1:
    length_option = st.select_slider("📝 목표 글자 수", options=[500, 1000, 2000], value=1000)
with col_opt2:
    start_date = st.date_input("📅 검색 시작일", datetime.now() - timedelta(days=60))
with col_opt3:
    end_date = st.date_input("📅 검색 종료일", datetime.now())

input_data = st.text_input("검색어를 입력하세요 (예: 커피의 효능)", placeholder="검색어에 대한 지식 정보를 3개 영상에서 찾아드려요.")

if st.button("🔍 유튜브 영상 목록 불러오기"):
    if not YOUTUBE_API_KEY:
        st.warning("유튜브 API 키를 확인해 주세요!")
    elif not input_data:
        st.warning("검색어를 입력해 주세요!")
    else:
        try:
            youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
            rfc_start_date = start_date.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            search_res = youtube.search().list(
                q=f"{input_data} -shorts", part='id,snippet', maxResults=30, 
                type='video', order='relevance', 
                relevanceLanguage='ko', regionCode='KR',
                publishedAfter=rfc_start_date
            ).execute().get('items', [])
            
            results = []
            seen_titles = set()
            channel_counts = {}

            for v in search_res:
                v_id = v['id']['videoId']
                v_title = v['snippet']['title']
                channel_id = v['snippet']['channelId']
                
                clean_title = re.sub(r'[^가-힣A-Za-z0-9]', '', v_title)
                title_key = clean_title[:15]
                if title_key in seen_titles: continue
                if channel_counts.get(channel_id, 0) >= 2: continue
                
                v_info = youtube.videos().list(part='contentDetails', id=v_id).execute()
                duration_raw = v_info['items'][0]['contentDetails']['duration']
                duration_sec = isodate.parse_duration(duration_raw).total_seconds()
                
                if duration_sec > 60: 
                    results.append({
                        "id": v_id, "title": v_title, "url": f"https://www.youtube.com/watch?v={v_id}"
                    })
                    seen_titles.add(title_key)
                    channel_counts[channel_id] = channel_counts.get(channel_id, 0) + 1
            
            st.session_state.search_results = results
            st.success(f"'{input_data}'에 대한 결과 {len(results)}개를 찾았어요! 확인 후 골라주세요. 😊")
        except Exception as e:
            st.error(f"검색 오류: {e}")

if st.session_state.search_results:
    st.markdown("---")
    st.markdown("### 📋 2단계: 영상 확인 및 선택 (최대 3개)")
    
    selected_indices = []
    for i, item in enumerate(st.session_state.search_results[:15]):
        col_check, col_link = st.columns([5, 1])
        with col_check:
            if st.checkbox(f"{i+1}. {item['title']}", key=f"v89_check_{item['id']}"):
                selected_indices.append(i)
        with col_link:
            st.markdown(f"[📺 확인]({item['url']})")
    
    st.markdown("---")
    if st.button("✍️ 선택한 영상 기반 블로그 생성하기"):
        if not selected_indices:
            st.warning("영상을 선택해 주세요!")
        else:
            selected_videos = [st.session_state.search_results[idx] for idx in selected_indices]
            try:
                client = genai.Client(api_key=GEMINI_API_KEY)
                with st.spinner("선택하신 영상 속 지식을 모아 알찬 포스팅을 작성 중이에요... 💖"):
                    video_context = ""
                    for i, v in enumerate(selected_videos):
                        video_context += f"[영상{i+1}]\n제목: {v['title']}\n링크: {v['url']}\n\n"
                    
                    # 지식 전달 중심의 프롬프트로 대폭 수정
                    final_prompt = f"""
                    [페르소나: 7.4 버전의 다정하지만 전문적인 정보 전달 블로거]
                    - 말투: "사랑하는 이웃님들!"로 시작, "~해요", "~했답니다" 등 다정한 파워블로거 톤 유지.
                    - 미션: 사용자가 검색한 '{input_data}'에 대하여, 제공된 영상들이 공통적으로 말하는 정보와 각 영상만의 꿀팁을 분석해서 정리할 것.
                    
                    [제공된 영상 정보]
                    {video_context}
                    
                    [블로그 구성 규칙]
                    1. 도입: "{input_data}"에 대해 궁금해하는 이웃님들을 위한 따뜻한 인사.
                    2. 본문: 단순한 감상이 아니라, 각 영상에서 언급된 구체적인 지식(예: 효능 3가지, 주의사항 등)을 요약하여 정보성 있게 작성.
                    3. 결론: 내용을 종합하여 독자들에게 주는 실질적인 조언.
                    4. 하단(출처): "📍 함께 보면 행복해지는 오늘의 영상 출처" 섹션을 만들어 영상 제목과 링크를 리스트로 남길 것.
                    
                    글자 수: {length_option}자 내외, 이모지 활용.
                    """
                    final_result = client.models.generate_content(model="gemini-2.5-flash", contents=final_prompt)
                    
                    st.success("✅ 지식이 가득 담긴 7.4 감성 포스팅 완성!")
                    st.markdown(final_result.text)
                    st.download_button("📂 포스팅 저장하기", final_result.text, file_name="knowledge_blog.txt")
            except Exception as e:

                st.error(f"생성 중 오류: {e}")
