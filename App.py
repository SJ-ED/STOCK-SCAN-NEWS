import streamlit as st
import feedparser
import pandas as pd
import yfinance as yf
import requests
import urllib.parse
from datetime import datetime, timedelta
import re

# --- 頁面設定 ---
st.set_page_config(
    page_title="台股戰情室 (自動主力版)",
    page_icon="🏯",
    layout="wide",
)

# --- CSS 美化 ---
st.markdown("""
    <style>
    .big-font { font-size:18px !important; }
    .stDataFrame { width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- 定義資料結構 ---
KEYWORD_GROUPS = {
    '🔥 熱門': ['收購', '併購', '入股', '經營權', '處置股', '注意股', '重訊'],
    '💰 營收': ['訂單', '大單', '急單', '轉單', '營收新高', '獲利新高', '三率三升'],
    '🏭 產業': ['漲價', '報價', '擴產', '新廠', '缺貨', '供不應求', '資本支出'],
    '📈 訊號': ['法說', '庫藏股', '增資', '減資', '股利', '殖利率', '填息'],
    '🤖 科技': ['AI', '伺服器', 'CPO', '散熱', '機器人', 'CoWoS', '先進封裝', '矽光子', 'B100']
}

TARGET_SITES = [
    'site:news.cnyes.com', 'site:money.udn.com', 'site:tw.stock.yahoo.com', 
    'site:ctee.com.tw', 'site:bnext.com.tw', 'site:technews.tw'
]

# --- 核心功能函數 ---

def fetch_broker_data(url):
    """
    爬取 MoneyDJ/券商分點網頁的買超排行
    """
    try:
        # 偽裝成一般瀏覽器，避免被擋
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers)
        # MoneyDJ 通常使用 big5 編碼
        response.encoding = 'big5'
        
        # 使用 Pandas 解析 HTML 表格
        dfs = pd.read_html(response.text)
        
        # 尋找包含數據的表格。通常這類網頁最大的表格就是數據
        # 這裡做一個簡單的篩選邏輯：找欄位裡有"買超張數"的表
        target_df = None
        for df in dfs:
            # 將欄位名稱轉字串比對
            if any("買超張數" in str(col) for col in df.columns):
                target_df = df
                break
        
        if target_df is not None:
            # 清理資料：通常第一列可能是多層索引或雜訊
            # 假設結構是：[名次, 股票名稱, 買超張數...] 
            # 有時候股票名稱欄位會包含代碼 (如 "2330台積電")
            
            # 嘗試標準化欄位
            # 這裡針對該網址結構做特化處理
            stock_list = []
            
            # 遍歷每一列
            for index, row in target_df.iterrows():
                # 將整列轉為字串搜尋數字 (股票代碼)
                row_str = str(row.values)
                # 抓取 4碼數字 (簡單過濾)
                codes = re.findall(r'[1-9]\d{3}', row_str)
                if codes:
                    # 通常第一個出現的四位數就是代碼
                    stock_list.append(codes[0])
            
            # 去重並取前 20 名
            return list(set(stock_list))[:20]
            
        return []
    except Exception as e:
        st.error(f"爬取券商資料失敗：{e}")
        return []

def get_google_news_combined(time_str):
    """
    time_str: "1h" (一小時內), "12h" (早報), "1d" (全天)
    """
    all_news = []
    progress_bar = st.progress(0)
    total_groups = len(KEYWORD_GROUPS)
    
    for i, (group_name, keywords) in enumerate(KEYWORD_GROUPS.items()):
        kw_query = " OR ".join(keywords)
        site_query = " OR ".join(TARGET_SITES)
        full_query = f"({kw_query}) AND ({site_query}) when:{time_str}"
        encoded_query = urllib.parse.quote(full_query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries:
                existing = next((item for item in all_news if item['標題'] == entry.title), None)
                if existing:
                    if group_name not in existing['涉及面向']:
                        existing['涉及面向'] += f", {group_name}"
                else:
                    all_news.append({
                        '標題': entry.title,
                        '連結': entry.link,
                        '時間': entry.published if 'published' in entry else datetime.now().strftime("%H:%M"),
                        '涉及面向': group_name,
                        'timestamp': pd.to_datetime(entry.published) if 'published' in entry else datetime.now()
                    })
        except:
            pass
        progress_bar.progress((i + 1) / total_groups)
    
    progress_bar.empty()
    return all_news

def get_tech_analysis(ticker_list):
    if not ticker_list: return pd.DataFrame()
    data = []
    for code in ticker_list:
        try:
            stock = yf.Ticker(f"{code}.TW")
            hist = stock.history(period="3mo")
            if len(hist) > 20:
                price = hist['Close'].iloc[-1]
                ma5 = hist['Close'].rolling(5).mean().iloc[-1]
                ma20 = hist['Close'].rolling(20).mean().iloc[-1]
                ma60 = hist['Close'].rolling(60).mean().iloc[-1]
                vol = hist['Volume'].iloc[-1]
                vol_ma5 = hist['Volume'].rolling(5).mean().iloc[-1]
                
                # 趨勢判斷
                trend = "盤整"
                if price > ma5 > ma20 > ma60: trend = "🔥 強勢多頭"
                elif price > ma20 and price > ma60: trend = "📈 多頭修正"
                elif price < ma20: trend = "❄️ 弱勢/空頭"
                
                data.append({
                    '代碼': code,
                    '現價': round(price, 2),
                    '月線乖離%': round(((price - ma20)/ma20)*100, 2),
                    '技術型態': trend,
                    '量能': "爆量" if vol > vol_ma5 * 1.5 else "縮量" if vol < vol_ma5 * 0.7 else "溫和"
                })
        except: continue
    return pd.DataFrame(data)

# --- 側邊欄 ---
st.sidebar.title("🏯 台股戰情室 v3")

# 1. 時間模式 (滿足 早報/盤中/盤後)
time_mode = st.sidebar.radio(
    "時間模式", 
    ["☀️ 早報 (08:45前)", "⚡ 盤中 (即時突發)", "🌙 盤後 (全日總結)"]
)

if "早報" in time_mode:
    search_period = "12h" # 昨晚到今早
    st.sidebar.info("搜尋昨晚收盤後 ~ 開盤前的新聞")
elif "盤中" in time_mode:
    search_period = "1h"  # 只看過去一小時
    st.sidebar.warning("搜尋過去 1 小時內的最新突發")
else:
    search_period = "1d"  # 過去24小時
    st.sidebar.success("搜尋今日全天盤後總整理")

st.sidebar.markdown("---")

# 2. 自動抓取券商分點
st.sidebar.subheader("🕵️‍♂️ 主力分點追蹤")
# 提供預設網址 (範例：凱基台北 或 使用者提供的網址)
default_url = "https://fubon-ebrokerdj.fbs.com.tw/z/zg/zgb/zgb0.djhtm?a=9200&b=9268"
broker_url = st.sidebar.text_input("輸入券商分點網址 (MoneyDJ/富邦)", value=default_url)

manual_tickers = st.sidebar.text_area("或手動輸入代碼 (逗號分隔)", "")

# 3. 執行
run = st.sidebar.button("🚀 啟動掃描", type="primary")

# --- 主畫面 ---
st.title(f"{time_mode} 戰情看板")

if run:
    # === Step 1: 處理主力籌碼 ===
    target_tickers = []
    
    # 從網址抓取
    if broker_url:
        with st.spinner("正在潛入券商網頁抓取主力買超股..."):
            scraped_tickers = fetch_broker_data(broker_url)
            if scraped_tickers:
                st.toast(f"成功抓取到 {len(scraped_tickers)} 檔主力股！")
                target_tickers.extend(scraped_tickers)
            else:
                st.error("無法從網址抓取資料，請確認網址格式正確。")
    
    # 加上手動輸入
    if manual_tickers:
        manual_list = re.findall(r'[1-9]\d{3}', manual_tickers)
        target_tickers.extend(manual_list)
        
    # 去重
    target_tickers = list(set(target_tickers))

    col1, col2 = st.columns([1, 1])

    # === Step 2: 左側 - 顯示主力股技術面 ===
    with col1:
        st.subheader("📊 主力關注股 x 技術面")
        if target_tickers:
            df_tech = get_tech_analysis(target_tickers)
            if not df_tech.empty:
                # 把強勢股排前面
                df_tech = df_tech.sort_values(by="月線乖離%", ascending=False)
                st.dataframe(
                    df_tech, 
                    hide_index=True, 
                    use_container_width=True,
                    column_config={
                        "技術型態": st.column_config.TextColumn("型態", width="small"),
                    }
                )
            else:
                st.info("抓到了代碼，但無法取得即時股價 (可能是盤中API限制)")
        else:
            st.info("尚未輸入或抓取到股票代碼")

    # === Step 3: 右側 - 顯示相關新聞 ===
    with col2:
        st.subheader("📰 市場焦點新聞")
        with st.spinner(f"搜尋過去 {search_period} 新聞中..."):
            news_data = get_google_news_combined(search_period)
            
        if news_data:
            df_news = pd.DataFrame(news_data)
            df_news = df_news.sort_values(by='timestamp', ascending=False)
            
            st.dataframe(
                df_news[['時間', '涉及面向', '標題', '連結']],
                column_config={
                    "連結": st.column_config.LinkColumn("Go", display_text="閱讀"),
                    "標題": st.column_config.TextColumn("標題", width="medium"),
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("該時段內無符合條件的重要新聞。")

else:
    st.info("👈 請在左側設定網址後，點擊「啟動掃描」")
    st.markdown("""
    ### 📝 自動化操作說明
    1. **網址來源**：程式支援爬取 `fubon-ebrokerdj` 或 `moneydj` 格式的「分點買賣超」頁面。
    2. **早報模式**：每天 08:00 ~ 08:45 使用，程式會搜尋昨晚到今早的消息。
    3. **盤中模式**：盤中若有異動，切換至此模式，程式只會搜尋「最近 1 小時」的突發新聞。
    """)
