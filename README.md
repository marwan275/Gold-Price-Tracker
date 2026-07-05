# 24K Gold Tracker

24K Gold Tracker is a small Tkinter desktop app for checking gold prices in EGP and estimating the value of a gold holding by weight. The main screen prefers the Egypt market feed when it is available, keeps a worldwide converted price beside it, and falls back to recent cached values when a source is temporarily unavailable.

The app is built around the Egyptian BTC 10g 24K ingot listing configured in `gold_tracker/config.py`, the `GoldPrice.Today` live API, and Yahoo Finance historical data for `GC=F`.

<img width="1252" height="1065" alt="Screenshot 2026-07-05 125550" src="https://github.com/user-attachments/assets/bc73086e-80ea-4211-a41e-283c97d64d53" />
<img width="1127" height="990" alt="Screenshot 2026-07-05 125746" src="https://github.com/user-attachments/assets/7c4361cb-1db9-4efb-b25c-16b772bda0df" />
<img width="1302" height="940" alt="Screenshot 2026-07-05 160605" src="https://github.com/user-attachments/assets/e7542896-9a10-4f37-a50a-9323ce7882b6" />


## What It Does

- Shows Egypt market and worldwide EGP-per-gram prices on the dashboard.
- Calculates the current value for the grams entered in the weight selector.
- Refreshes prices automatically every minute and supports manual refreshes.
- Opens a history window with a one-year USD-per-gram chart from Yahoo Finance.
- Opens a profit calculator for purchase lots, average paid price, cost basis, current profit or loss, and Excel import/export.
- Writes logs to a per-user log directory, with console logging enabled during local runs.

## Requirements

- Python 3.10 or newer.
- Google Chrome, used by Selenium for the Egypt market page.
- Tkinter. It is included with most Python installers.
- `openpyxl` - Excel workbook import/export support

## Setup

From the repository root:

```bash
python -m venv venv
```

Activate the environment on Windows:

```bash
venv\Scripts\activate
```

Activate it on macOS or Linux:

```bash
source venv/bin/activate
```

Install the package and its command-line entry point:

```bash
pip install -e .
```

Run the app:

```bash
gold-tracker
```

Or run it directly as a module:

```bash
python -m gold_tracker
```

## Price Source Notes

The Egypt market price is scraped with Selenium, so the first run may take extra time while `webdriver-manager` resolves ChromeDriver. To use a specific driver path, set `GOLDTRACKER_CHROMEDRIVER` or update `CHROME_DRIVER_PATH` in `gold_tracker/config.py`.

Live prices can fail because the third-party API is unavailable, the source page changes, ChromeDriver cannot start, or the network is down. The dashboard keeps short-lived cached prices so one failed source does not immediately blank the UI.

Historical prices use Yahoo Finance gold futures closes and are converted from troy ounces to grams. They are displayed as USD/gram, not EGP/gram. Futures prices are not the same as the live spot price, so the history chart should be treated as market context rather than an exact local selling price.

The Egypt market price is based on the BTC 10g 24K ingot listing divided by 10. This is not a pure raw-gold gram price; it includes the product premium, making charges, and taxes included in that listing. That makes it closer to the kind of price a buyer might see at a local shop in Egypt.

## Code Layout

- `gold_tracker/app.py` owns the Tk application lifecycle, shared state, and background refresh coordination.
- `gold_tracker/models.py` contains shared data models used across services and UI windows.
- `gold_tracker/core/app_workers.py` prevents duplicate background jobs from running at the same time.
- `gold_tracker/services/price_fetcher.py` fetches live prices, parses the Egypt source page, caches recent results, and loads historical data.
- `gold_tracker/services/excel_handler.py` imports and exports column-oriented Excel workbooks for calculator data.
- `gold_tracker/ui/` contains the main dashboard, history window, profit calculator window, and shared UI components.
- `gold_tracker/logging_config.py` configures console and rotating file logging.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Financial Disclaimer

Use the prices as a quick reference only. They come from third-party sources and may differ from actual buy or sell rates, dealer spreads, taxes, and local market conditions.
