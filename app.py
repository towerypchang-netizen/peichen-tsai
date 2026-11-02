import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import xml.etree.ElementTree as ET

# 1. 頁面基礎配置
st.set_page_config(
    page_title="蔡佩呈 - 泰山區選情即時看板與戰略分析",
    page_icon="🗳️",
    layout="wide"
)

# 標題與數據透明度提示
st.title("🗳️ 新北市議員參選人【蔡佩呈】即時選情與戰略分析看板")
st.caption("聚焦泰山・五股・新莊・林口選區 | 數據來源：Google News 即時 RSS & 競選團隊內部研判")
st.warning("⚠️ 數據提示：本系統「即時新聞情報」為真實 API 自動抓取；「選情指標與 SWOT 分析」為競選團隊內部研判參數，非 AI 杜撰內容。")

# 2. 側邊欄：新聞與輿情設定
st.sidebar.header("⚙️ 即時新聞數據源設定")
search_keyword = st.sidebar.text_input("輸入監測關鍵字", "蔡佩呈 泰山")
rss_limit = st.sidebar.slider("顯示新聞筆數", min_value=5, max_value=20, value=10)
refresh_btn = st.sidebar.button("🔄 重新整理新聞數據")

# 3. 真實 Google News RSS 抓取函式（嚴格避免 AI 杜撰假消息）
@st.cache_data(ttl=1800)  # 快取 30 分鐘，避免頻繁請求
def fetch_real_google_news(keyword):
    url = f"https://news.google.com/rss/search?q={keyword}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        
        articles = []
        for item in root.findall('.//item'):
            title = item.find('title').text if item.find('title') is not None else "無標題"
            link = item.find('link').text if item.find('link') is not None else ""
            pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
            
            articles.append({
                "標題": title,
                "新聞連結": link,
                "發布時間": pub_date
            })
            
        return pd.DataFrame(articles)
    except Exception as e:
        # 發生錯誤或無網路時，回傳空表格，絕不撰寫假新聞
        return pd.DataFrame(columns=["標題", "新聞連結", "發布時間"])

# 載入新聞資料
news_df = fetch_real_google_news(search_keyword)

# 4. 主介面分頁
tab1, tab2, tab3 = st.tabs(["📰 即時真實新聞情報", "🎯 SWOT 戰略矩陣", "📊 團隊選情評估指標"])

# TAB 1: 即時真實新聞情報
with tab1:
    st.subheader(f"📡 Google News 即時輿情監測（關鍵字：{search_keyword}）")
    
    if news_df.empty:
        st.info("ℹ️ 目前未抓取到相關新聞，或網路連線暫時中斷，請確認搜尋關鍵字或點擊側邊欄重新整理。")
    else:
        st.success(f"成功擷取到 {len(news_df)} 則最新真實新聞：")
        for idx, row in news_df.head(rss_limit).iterrows():
            with st.expander(f"📌 {row['標題']}"):
                st.write(f"**發布時間**：{row['發布時間']}")
                st.write(f"**閱讀原文**：[{row['新聞連結']}]({row['新聞連結']})")

# TAB 2: SWOT 戰略分析矩陣
with tab2:
    st.subheader("💡 蔡佩呈 SWOT 競選戰略分析")
    st.caption("分析基於：蔡佩呈之十年議員服務處主任經驗、泰山在地深耕及三寶媽家庭形象。")

    col_s, col_w = st.columns(2)
    with col_s:
        st.success("### 💪 S (Strengths) 內部優勢\n"
                   "- **深耕泰山 10 年**：長期擔任服務處主任，掌握泰山各里基層網絡與區公所運作機制。\n"
                   "- **親和力與三寶媽形象**：精準吸引年輕父母、婦幼團體與家庭選民。\n"
                   "- **服務實績明確**：具備拆除路口視線盲點牆體等有感地方建設實績。")
    
    with col_w:
        st.warning("### ⚠️ W (Weaknesses) 內部劣勢\n"
                   "- **個人品牌轉換期**：需將過去「服務處主任」的背後功臣形象，全面轉換為「蔡佩呈」個人參選品牌。\n"
                   "- **跨區知名度**：在泰山基本盤穩固，但在五股、新莊等延伸選區仍需擴大聲量。")

    col_o, col_t = st.columns(2)
    with col_o:
        st.info("### 🚀 O (Opportunities) 外部機會\n"
                "- **塭仔圳重劃區人口遷入**：大量年輕新家庭進駐，對托育、幼教與公園設施需求強烈。\n"
                "- **交通建設議題高熱度**：泰山民眾高度關注五泰輕軌、泰板輕軌及道路安全改善。")
    
    with col_t:
        st.error("### 🛡️ T (Threats) 外部威脅\n"
                 "- **選區競爭激烈**：同選區有多位新人參選，搶奪青年與中間選民。\n"
                 "- **重大施工陣痛期**：重劃區與交通工程施工期長，易引發周邊居民交通抱怨。")

    st.markdown("---")
    st.subheader("🎯 SWOT 交叉應戰策略 (TOWS)")
    st.markdown("""
    * **SO 戰略（極大化優勢與機會）**：主打**「泰山育兒與路口安全」**，運用三寶媽經驗主導塭仔圳公園與托育設施公聽會。
    * **WO 戰略（克服劣勢並把握機會）**：透過短影音紀錄「泰山會勘第一線」，將 10 年服務經驗數位化，吸引新遷入重劃區的青年人口。
    * **ST 戰略（運用優勢化解威脅）**：面對施工陣痛期造成的民怨，發揮熟稔市府機關優勢，第一時間進行現場會勘並督促工期。
    * **WT 戰略（減少劣勢並避開威脅）**：加強跨區議題聯防，與同區域立委或優質議員聯合聯名宣傳，提升整體信任感。
    """)

# TAB 3: 團隊內部評估數據（包含放回的圓餅圖）
with tab3:
    st.subheader("📊 競選團隊策略參數（內部評估）")
    st.caption("此區數據為競選團隊手動設定之策略目標與話題權重，非即時自動算出的真實民調。")

    c1, c2 = st.columns(2)
    
    # 圓餅圖放回此處
    with c1:
        st.write("#### 🔥 泰山區重點議題關注重點分佈")
        issue_data = pd.DataFrame({
            "議題": ["塭仔圳重劃區配套", "交通死角與路口安全", "婦幼托育與公園", "五泰輕軌進度", "長照與銀髮福利"],
            "關注度 (%)": [35, 28, 20, 10, 7]
        })
        fig_pie = px.pie(
            issue_data, 
            values="關注度 (%)", 
            names="議題", 
            hole=0.4, 
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with c2:
        st.write("#### 戰略執行進度")
        st.progress(0.75, text="泰山區里長拜訪覆蓋率：75%")
        st.progress(0.60, text="路口會勘改善案完成率：60%")
        st.progress(0.40, text="新莊/五股跨區客座宣傳進度：40%")
