import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

# 頁面配置
st.set_page_config(
    page_title="蔡佩呈 - 泰山區選情即時看板與策略系統",
    page_icon="🗳️",
    layout="wide"
)

# 標題區
st.title("🗳️ 新北市議員參選人【蔡佩呈】即時選情與戰略分析看板")
st.caption("聚焦泰山・五股・新莊・林口選區 | 數據驅動的 SWOT 選戰決策系統")

# 側邊欄：新聞與聲量爬蟲設定
st.sidebar.header("⚙️ 輿情數據源與篩選")
selected_district = st.sidebar.selectbox("目標選區 focus", ["泰山區", "五股區", "新莊區", "林口區"])
search_keyword = st.sidebar.text_input("搜尋關鍵字", "蔡佩呈 泰山 交通")
refresh_btn = st.sidebar.button("🔄 重新拉取即時新聞 RSS")

# 模擬/真實抓取 Google News RSS
@st.cache_data(ttl=3600)
def fetch_google_news_rss(keyword):
    url = f"https://news.google.com/rss/search?q={keyword}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    try:
        response = requests.get(url, timeout=5)
        root = ET.fromstring(response.content)
        articles = []
        for item in root.findall('.//item')[:10]:
            articles.append({
                "title": item.find('title').text,
                "link": item.find('link').text,
                "pubDate": item.find('pubDate').text
            })
        return pd.DataFrame(articles)
    except Exception as e:
        # Fallback 模擬數據
        return pd.DataFrame([
            {"title": "地方安全不能等！蔡佩呈爭取拆牆改善五股路口視線盲點", "link": "https://example.com/1", "pubDate": "2026-01-29"},
            {"title": "泰山塭仔圳開發後續：鄉親關心公設進度與托育資源", "link": "https://example.com/2", "pubDate": "2026-02-01"},
            {"title": "三寶媽參政！蔡佩呈發表親子公園與婦幼安全政見", "link": "https://example.com/3", "pubDate": "2026-02-05"}
        ])

news_df = fetch_google_news_rss(search_keyword)

# 頁籤規劃
tab1, tab2, tab3 = st.tabs(["📊 輿情儀表板", "🎯 SWOT 戰略分析矩陣", "📰 即時地方新聞情報"])

with tab1:
    col1, col2, col3 = st.columns(3)
    col1.metric("本週選區聲量排名", "No. 2", delta="+1 升位")
    col2.metric("正面好感度 (P/N比)", "3.45", delta="+0.25")
    col3.metric("關鍵議題聚焦", "塭仔圳 / 交通拆牆", delta="泰山區聲量最高")

    st.markdown("---")
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("🔥 泰山區民眾關心熱門議題")
        issues_data = pd.DataFrame({
            "議題": ["塭仔圳重劃區配套", "交通與路口死角", "婦幼托育與親子空間", "五泰輕軌建設進度", "銀髮長照與里鄰服務"],
            "關注度 (%)": [35, 28, 18, 12, 7]
        })
        fig_pie = px.pie(issues_data, values="關注度 (%)", names="議題", hole=0.4,
                         color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig_pie, use_container_width=True)

    with c2:
        st.subheader("📈 主要候選人聲量趨勢 (近30天)")
        timeline_data = pd.DataFrame({
            "日期": ["W1", "W2", "W3", "W4"],
            "蔡佩呈": [120, 180, 240, 310],
            "競品 A": [200, 210, 220, 250],
            "競品 B": [150, 160, 170, 190]
        })
        fig_line = px.line(timeline_data, x="日期", y=["蔡佩呈", "競品 A", "競品 B"], 
                           markers=True, title="聲量變化圖")
        st.plotly_chart(fig_line, use_container_width=True)

with tab2:
    st.subheader("💡 蔡佩呈 SWOT 應對策略導出系統")
    st.info("基於地方扎根經歷（服務處主任）、三寶媽形象與泰山在地輿情擬定：")

    col_s, col_w = st.columns(2)
    with col_s:
        st.success("### 💪 S (Strengths) 優勢\n"
                   "- **十年基層扎根**：長年擔任議員服務處主任，熟知泰山各里長與地方大小事。\n"
                   "- **親和力與三寶媽形象**：精準吸引年輕父母、婦幼團體與家庭票源。\n"
                   "- **會勘執行力高**：具備拆除視線盲點牆體等有感建設實績。")
    
    with col_w:
        st.warning("### ⚠️ W (Weaknesses) 劣勢\n"
                   "- **新人知名度需擴張**：需快速將「服務處主任/宋主任」的轉化為「蔡佩呈」個人品牌。\n"
                   "- **跨區影響力**：在泰山本盤極強，但五股、新莊等大選區仍需加速開拓。")

    col_o, col_t = st.columns(2)
    with col_o:
        st.info("### 🚀 O (Opportunities) 機會\n"
                "- **塭仔圳重劃區人口遷入**：年輕家庭大量增加，急需托育、小學學區與公園建設。\n"
                "- **交通議題高度關注**：泰山民眾對泰板輕軌、五泰輕軌及路口改善關注度極高。")
    
    with col_t:
        st.error("### 🛡️ T (Threats) 威脅\n"
                 "- **多黨競爭激烈**：同選區新人輩出，搶奪年輕與中間選民。\n"
                 "- **重劃區施工陣痛期**：施工造成的交通壅塞易引發民怨。")

    st.markdown("### 🎯 SWOT 交錯戰略行動方案 (SO / ST / WO / WT)")
    st.markdown("""
    * **SO 戰略（乘勝追擊）**：以「三寶媽 + 10年建設實績」為核心，推出**「泰山育兒友善廊帶」**政策，主導重劃區公園與幼兒園規劃。
    * **WO 戰略（扭轉劣勢）**：利用 Facebook / Instagram / Line 經營短影音，紀錄「泰山會勘一日」，將深耕經驗轉化為網路個人聲聲量。
    * **ST 戰略（避開威脅）**：面對交通施工陣痛期，第一時間到場會勘改善（如拆除視線死角），主導「有感交通防護」。
    * **WT 戰略（防禦減害）**：強化跨區聯防（泰山+五股+林口），與同黨立委或市府政策聯名，提升跨區信任感。
    """)

with tab3:
    st.subheader(f"📰 最新新聞情報與地方聲量（關鍵字：{search_keyword}）")
    for idx, row in news_df.iterrows():
        with st.expander(f"📌 {row['title']} ({row['pubDate']})"):
            st.write(f"連結：[{row['link']}]({row['link']})")
            st.write("建議戰略行動：針對此議題留言說明服務處處理進度，並轉發至 FB 泰山地方社團。")