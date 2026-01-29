# Persistence Scenarios Guide

This document explains how the bot's persistence system handles different trading scenarios when Firebase Firestore persistence is enabled.

## Overview

When persistence is enabled, the bot:
- ✅ Tracks all trades it makes (BUY/SELL) in Firestore
- ✅ Maintains ownership records for each symbol
- ✅ Prevents selling stocks not purchased by the bot
- ✅ Detects external sales (stocks sold outside the bot)
- ✅ Uses external sale proceeds for reinvestment
- ✅ Handles manually purchased stocks that enter top 5

## Scenario 1: First Ever Run

**Situation:** Bot runs for the first time with an empty portfolio.

### Example:
- **Week 1**: Bot runs, portfolio is empty
- **Top 5**: AAPL, MSFT, GOOGL, TSLA, NVDA

### Bot Behavior:
1. **Detects empty portfolio** (no positions from previous week's leaderboard)
2. **Checks cash balance** (must be >= $10,000)
3. **Divides initial capital** equally among top 5 stocks
4. **Buys** $2,000 worth of each stock (assuming $10,000 initial capital)
5. **Records all trades** in Firestore:
   - `trades` collection: 5 BUY records
   - `ownership` collection: 5 ownership records (one per symbol)

### Firestore State After Week 1:
```
trades: [
  {symbol: "AAPL", action: "BUY", quantity: X, price: Y, total: 2000},
  {symbol: "MSFT", action: "BUY", quantity: X, price: Y, total: 2000},
  {symbol: "GOOGL", action: "BUY", quantity: X, price: Y, total: 2000},
  {symbol: "TSLA", action: "BUY", quantity: X, price: Y, total: 2000},
  {symbol: "NVDA", action: "BUY", quantity: X, price: Y, total: 2000}
]

ownership: {
  AAPL: {quantity: X, total_cost: 2000},
  MSFT: {quantity: X, total_cost: 2000},
  GOOGL: {quantity: X, total_cost: 2000},
  TSLA: {quantity: X, total_cost: 2000},
  NVDA: {quantity: X, total_cost: 2000}
}
```

---

## Scenario 2: Happy Path - No External Sales

**Situation:** Normal rebalancing with no external sales or manual purchases.

### Example:
- **Week 1**: Bot owns AAPL, MSFT, GOOGL, TSLA, NVDA
- **Week 2**: Top 5 changes to AAPL, MSFT, GOOGL, TSLA, META (NVDA dropped out, META entered)

### Bot Behavior:
1. **Compares leaderboards:**
   - Previous week: AAPL, MSFT, GOOGL, TSLA, NVDA
   - Current week: AAPL, MSFT, GOOGL, TSLA, META
   - NVDA dropped out → Sell NVDA
   - META entered → Buy META

2. **Sells NVDA:**
   - Checks persistence: NVDA is bot-owned ✅
   - Sells all NVDA shares
   - Records SELL trade in Firestore
   - Updates ownership: Deletes NVDA record (all sold)
   - Gets proceeds: $X from NVDA sale

3. **Buys META:**
   - Uses proceeds from NVDA sale
   - Buys META with equal allocation
   - Records BUY trade in Firestore
   - Creates ownership record for META

### Firestore State After Week 2:
```
trades: [
  ... (previous trades),
  {symbol: "NVDA", action: "SELL", quantity: X, price: Y, total: proceeds},
  {symbol: "META", action: "BUY", quantity: X, price: Y, total: proceeds}
]

ownership: {
  AAPL: {quantity: X, total_cost: 2000},
  MSFT: {quantity: X, total_cost: 2000},
  GOOGL: {quantity: X, total_cost: 2000},
  TSLA: {quantity: X, total_cost: 2000},
  META: {quantity: X, total_cost: proceeds}  // NVDA removed
}
```

---

## Scenario 3: External Sales

### 3A: External Sales with Stock Still in Top 5

**Situation:** Stock is sold externally but remains in top 5.

### Example:
- **Week 1**: Bot buys 6 TSLA shares
- **Week 2**: TSLA still in top 5, but 2 TSLA shares sold manually
- **Week 3**: Bot runs, TSLA still in top 5

### Bot Behavior:
1. **Detects external sale:**
   - DB ownership: 6 TSLA shares
   - Broker position: 4 TSLA shares remaining
   - Detects: 2 shares sold externally
   - Updates ownership: 4 TSLA marked as bot-owned
   - Calculates proceeds: Cost basis for 2 shares
   - Records external sale in `external_sales` collection

2. **Buy logic:**
   - TSLA is in top 5 (`current_week_set`)
   - TSLA had external sales (`external_sales_by_symbol`)
   - Adds TSLA to buy list for buyback

3. **Buys TSLA back:**
   - Uses external sale proceeds (from 2 shares)
   - Also uses proceeds from any stocks that dropped out
   - Buys TSLA to restore position
   - Records BUY trade in Firestore
   - Updates ownership: Adds bought shares to existing 4

### Firestore State:
```
trades: [
  ... (previous trades),
  {symbol: "TSLA", action: "BUY", quantity: Y, price: Z, total: buyback_amount}
]

ownership: {
  TSLA: {quantity: 4 + Y, total_cost: adjusted_cost}  // 4 remaining + buyback
}

external_sales: [
  {symbol: "TSLA", quantity: 2, estimated_proceeds: X, used_for_reinvestment: true}
]
```

### 3B: External Sales with Stock NOT in Top 5

**Situation:** Stock is sold externally and drops out of top 5.

### Example:
- **Week 1**: Bot buys 6 TSLA shares
- **Week 2**: TSLA still in top 5, but 2 TSLA shares sold manually
- **Week 3**: Bot runs, TSLA NOT in top 5 (dropped out)

### Bot Behavior:
1. **Detects external sale:**
   - DB ownership: 6 TSLA shares
   - Broker position: 4 TSLA shares remaining
   - Detects: 2 shares sold externally
   - Updates ownership: 4 TSLA marked as bot-owned
   - Records external sale

2. **Sell logic:**
   - TSLA was in previous week's top 5
   - TSLA NOT in current week's top 5
   - TSLA is bot-owned (4 shares)
   - Adds TSLA to sell list

3. **Sells TSLA:**
   - Sells all 4 remaining TSLA shares
   - Records SELL trade
   - Deletes ownership record
   - Gets proceeds: From 4 shares

4. **Buy logic:**
   - TSLA NOT in top 5 → No buyback
   - Uses all proceeds (4 shares + 2 external sale proceeds) to buy new entrants

### Firestore State:
```
trades: [
  ... (previous trades),
  {symbol: "TSLA", action: "SELL", quantity: 4, price: Y, total: proceeds}
]

ownership: {
  // TSLA removed (all sold)
}

external_sales: [
  {symbol: "TSLA", quantity: 2, estimated_proceeds: X, used_for_reinvestment: true}
]
```

---

## Scenario 4: Multiple Stocks Moving In and Out

**Situation:** Complex rebalancing with multiple changes.

### Example:
- **Week 1**: Bot owns AAPL, MSFT, GOOGL, TSLA, NVDA
- **Week 2**: 
  - Top 5 changes to: AAPL, MSFT, GOOGL, META, AMD
  - TSLA and NVDA drop out
  - META and AMD enter
  - User manually sold 2 TSLA shares before bot runs

### Bot Behavior:
1. **Detects external sales:**
   - TSLA: 6 bot-owned → 4 remaining (2 sold externally)
   - Records external sale for TSLA

2. **Sell logic:**
   - TSLA: Dropped out, 4 shares bot-owned → Sell all 4
   - NVDA: Dropped out, bot-owned → Sell all
   - Gets proceeds: From TSLA (4 shares) + NVDA + TSLA external sale (2 shares)

3. **Buy logic:**
   - META: New entrant → Buy
   - AMD: New entrant → Buy
   - TSLA: NOT in top 5 → No buyback
   - Divides proceeds equally between META and AMD

4. **Records all trades:**
   - SELL: TSLA (4 shares), NVDA (all shares)
   - BUY: META, AMD
   - External sale: TSLA (2 shares)

### Firestore State:
```
trades: [
  ... (previous trades),
  {symbol: "TSLA", action: "SELL", quantity: 4, price: Y, total: proceeds1},
  {symbol: "NVDA", action: "SELL", quantity: X, price: Y, total: proceeds2},
  {symbol: "META", action: "BUY", quantity: X, price: Y, total: allocation1},
  {symbol: "AMD", action: "BUY", quantity: X, price: Y, total: allocation2}
]

ownership: {
  AAPL: {quantity: X, total_cost: 2000},
  MSFT: {quantity: X, total_cost: 2000},
  GOOGL: {quantity: X, total_cost: 2000},
  META: {quantity: X, total_cost: allocation1},
  AMD: {quantity: X, total_cost: allocation2}
  // TSLA and NVDA removed
}

external_sales: [
  {symbol: "TSLA", quantity: 2, estimated_proceeds: X, used_for_reinvestment: true}
]
```

---

## Additional Scenarios

### Manually Purchased Stock Enters Top 5

**Situation:** User manually buys a stock, then it enters top 5.

### Example:
- **Week 1**: User manually buys 10 TSLA shares
- **Week 2**: TSLA enters top 5

### Bot Behavior:
1. **Detects manually held stock:**
   - TSLA is in portfolio (10 shares)
   - TSLA is in top 5
   - TSLA NOT in persistence DB (manually purchased)
   - Adds TSLA to buy list

2. **Buys TSLA:**
   - Uses proceeds from stocks that dropped out
   - Buys TSLA to bring to target allocation
   - Records BUY trade
   - Creates ownership record

3. **Future behavior:**
   - Bot can now sell TSLA if it drops out (only bot-purchased shares)
   - Original 10 manual shares remain protected

### Partial External Sale

**Situation:** Some bot-owned shares sold externally, but more remain than were sold.

### Example:
- **Week 1**: Bot buys 10 TSLA shares
- **Week 2**: User sells 3 TSLA shares manually
- **Week 3**: Bot runs, TSLA still in top 5

### Bot Behavior:
1. **Detects external sale:**
   - DB ownership: 10 TSLA shares
   - Broker position: 7 TSLA shares remaining
   - Detects: 3 shares sold externally
   - Updates ownership: 7 TSLA marked as bot-owned (assumes remaining are bot-owned)
   - Records external sale for 3 shares

2. **Buy logic:**
   - TSLA in top 5 → Adds to buyback list
   - Uses external sale proceeds to buy TSLA back

---

## Key Principles

1. **Bot only sells stocks it purchased** (when persistence enabled)
2. **External sales are detected** by comparing DB ownership vs broker positions
3. **Remaining shares (up to bot purchase count) are assumed bot-owned** after external sales
4. **External sale proceeds are used for reinvestment** (buyback if still in top 5, or new stocks)
5. **Manually purchased stocks entering top 5** are bought by bot to bring to target allocation
6. **All trades are recorded** in Firestore for tracking and audit

## Trade Recording Timing

### When Trades Are Recorded

Trades are recorded in Firestore **immediately after the broker confirms the order was submitted successfully**, not when the order is filled/completed.

**Current Behavior:**
- **Order Submission**: Broker's `buy()` or `sell()` returns `True` when order is accepted
- **Trade Recording**: Trade is recorded in Firestore immediately after order submission
- **Ownership Update**: Ownership records are updated based on expected trade

### Important Considerations

⚠️ **Market Closed / Pending Orders:**
- If the market is closed, orders are accepted but not filled until market opens
- Trade is still recorded in Firestore when order is submitted
- Ownership is updated based on expected trade, not actual fill
- If order fails to fill or is cancelled, ownership records may be inaccurate

⚠️ **Order Fill vs Order Submission:**
- The bot records trades when orders are **submitted**, not when they're **filled**
- Actual fill price may differ from recorded price (uses current market price)
- Actual fill quantity may differ from requested quantity (for partial fills)

### Example Scenario

**Market Closed:**
1. Bot runs at 4:00 PM (market closed)
2. Bot submits BUY order for TSLA → Broker accepts order → Returns `True`
3. Trade is recorded in Firestore immediately
4. Ownership updated: TSLA = X shares
5. Order remains pending until next market open
6. Order fills at 9:30 AM next day at different price
7. **Discrepancy**: Firestore shows order price, actual fill may be different

### Recommendations

**For Production Use:**
- Run bot during market hours (e.g., 9:30 AM - 4:00 PM ET) to ensure immediate fills
- Consider adding order status checking to verify fills before recording
- Monitor order status and update Firestore records if orders fail to fill

**Current Limitations:**
- No order status verification after submission
- No fill price tracking (uses estimated/current price)
- No handling of partial fills or cancelled orders
- Ownership may be inaccurate if orders don't fill

### Trade History Reconciliation

The bot can reconcile Firestore records with broker trade history to update records with actual fill prices and quantities.

**How It Works:**
1. **At Start of Each Run**: Bot calls `broker.get_trade_history()` to get recent trades
2. **Matching**: Compares broker trades with Firestore records by:
   - Trade ID (if available)
   - Symbol + Action + Timestamp (within 1 hour window)
3. **Updates**: Updates Firestore records with:
   - Actual fill price (from broker)
   - Actual fill quantity (from broker)
   - Actual total (from broker)
   - Reconciliation timestamp
4. **Detection**: Identifies:
   - **Updated**: Trades that were updated with actual fill data
   - **Missing**: Broker trades not in Firestore (external trades)
   - **Unfilled**: Firestore trades not found in broker (orders that didn't fill)

**Example:**
```
Reconciliation complete: 3 updated, 1 missing, 0 unfilled
```

**Benefits:**
- ✅ Corrects fill prices after orders execute
- ✅ Handles partial fills
- ✅ Detects unfilled orders
- ✅ Identifies external trades

**Broker Support:**
- ✅ **Alpaca**: Fully implemented - uses `get_orders()` API
- ✅ **Robinhood**: Fully implemented - uses `get_all_stock_orders()` API
- ✅ **Webull**: Implemented - uses order history API (may need adjustment based on actual SDK endpoints)

**Note:** If a broker's `get_trade_history()` returns empty list, reconciliation is skipped gracefully.

### Future Improvements

Potential enhancements:
1. **Order Status Checking**: Verify order fill before recording trade
2. **Automatic Ownership Recalculation**: Recalculate ownership from reconciled trades
3. **Order Cancellation Handling**: Handle cancelled/rejected orders automatically
4. **Real-time Order Status**: Poll order status until filled
5. **Fill Price Tracking**: Always use reconciliation to get actual fill prices

## Troubleshooting

### Bot won't sell a stock
- **Check:** Is the stock in persistence DB?
- **Solution:** If manually purchased, bot won't sell it (by design)

### External sales not detected
- **Check:** Is persistence enabled?
- **Check:** Are broker positions accurate?
- **Solution:** Bot compares DB vs broker positions at each run

### Proceeds not used
- **Check:** Are there stocks to buy?
- **Check:** Is cash balance sufficient?
- **Solution:** Bot only uses proceeds when rebalancing is needed

---

For more information, see:
- [Persistence Configuration](../README.md#persistence-configuration-optional)
- [Firebase Setup](../README.md#persistence-configuration-optional)
