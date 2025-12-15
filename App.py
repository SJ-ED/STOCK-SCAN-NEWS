import streamlit as st
import feedparser
import pandas as pd
from datetime import datetime
import urllib.parse

# --- 頁面設定 ---
st.set_page_config(
    page_title="台股題材挖掘機 (Google引擎版)",
    page_icon="🔥",
    layout="wide",
)

# --- CSS 優化 ---
st.markdown("""
    <style>
    .big-font { font-size:18px !important; }
    div[data-testid="stDataFrame"] { width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- 關鍵字與預設設定 ---
# 這裡將關鍵字分類，方便使用者一次選一組
KEYWORD_GROUPS = {
    '🔥 熱門題材': ['收購', '併購', '入股', '處分利益', '經營權'],
    '💰 營收獲利': ['訂單', '大單', '急單', '轉單', '營收新高', '獲利新高', '三率三升'],
    '🏭 產業動態': ['漲價', '調漲', '報價', '擴產', '新廠', '缺貨', '供不應求'],
    '📈 股市訊號': ['法說', '庫藏股', '實施庫藏', '增資', '減資', '股利', '殖利率'],
    '🤖 科技趨勢': ['AI', '伺服器', 'CPO', '散熱', '機器人', 'CoWoS', '先進封裝']
}

# 指定搜尋的新聞來源 (避免搜尋到部落格或內容農場)
TARGET_SITES = [
    'site:news.cnyes.com',       # 鉅亨網
    'site:money.udn.com',        # 經濟日報
    'site:tw.stock.yahoo.com',   # Yahoo股市
    'site:ctee.com.tw',          # 工商時報
    'site:bnext.com.tw',         # 數位時代
    'site:technews.tw'           # 科技新報
]

def get_google_news_feed(keywords):
    """
    建立 Google News RSS 搜尋連結
    """
    # 組合關鍵字查詢：(關鍵字1 OR 關鍵字2)
    kw_query = " OR ".join(keywords)
    
    # 組合網站來源查詢：(site:A OR site:B)
    site_query = " OR ".join(TARGET_SITES)
    
    # 最終查詢字串：(訂單 OR 大單) AND (site:cnyes... OR ...) when:1d
    # when:1d 代表只搜尋過去 24 小時 (確保新聞新鮮)
    full_query = f"({kw_query}) AND ({site_query}) when:1d"
    
    # 進行 URL 編碼
    encoded_query = urllib.parse.quote(full_query)
    
    # Google News RSS 格式
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    return rss_url

def fetch_google_news(keywords):
    if not keywords:
        return []
    
    rss_url = get_google_news_feed(keywords)
    
    try:
        feed = feedparser.parse(rss_url)
        news_items = []
        
        for entry in feed.entries:
            # 處理時間格式
            pub_date = entry.published if 'published' in entry else ""
            try:
                # 嘗試將 Google 時間轉為 datetime 物件以便排序
                dt_obj = pd.to_datetime(pub_date)
                display_time = dt_obj.strftime("%m-%d %H:%M")
            except:
                display_time = pub_date

            news_items.append({
                '時間': display_time,
                '標題': entry.title,
                '連結': entry.link,
                '來源機構': entry.source.title if 'source' in entry else "Google News",
                '原始時間': dt_obj if 'dt_obj' in locals() else datetime.min # 用於排序
            })
            
        return news_items
    except Exception as e:
        st.error(f"連線發生錯誤: {e}")
        return []

# --- 側邊欄控制 ---
st.sidebar.header("🔍 搜尋設定")

# 選擇題材群組
selected_group = st.sidebar.selectbox("選擇題材類型", list(KEYWORD_GROUPS.keys()))
default_kws = KEYWORD_GROUPS[selected_group]

# 允許使用者增刪關鍵字
user_keywords = st.sidebar.multiselect(
    "細部調整關鍵字",
    options=default_kws + ['台積電', '鴻海', '聯發科'], # 補充一些個股供選
    default=default_kws
)

# 自定義輸入
custom_kw = st.sidebar.text_input("或輸入自訂關鍵字 (如：B100)")
if custom_kw:
    user_keywords.append(custom_kw)

if st.sidebar.button("🚀 開始搜尋", type="primary"):
    st.session_state['trigger_search'] = True

# --- 主畫面 ---
st.title(f"📰 台股新聞快搜：{selected_group}")
st.caption("資料來源：Google News (鎖定鉅亨、聯合、工商、Yahoo等權威媒體)")

# 自動觸發或手動觸發
if user_keywords:
    with st.spinner('正在召喚 Google 搜尋引擎...'):
        data = fetch_google_news(user_keywords)
        
    if data:
        df = pd.DataFrame(data)
        # 依照時間排序 (新的在上面)
        df = df.sort_values(by='原始時間', ascending=False)
        
        # 顯示結果
        st.success(f"過去 24 小時內，找到 **{len(df)}** 則相關新聞")
        
        st.dataframe(
            df[['時間', '來源機構', '標題', '連結']],
            column_config={
                "連結": st.column_config.LinkColumn("新聞連結", display_text="前往閱讀"),
                "標題": st.column_config.TextColumn("標題", width="large"),
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.warning("🧐 過去 24 小時內，主要媒體沒有報導包含這些關鍵字的新聞。")
        st.info("建議：嘗試更換「題材類型」或是增加更通用的關鍵字。")
else:
    st.info("👈 請在左側選擇關鍵字開始搜尋")
