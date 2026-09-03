# NASDAQ Complete Data Pipeline -- Data Dictionary

> **Comprehensive field definitions for all collected data points**
> Version 1.0 | July 2026

---

## 1. Company Information Fields

| Field | Type | Description | Source |
|-------|------|-------------|--------|
| `ticker` | String | Stock ticker symbol (e.g., AAPL) | NASDAQ Trader |
| `company_name` | String | Full company legal/operating name | NASDAQ Trader / yfinance |
| `exchange` | String | Primary listing exchange | NASDAQ Trader |
| `sector` | String | GICS sector classification | yfinance |
| `industry` | String | GICS industry group | yfinance |
| `country` | String | Headquarters country | yfinance |
| `market_cap` | Float | Current market capitalization (USD) | yfinance |
| `ipo_year` | Integer | Year of initial public offering | yfinance |
| `is_etf` | Boolean | Whether the security is an ETF | NASDAQ Trader |
| `is_active` | Boolean | Whether currently trading | Pipeline validation |
| `long_business_summary` | Text | Company business description | yfinance / web scrape |

---

## 2. Price Data Fields (Daily / Weekly / Monthly)

| Field | Type | Description |
|-------|------|-------------|
| `date` | Date | Trading date (or period start for weekly/monthly) |
| `open` | Float | Opening price for the period |
| `high` | Float | Highest price during the period |
| `low` | Float | Lowest price during the period |
| `close` | Float | Closing price for the period |
| `volume` | Integer | Total shares traded during the period |
| `adj_close` | Float | Closing price adjusted for all splits and dividend distributions |

**Notes:**
- Prices are in USD
- Adjusted close accounts for stock splits, reverse splits, and dividend distributions
- Weekly data resamples daily data using Friday week-ending aggregation
- Monthly data uses calendar month-ending aggregation

---

## 3. Dividend Fields

| Field | Type | Description |
|-------|------|-------------|
| `date` | Date | Ex-dividend date |
| `amount` | Float | Dividend amount paid per share (USD) |

**Note:** Both regular and special dividends are included.

---

## 4. Stock Split Fields

| Field | Type | Description |
|-------|------|-------------|
| `date` | Date | Split effective date |
| `ratio` | Float | Numeric split ratio (e.g., 4.0 = 4:1, 0.5 = 1:2) |
| `split_factor` | String | Human-readable split description (e.g., "4:1") |

---

## 5. Fundamentals Fields (58+ metrics)

### Valuation & Size

| Field | Description |
|-------|-------------|
| `market_cap` | Market capitalization = share price × shares outstanding |
| `enterprise_value` | Enterprise value = market cap + debt - cash |
| `trailing_pe` | Price-to-earnings ratio (trailing 12 months) |
| `forward_pe` | Price-to-earnings ratio (forward 1 year estimate) |
| `price_to_book` | Price-to-book ratio |
| `price_to_sales` | Price-to-sales ratio (trailing 12 months) |
| `peg_ratio` | P/E ratio divided by earnings growth rate |

### Per-Share Data

| Field | Description |
|-------|-------------|
| `earnings_per_share` | Trailing 12-month earnings per share |
| `book_value` | Book value per share |
| `revenue_per_share` | Revenue per share |

### Profitability

| Field | Description |
|-------|-------------|
| `profit_margin` | Net income / revenue |
| `gross_margin` | Gross profit / revenue |
| `ebitda_margin` | EBITDA / revenue |
| `operating_margin` | Operating income / revenue |
| `return_on_assets` | Net income / total assets |
| `return_on_equity` | Net income / shareholder equity |

### Growth

| Field | Description |
|-------|-------------|
| `revenue_growth` | Year-over-year revenue growth rate |
| `earnings_growth` | Year-over-year earnings growth rate |

### Financial Health

| Field | Description |
|-------|-------------|
| `debt_to_equity` | Total debt / shareholder equity |
| `current_ratio` | Current assets / current liabilities |
| `quick_ratio` | (Current assets - inventory) / current liabilities |
| `total_debt` | Total debt outstanding (USD) |
| `total_cash` | Cash and cash equivalents (USD) |
| `total_cash_per_share` | Cash per share |

### Cash Flow

| Field | Description |
|-------|-------------|
| `total_revenue` | Trailing 12-month revenue (USD) |
| `net_income` | Net income (USD) |
| `free_cashflow` | Operating cash flow - capital expenditures |
| `operating_cashflow` | Cash from operations |
| `gross_profit` | Revenue - cost of goods sold |
| `ebitda` | Earnings before interest, taxes, depreciation, amortization |

### Short Interest & Ownership

