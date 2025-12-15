import streamlit as st
import feedparser
import pandas as pd
from datetime import datetime
import time

# --- 頁面設定 ---
st.set_page_config(
    page_title="台股題材挖掘機",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 自定義樣式 (CSS) ---
st.markdown("""
    <style>
    .big-font { font-size:20px !important; font-weight: bold; }
    .highlight { color: #e74c3c; font-weight: bold; }
    div[data-testid="stDataFrame"] { width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- 新聞來源 (RSS) ---
RSS_SOURCES = {
    'Yahoo 股市 (頭條)': 'https://tw.stock.yahoo.com/rss?category=tw-market',
    'MoneyDJ (即時)': 'https://www.moneydj.com/rss/newstitle.aspx?tp=a',
    '鉅亨網 (頭條)': 'https://news.cnyes.com/rss/headline',
    '聯合新聞網 (股市)': 'https://money.udn.com/rssfeed/news/1001/5590/5591?ch=money',
    '中時電子報 (財經)': 'https://www.chinatimes.com/rss/realtimenews-finance.xml'
}

# --- 預設關鍵字 ---
DEFAULT_KEYWORDS = [
    '收購', '併購', '入股',
    '訂單', '大單', '轉單', '急單',
    '漲價', '調漲', '報價',
    '擴產', '新廠', '動土',
    '營收新高', '獲利新高', '三率三升',
    '法說', '股利', '殖利率',
    '處置', '注意股', '庫藏股'
]

def parse_time(published_str):
    """簡單的時間解析，失敗則回傳原字串"""
    try:
        # 嘗試解析 RSS 的標準時間格式
        dt = pd.to_datetime(published_str)
        # 轉換為台灣時間 (假設 Server 是 UTC，簡單處理加8小時，或直接格式化)
        # 這裡簡化處理，直接回傳易讀格式
        return dt.strftime("%m-%d %H:%M")
    except:
        return published_str

def fetch_news(selected_sources, keywords):
    news_items = []
    
    status_text = st.sidebar.empty()
    progress_bar = st.sidebar.progress(0)
    
    total_sources = len(selected_sources)
    
    for i, source_name in enumerate(selected_sources):
        status_text.text(f"正在掃描: {source_name}...")
        rss_url = RSS_SOURCES[source_name]
        
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries:
                title = entry.title
                summary = entry.summary if 'summary' in entry else ""
                
                # 關鍵字比對 (同時檢查標題與摘要)
                matched = []
                for kw in keywords:
                    if kw in title or kw in summary:
                        matched.append(kw)
                
                if matched:
                    news_items.append({
                        '發布時間': parse_time(entry.get('published', datetime.now().strftime("%Y-%m-%d %H:%M"))),
                        '來源': source_name,
                        '標題': title,
                        '命中題材': ", ".join(matched),
                        '連結': entry.link
                    })
        except Exception as e:
            st.error(f"無法讀取 {source_name}: {e}")
            
        progress_bar.progress((i + 1) / total_sources)
        
    status_text.text("掃描完成！")
    time.sleep(0.5)
    status_text.empty()
    progress_bar.empty()
    
    return news_items

# --- 側邊欄控制區 ---
st.sidebar.title("🔍 篩選設定")

# 1. 關鍵字設定
user_keywords = st.sidebar.multiselect(
    "監控關鍵字 (可自行新增)",
    options=DEFAULT_KEYWORDS,
    default=['收購', '訂單', '漲價', '營收新高', '擴產']
)

# 允許使用者輸入自定義關鍵字
custom_kw = st.sidebar.text_input("新增自定義關鍵字 (按 Enter 加入)")
if custom_kw and custom_kw not in user_keywords:
    user_keywords.append(custom_kw)
    st.sidebar.info(f"已暫時加入: {custom_kw}")

# 2. 來源設定
selected_sources = st.sidebar.multiselect(
    "新聞來源",
    options=list(RSS_SOURCES.keys()),
    default=list(RSS_SOURCES.keys())
)

# 3. 重新整理按鈕
if st.sidebar.button("🔄 立即重新掃描", type="primary"):
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown(f"最後更新: {datetime.now().strftime('%H:%M:%S')}")

# --- 主畫面 ---
st.title("📈 盤中題材快篩儀表板")

if not user_keywords:
    st.warning("⚠️ 請至少選擇一個關鍵字進行監控。")
else:
    with st.spinner('正在全網搜集資料中...'):
        data = fetch_news(selected_sources, user_keywords)

    if data:
        df = pd.DataFrame(data)
        
        # 依照時間排序 (假設字串格式可排，若格式混亂可能不準確，但通常夠用)
        df = df.sort_values(by="發布時間", ascending=False)
        
        # 顯示統計
        st.success(f"共搜尋到 **{len(df)}** 則符合「{'、'.join(user_keywords)}」的新聞")
        
        # 使用 Streamlit Dataframe 顯示 (支援點擊連結)
        st.dataframe(
            df,
            column_config={
                "連結": st.column_config.LinkColumn(
                    "閱讀全文",
                    display_text="點擊前往"
                ),
                "標題": st.column_config.TextColumn(
                    "新聞標題",
                    width="large"
                ),
                "命中題材": st.column_config.TextColumn(
                    "題材",
                    width="medium"
                ),
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("💡 目前在選定的來源中，找不到符合關鍵字的新聞。休息一下吧！")