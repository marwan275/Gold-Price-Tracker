# 24K-GoldTracker

24K-GoldTracker is a Windows-friendly desktop app for following 24K gold prices in Egyptian Pounds. It helps you check the latest market price, estimate the value of your gold by grams, review recent price history, and calculate profit or loss on purchases.

The app opens as one maximized window with a simple left sidebar:

- Dashboard for today's price and value by grams.
- Calculator for purchase rows and profit/loss.
- History for the recent gold futures trend.

The dashboard prefers the Egypt market feed when it is available, shows a worldwide converted EGP-per-gram price beside it, and can keep using recent saved values when one source is temporarily unavailable.

The app is built around the Egyptian BTC 10g 24K ingot listing configured in `gold_tracker/config.py`, the `GoldPrice.Today` live API, and Yahoo Finance historical data for `GC=F`.

<img width="1920" height="1140" alt="image" src="https://github.com/user-attachments/assets/d2799b11-7d6d-4df8-98a5-4aa37896ed40" />

<img width="1920" height="1140" alt="image" src="https://github.com/user-attachments/assets/bc98f578-c313-48ec-9448-e6363078a8d2" />

<img width="1920" height="1140" alt="image" src="https://github.com/user-attachments/assets/6ee004af-c514-4358-b301-263cdac661d3" />


## Highlights

- Live Egypt and worldwide EGP-per-gram prices.
- Automatic refresh every minute, plus a manual refresh button.
- Value estimate from the grams you enter.
- Profit calculator with total grams, average buy price, total paid, break-even price, profit/loss, and profit percentage.
- Excel import and export for calculator data.
- One-year history chart from Yahoo Finance.
- Background loading for prices and history so the interface stays usable.
- Stable dashboard and calculator cards even when numbers get large.
- Rotating log files for troubleshooting.

## Requirements

- Python 3.10 or newer.
- Tkinter. It is included with most Python installers.
- PyInstaller and Inno Setup 6 are only needed if you want to build a shareable Windows installer.

Python dependencies are installed from `pyproject.toml` when you install the package.

## Quick Start

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

Start the app:

```bash
24K-GoldTracker
```

Or run it directly as a module:

```bash
python -m gold_tracker
```

## Using The App

This section explains the three main screens and what to expect while the app is loading or closing.

### Dashboard

Use the Dashboard to check the latest price and estimate the value of a gold amount.

- Enter grams directly or use the stepper buttons.
- The main value updates when prices refresh.
- Egypt market and worldwide market prices are shown separately.
- The last update time shows when the latest successful refresh happened.

The first live price arrives quickly because both live sources use direct HTTP requests.

### Calculator

Use the Calculator to estimate profit or loss from your purchase rows.

For each row, enter:

- `Grams`: how much gold you bought.
- `Total Paid`: the total amount paid for that row.

The calculator shows:

- paid price per gram for each row,
- row profit/loss,
- total grams,
- average buy price,
- total paid,
- current market value,
- break-even price,
- total profit/loss,
- profit/loss percentage.

You can export the calculator to Excel, edit it, and import it again later.

### History

Use History to review the recent gold futures trend. The chart uses Yahoo Finance `GC=F` closes converted from USD per troy ounce to USD per gram.

This chart is useful for market context, but it is not the same as the live Egypt shop price shown on the Dashboard.

### Startup And Closing

Prices and history load in the background. This means the window can open and stay responsive while data is still loading.

When you close the window, the app asks background workers to stop and closes the UI quickly. If a network task is still busy, the app skips slow cleanup instead of leaving the window stuck on screen.

## Price Source Notes

The Egypt market price is loaded from the listing site's Magento GraphQL backend using the configured BTC 10g 24K ingot URL to identify the product.

Live prices can fail because the third-party API is unavailable, the GraphQL backend changes, or the network is down. The dashboard keeps short-lived cached prices so one failed source does not immediately blank the UI.

Historical prices use Yahoo Finance gold futures closes and are converted from troy ounces to grams. They are displayed as USD/gram, not EGP/gram. Futures prices are not the same as the live spot price, so the history chart should be treated as market context rather than an exact local selling price.

The Egypt market price is based on the BTC 10g 24K ingot listing divided by 10. This is not a pure raw-gold gram price; it includes the product premium, making charges, and taxes included in that listing. That makes it closer to the kind of price a buyer might see at a local shop in Egypt.

## Excel Files

The calculator export is column-oriented so it is easy to inspect and edit in Excel. It includes purchase columns for grams, bought total, price per gram, and row profit/loss, plus summary columns for total grams, average bought price, cost basis, profit/loss, and profit/loss percentage.

Imports expect at least `grams` and `bought total` headers. Extra columns from exported files are allowed.

## Logging

Logging is configured in `gold_tracker/logging_config.py` and controlled by constants in `gold_tracker/config.py`.

- Windows log files are written under `%LOCALAPPDATA%\24K-GoldTracker\logs\gold_tracker.log`.
- Non-Windows fallback logs are written under `~/.24k-goldtracker/logs/gold_tracker.log`.
- Console logs are written to stdout, so PowerShell commands such as `24K-GoldTracker | Tee-Object -FilePath test.log` capture app logs.
- Third-party debug noise from urllib3, yfinance, and peewee is suppressed to `WARNING` so app logs stay readable.

To make app logs more verbose during development, change `LOG_LEVEL` in `gold_tracker/config.py`.


## Windows Build And Installer

The repository includes a PyInstaller spec and an Inno Setup script.

Build the folder-style executable first:

```powershell
pyinstaller 24K-GoldTracker.spec
```

The executable should be created at:

```text
dist\24K-GoldTracker-1.1.0\24K-GoldTracker-1.1.0.exe
```

Then build the installer with Inno Setup 6:

```powershell
iscc installer\24K-GoldTracker.iss
```

The installer output is:

```text
dist\24K-GoldTrackerSetup-1.1.0.exe
```

See `installer/README.md` for the short installer-specific checklist.

## Code Layout

- `gold_tracker/app.py` owns the Tk application lifecycle, shared state, screen navigation, and background refresh coordination.
- `gold_tracker/models.py` contains shared data models used across services and UI views.
- `gold_tracker/core/app_workers.py` prevents duplicate background jobs from running at the same time.
- `gold_tracker/services/price_fetcher.py` fetches live prices, queries the Egypt GraphQL backend, caches recent results, and loads historical data.
- `gold_tracker/services/excel_handler.py` imports and exports column-oriented Excel workbooks for calculator data.
- `gold_tracker/ui/app_shell.py` builds the single-window sidebar navigation shell.
- `gold_tracker/ui/dashboard_view.py` builds the live price dashboard and keeps the main value card layout stable.
- `gold_tracker/ui/history_window.py` builds the embedded history chart view.
- `gold_tracker/ui/profit_calculator_window.py` builds the embedded calculator and keeps summary cards stable for large values.
- `gold_tracker/ui/components.py` contains shared Tkinter styling helpers.
- `gold_tracker/logging_config.py` configures console and rotating file logging.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Financial Disclaimer

Use the prices as a quick reference only. They come from third-party sources and may differ from actual buy or sell rates, dealer spreads, taxes, and local market conditions.
