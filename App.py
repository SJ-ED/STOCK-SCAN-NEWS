# 記得在檔案最上方 (import區) 確保有這一行，如果沒有請加上：
import urllib3

# --- 核心功能函數 ---

def fetch_broker_data(url):
    """
    爬取 MoneyDJ/券商分點網頁的買超排行 (已修復 SSL 憑證問題)
    """
    try:
        # 1. 關閉 "不安全連線" 的警告訊息 (讓畫面乾淨一點)
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # 偽裝成一般瀏覽器
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # 2. 關鍵修改：加入 verify=False (忽略憑證檢查)
        response = requests.get(url, headers=headers, verify=False)
        
        # MoneyDJ 通常使用 big5 編碼
        response.encoding = 'big5'
        
        # 使用 Pandas 解析 HTML 表格
        dfs = pd.read_html(response.text)
        
        # 尋找包含數據的表格
        target_df = None
        for df in dfs:
            if any("買超張數" in str(col) for col in df.columns):
                target_df = df
                break
        
        if target_df is not None:
            stock_list = []
            for index, row in target_df.iterrows():
                row_str = str(row.values)
                # 抓取 4碼數字 (簡單過濾)
                codes = re.findall(r'[1-9]\d{3}', row_str)
                if codes:
                    stock_list.append(codes[0])
            
            # 去重並取前 20 名
            return list(set(stock_list))[:20]
            
        return []
    except Exception as e:
        # 如果還是錯，印出更詳細的原因
        st.error(f"爬取失敗，原因：{e}")
        return []
