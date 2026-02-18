import yfinance as yf
import pandas as pd
import numpy as np
from openai import OpenAI
import os

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# Edison Chen's portfolio
portfolio = {
    'NVDA': 3231,
    'TSLA': 2710,
    'RKLB': 4500,
    'AMD': 2000,
    'GOOG': 1500,
    'ORCL': 2700,
    'AMZN': 813,
    'IBIT': 4000,
    'META': 206,
    'HOOD': 1860,
    'QQQ': 550,
    'SPY': 350
}

def get_historical_data(tickers, period='1y'):
    """Fetches historical data for given tickers."""
    data = yf.download(tickers, period=period)
    return data.xs('Close', level=0, axis=1)

def calculate_macd(df, short_window=12, long_window=26, signal_window=9):
    """Calculates MACD for a given DataFrame."""
    exp1 = df.ewm(span=short_window, adjust=False).mean()
    exp2 = df.ewm(span=long_window, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=signal_window, adjust=False).mean()
    return macd, signal

def calculate_rsi(df, window=14):
    """Calculates RSI for a given DataFrame."""
    delta = df.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_bollinger_bands(df, window=20, num_std_dev=2):
    """Calculates Bollinger Bands for a given DataFrame."""
    rolling_mean = df.rolling(window=window).mean()
    rolling_std = df.rolling(window=window).std()
    upper_band = rolling_mean + (rolling_std * num_std_dev)
    lower_band = rolling_mean - (rolling_std * num_std_dev)
    return rolling_mean, upper_band, lower_band

def analyze_technical_indicators(df):
    """Analyzes technical indicators and generates signals."""
    analysis = {}
    for ticker in df.columns:
        stock_data = df[ticker].dropna()
        if len(stock_data) < 26: # MACD needs at least 26 periods
            analysis[ticker] = "Not enough data for comprehensive technical analysis."
            continue

        macd, macd_signal = calculate_macd(stock_data)
        rsi = calculate_rsi(stock_data)
        ma, upper_band, lower_band = calculate_bollinger_bands(stock_data)

        latest_price = stock_data.iloc[-1]
        latest_macd = macd.iloc[-1]
        latest_macd_signal = macd_signal.iloc[-1]
        latest_rsi = rsi.iloc[-1]
        latest_ma = ma.iloc[-1]
        latest_upper_band = upper_band.iloc[-1]
        latest_lower_band = lower_band.iloc[-1]

        signals = []
        if latest_macd > latest_macd_signal and macd.iloc[-2] <= macd_signal.iloc[-2]:
            signals.append("MACD金叉 (看涨)")
        elif latest_macd < latest_macd_signal and macd.iloc[-2] >= macd_signal.iloc[-2]:
            signals.append("MACD死叉 (看跌)")

        if latest_rsi > 70:
            signals.append("RSI超买 (可能回调)")
        elif latest_rsi < 30:
            signals.append("RSI超卖 (可能反弹)")

        if latest_price > latest_upper_band:
            signals.append("价格突破布林带上轨 (强势上涨，但可能短期回调)")
        elif latest_price < latest_lower_band:
            signals.append("价格突破布林带下轨 (强势下跌，但可能短期反弹)")

        if not signals:
            signals.append("无明显技术信号")

        analysis[ticker] = {
            "latest_price": latest_price,
            "MACD": latest_macd,
            "MACD_Signal": latest_macd_signal,
            "RSI": latest_rsi,
            "MA": latest_ma,
            "Upper_Bollinger_Band": latest_upper_band,
            "Lower_Bollinger_Band": latest_lower_band,
            "Signals": signals
        }
    return analysis

def calculate_portfolio_value(prices, portfolio):
    """Calculates the total portfolio value."""
    total_value = 0
    for ticker, shares in portfolio.items():
        if ticker in prices:
            total_value += prices[ticker] * shares
    return total_value

def calculate_risk_metrics(df, portfolio):
    """Calculates basic risk metrics for the portfolio."""
    returns = df.pct_change().dropna()
    portfolio_returns = (returns * pd.Series(portfolio)).sum(axis=1) / calculate_portfolio_value(df.iloc[-1], portfolio)
    
    max_drawdown = (portfolio_returns + 1).cumprod().div((portfolio_returns + 1).cumprod().cummax()) - 1
    max_drawdown_value = max_drawdown.min()

    # Simplified VaR (Historical VaR at 99% confidence level)
    var_99 = portfolio_returns.quantile(0.01)

    # Individual stock concentration
    latest_prices = df.iloc[-1]
    current_portfolio_value = calculate_portfolio_value(latest_prices, portfolio)
    concentrations = {ticker: (latest_prices[ticker] * shares) / current_portfolio_value * 100 
                      for ticker, shares in portfolio.items() if ticker in latest_prices}

    return {
        "Max_Drawdown": max_drawdown_value,
        "VaR_99": var_99,
        "Concentrations": concentrations
    }

