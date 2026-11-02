import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import xml.etree.ElementTree as ET

# 1. 頁面基礎配置
st.set_page_config(
    page_title="蔡佩呈 - 泰山選情即時看板與戰略分析",
    page_icon="🗳️",
    layout="wide"
)

# 標題與聲明
st.title("🗳️ 新北市議員參選人【蔡佩呈】即時選情與戰略分析看板")
st.caption("聚焦泰山・五股・新莊・林口選區 | 數據驅動的 SWOT 選戰決策系統")
st.info("ℹ️ **資料來源提示**：新聞情報由 Google News RSS 即時 API 自動抓取；熱門議題與聲量指標為競選團隊內部戰略評估設定。")

# 2. 側邊欄設定
st.sidebar.header("⚙️ 輿情數據源與監測設定")
selected_district = st.sidebar.selectbox("目標關注區域", ["泰山區", "五股區", "新莊區", "林口區"])
search_keyword = st.sidebar.text_input("搜尋關鍵字", "蔡佩呈 泰山")
rss_limit = st.sidebar.slider("顯示新聞筆數", min_value=5, max_value=20, value=10)
refresh_btn = st.sidebar.button("🔄 重新拉取即時新聞 RSS")

# 3. 真實 Google News RSS 抓取函式（無虛假消息）
@st.cache_data(ttl=1800)
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
                "連結": link,
                "發布時間": pub_date
            })
            
        return pd.DataFrame(articles)
    except Exception as e:
        # 抓取失敗時回傳空表格，嚴格避免寫死杜撰假新聞
        return pd.DataFrame(columns=["標題", "連結", "發布時間"])

# 載入新聞資料
news_df = fetch_real_google_news(search_keyword)

# 4. 主分頁架構
tab1, tab2, tab3 = st.tabs(["📊 輿情儀表板", "🎯 SWOT 戰略分析矩陣", "📰 即時地方新聞情報"])

# TAB 1: 輿情儀表板 (還原熱門議題圓餅圖與聲量趨勢圖)
with tab1:
    # 頂部關鍵 KPI 指標 (團隊內部觀察參數)
    col1, col2, col3 = st.columns(3)
    col1.metric("選區網路熱度", "前段班", delta="聲量持續穩定")
    col2.metric("正面好感度 (P/N比)", "3.45", delta="+0.25")
    col3.metric("泰山區最受關注議題", "塭仔圳重劃區配套", delta="聲量最高")

    st.markdown("---")
    c1, c2 = st.columns(2)
    
    # 泰山區熱門議題分佈 (圓餅圖)
    with c1:
        st.subheader(f"🔥 {selected_district} 民眾關心熱門議題")
        issues_data = pd.DataFrame({
            "議題": ["塭仔圳重劃區配套", "交通死角與路口安全", "婦幼托育與親子公園", "五泰輕軌建設進度", "銀髮長照與里鄰服務"],
            "關注度 (%)": [35, 28, 20, 10, 7]
        })
        fig_pie = px.pie(
            issues_data, 
            values="關注度 (%)", 
            names="議題", 
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Pastel,
            title="議題關注度比例 (團隊評估)"
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # 主要候選人聲量趨勢 (折線圖)
    with c2:
        st.subheader("📈 選區主要動向聲量趨勢 (近 4 週團隊評估)")
        timeline_data = pd.DataFrame({
            "週次": ["W1", "W2", "W3", "W4"],
            "蔡佩呈 (團隊指標)": [120, 180, 240, 310],
            "競品 A 聲量": [200, 210, 220, 250],
            "競品 B 聲量": [150, 160, 170, 190]
        })
        fig_line = px.line(
            timeline_data, 
            x="週次", 
            y=["蔡佩呈 (團隊指標)", "競品 A 聲量", "競品 B 聲量"], 
            markers=True, 
            title="選區聲量走向比較"
        )
        st.plotly_chart(fig_line, use_container_width=True)

# TAB 2: SWOT 戰略分析矩陣 (基於參選人真實背景)
with tab2:
    st.subheader("💡 蔡佩呈 SWOT 競選戰略矩陣")
    st.caption("分析依據：蔡佩呈之 10 年議員服務處主任經驗、泰山在地深耕及三寶媽家庭形象。")

    col_s, col_w = st.columns(2)
    with col_s:
        st.success("### 💪 S (Strengths) 優勢\n"
                   "- **十年基層扎根**：長年擔任服務處主任，熟知泰山各里長訴求與區公所運作。\n"
                   "- **親和力與三寶媽形象**：精準吸引年輕父母、婦幼團體與家庭選民。\n"
                   "- **實績即戰力**：具備協調拆除路口視線死角牆體等有感地方建設實績。")
    
    with col_w:
        st.warning("### ⚠️ W (Weaknesses) 劣勢\n"
                   "- **個人品牌轉換期**：需將過去「服務處主任」幕後形象，迅速轉化為「蔡佩呈」個人獨立參選品牌。\n"
                   "- **跨區影響力**：泰山基本盤穩固，但新莊、五股等延伸選區仍需持續擴大知名度。")

    col_o, col_t = st.columns(2)
    with col_o:
        st.info("### 🚀 O (Opportunities) 機會\n"
                "- **塭仔圳重劃區人口遷入**：新進年輕家庭多，對托育、幼教與公園設施需求強烈。\n"
                "- **交通議題高關注**：民眾對五泰輕軌、泰板輕軌及路口安全改進有強烈訴求。")
    
    with col_t:
        st.error("### 🛡️ T (Threats) 威脅\n"
                 "- **多黨新人競爭**：同選區新人輩出，搶奪青年與中間選民票源。\n"
                 "- **施工陣痛期民怨**：重劃區與重大交通工程施工容易產生區域塞車民怨。")

    st.markdown("---")
    st.subheader("🎯 SWOT 交錯戰略行動方案 (TOWS)")
    st.markdown("""
    * **SO 戰略（極大化優勢與機會）**：主打**「泰山育兒與路口安全」**，運用三寶媽經驗與十年基層經驗，主導重劃區幼兒園與公園建設公聽會。
    * **WO 戰略（克服劣勢並把握機會）**：透過短影音紀錄「泰山會勘第一線」，將服務經驗數位化，吸引新遷入重劃區的年輕選民。
    * **ST 戰略（運用優勢化解威脅）**：面對交通施工陣痛期，第一時間派員進行會勘並協調市府單位降低影響。
    * **WT 戰略（減少劣勢並避開威脅）**：加強跨區議題聯防，與同區域優質立委或議員聯名發布政見，提升整體認同度。
    """)

# TAB 3: 即時地方新聞情報 (完全真實 RSS)
with tab3:
    st.subheader(f"📰 Google News 即時地方新聞情報（關鍵字：{search_keyword}）")
    
    if news_df.empty:
        st.info("ℹ️ 目前沒有抓取到相關即時新聞，或網路 API 請求頻率過高。請確認關鍵字或點擊側邊欄重新整理。")
    else:
        st.success(f"目前共擷取到 {len(news_df)} 則即時真實新聞：")
        for idx, row in news_df.head(rss_limit).iterrows():
            with st.expander(f"📌 {row['標題']}"):
                st.write(f"**發布時間**：{row['發布時間']}")
                st.write(f"**新聞連結**：[{row['連結']}]({row['連結']})")
                st.caption("建議戰略行動：針對新聞議題評估是否發布粉專回應或規劃現場會勘。")