| Field | Description |
|-------|-------------|
| `short_ratio` | Days to cover (short interest / average daily volume) |
| `short_percent_float` | Short interest as percentage of float |
| `held_percent_institutions` | Percentage held by institutional investors |
| `held_percent_insiders` | Percentage held by insiders |
| `shares_outstanding` | Total shares outstanding |
| `shares_float` | Shares available for public trading |
| `shares_short` | Number of shares sold short |

### Trading Statistics

| Field | Description |
|-------|-------------|
| `beta` | 5-year monthly beta (volatility vs market) |
| `fifty_two_week_high` | 52-week high price |
| `fifty_two_week_low` | 52-week low price |
| `fifty_day_average` | 50-day moving average price |
| `two_hundred_day_average` | 200-day moving average price |
| `average_volume` | Average daily volume |
| `average_volume_10days` | Average daily volume (10 days) |

### Dividend Information

| Field | Description |
|-------|-------------|
| `dividend_rate` | Indicated annual dividend rate |
| `dividend_yield` | Dividend yield (annual dividend / price) |
| `payout_ratio` | Dividends paid / net income |
| `ex_dividend_date` | Most recent ex-dividend date |

### Analyst Estimates

| Field | Description |
|-------|-------------|
| `target_mean_price` | Mean analyst price target |
| `target_high_price` | Highest analyst price target |
| `target_low_price` | Lowest analyst price target |
| `recommendation_mean` | Mean analyst recommendation (1=Strong Buy, 5=Sell) |
| `number_of_analyst_opinions` | Number of analysts providing estimates |

---

## 6. Financial Statement Fields

### Income Statement

| Field | Description |
|-------|-------------|
| `total_revenue` | Total revenue/sales |
| `cost_of_revenue` | Cost of goods sold |
| `gross_profit` | Revenue - cost of revenue |
| `operating_expenses` | Total operating expenses |
| `operating_income` | Income from operations (EBIT) |
| `interest_expense` | Interest expense on debt |
| `income_before_tax` | Pre-tax income |
| `income_tax_expense` | Income tax provision |
| `net_income` | Net income attributable to parent |
| `diluted_eps` | Diluted earnings per share |
| `basic_eps` | Basic earnings per share |
| `ebitda` | EBITDA |
| `research_development` | R&D expense |
| `selling_general_admin` | SG&A expense |

### Balance Sheet

| Field | Description |
|-------|-------------|
| `total_assets` | Total assets |
| `total_liabilities` | Total liabilities |
| `total_equity` | Total shareholders' equity |
| `current_assets` | Current assets |
| `current_liabilities` | Current liabilities |
| `cash_and_equivalents` | Cash and cash equivalents |
| `accounts_receivable` | Trade receivables |
| `inventory` | Inventory |
| `property_plant_equipment` | Net PP&E |
| `goodwill` | Goodwill |
| `intangible_assets` | Intangible assets |
| `long_term_debt` | Long-term debt |
| `short_term_debt` | Short-term debt |
| `total_debt` | Total debt |
| `accounts_payable` | Trade payables |
| `retained_earnings` | Accumulated retained earnings |
| `working_capital` | Current assets - current liabilities |

### Cash Flow Statement

| Field | Description |
|-------|-------------|
| `operating_cashflow` | Cash from operating activities |
| `investing_cashflow` | Cash from investing activities |
| `financing_cashflow` | Cash from financing activities |
| `capital_expenditure` | CapEx (maintenance + growth) |
| `free_cashflow` | Operating CF - CapEx |
| `depreciation_amortization` | D&A expense |
| `stock_based_compensation` | SBC expense |
| `dividends_paid` | Cash dividends paid |
| `common_stock_repurchased` | Share buybacks |
| `change_in_working_capital` | Change in working capital |

---

## 7. Supplemental Web-Scraped Data

Data from supplemental sources stored as JSON in `supplemental_data.data_content`:

| Source | Data Types Collected |
|--------|---------------------|
| Yahoo Finance Profile | Company description, officers, sector/industry details |
| NASDAQ.com | Official company profile, key statistics, trading data |
| SEC EDGAR | Recent SEC filing list, CIK number, filing types |
| MarketBeat | Analyst ratings, price targets, consensus recommendations |

---

## Data Coverage Notes

- **Price data**: Coverage varies by ticker. Some tickers have data going back to the 1970s, others only from their IPO date.
- **Financial statements**: Typically available for the last 3-5 years (quarterly) and last 5-10 years (annual).
- **Fundamentals**: Snapshot as of the last scrape date. Refresh periodically for current values.
- **Supplemental data**: May be incomplete for smaller/non-US listed tickers.
- **All values in USD** unless otherwise noted.