def generate_openai_suggestions(analysis_report):
    """Generates investment suggestions using OpenAI API."""
    prompt = f"""你是一位资深的量化投资分析师，请根据以下量化分析报告，为 Edison Chen 先生的投资组合提供中文操作建议。Edison 先生的投资风格是激进型、超长期（10年+），重仓科技股，同时大量卖出 PUT 期权收取权利金。请重点关注其持仓股票的技术信号、风险指标，并结合其投资风格给出具体的买卖、期权策略调整建议。请注意，不需要提供多因子选股的建议，因为 Edison 先生已经有核心持仓。

量化分析报告：
{analysis_report}

请提供以下几点建议：
1. 对当前市场和投资组合的整体评估。
2. 对核心持仓股票的技术分析解读和操作建议（例如，是否考虑卖出PUT期权，调整行权价或到期日）。
3. 投资组合的风险评估和调整建议。
4. 针对Edison先生卖出PUT期权策略的优化建议。
5. 总结和后续行动建议。

请用中文清晰、专业地阐述，并避免使用过于专业的术语，确保建议可操作性强。"""

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini", # Using a smaller, faster model for this task
            messages=[
                {"role": "system", "content": "你是一位资深的量化投资分析师，专注于美股市场。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1500,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"OpenAI API 调用失败: {e}"

def main():
    tickers = list(portfolio.keys())
    print(f"Fetching historical data for: {tickers}")
    historical_data = get_historical_data(tickers, period='1y')
    print("Historical data fetched.")

    print("Analyzing technical indicators...")
    technical_analysis_results = analyze_technical_indicators(historical_data)
    print("Technical indicators analyzed.")

    print("Calculating risk metrics...")
    risk_metrics = calculate_risk_metrics(historical_data, portfolio)
    print("Risk metrics calculated.")

    report_content = "# Edison Chen 量化分析报告\n\n## 1. 投资组合概览\n\n" \
                     + pd.DataFrame([{'股票代码': k, '持股数量': v} for k, v in portfolio.items()]).to_markdown(index=False) \
                     + "\n\n## 2. 技术分析信号\n\n"

    for ticker, analysis in technical_analysis_results.items():
        report_content += f"### {ticker}\n"
        if isinstance(analysis, str):
            report_content += f"- {analysis}\n"
        else:
            report_content += f"- 最新价格: {analysis['latest_price']:.2f}\n"
            report_content += f"- MACD: {analysis['MACD']:.2f}, MACD信号线: {analysis['MACD_Signal']:.2f}\n"
            report_content += f"- RSI: {analysis['RSI']:.2f}\n"
            report_content += f"- 20日均线: {analysis['MA']:.2f}\n"
            report_content += f"- 布林带上轨: {analysis['Upper_Bollinger_Band']:.2f}, 布林带下轨: {analysis['Lower_Bollinger_Band']:.2f}\n"
            report_content += f"- 信号: {', '.join(analysis['Signals'])}\n"
        report_content += "\n"

    report_content += "## 3. 风险指标\n\n"
    report_content += f"- 最大回撤: {risk_metrics['Max_Drawdown']:.2%}\n"
    report_content += f"- 99% VaR (1天): {risk_metrics['VaR_99']:.2%}\n"
    report_content += "- 个股集中度:\n"
    for ticker, concentration in risk_metrics['Concentrations'].items():
        report_content += f"  - {ticker}: {concentration:.2f}%\n"
    report_content += "\n"

    print("Generating OpenAI suggestions...")
    suggestions = generate_openai_suggestions(report_content)
    report_content += "## 4. 智能操作建议 (由 OpenAI 生成)\n\n"
    report_content += suggestions
    print("OpenAI suggestions generated.")

    with open('/home/ubuntu/edison_quant_report.md', 'w', encoding='utf-8') as f:
        f.write(report_content)
    print("Quantitative analysis report saved to /home/ubuntu/edison_quant_report.md")

if __name__ == "__main__":
    main()
