"""Portfolio rebalancing logic."""

import logging
from typing import List, Optional
from ..broker import Broker
from ..broker.models import Allocation, TradeSummary
from ..leaderboard import LeaderboardClient
from ..notifications import EmailNotifier

logger = logging.getLogger(__name__)


class Rebalancer:
    """Handles portfolio rebalancing based on leaderboard rankings."""
    
    def __init__(
        self,
        broker: Broker,
        leaderboard_client: LeaderboardClient,
        initial_capital: float,
        email_notifier: Optional[EmailNotifier] = None,
    ):
        """
        Initialize rebalancer.
        
        Args:
            broker: Broker instance
            leaderboard_client: Leaderboard API client
            initial_capital: Initial capital for portfolio allocation
            email_notifier: Optional email notifier
        """
        self.broker = broker
        self.leaderboard_client = leaderboard_client
        self.initial_capital = initial_capital
        self.email_notifier = email_notifier
    
    def rebalance(self, dry_run: bool = False) -> TradeSummary:
        """
        Execute portfolio rebalancing based on week-over-week leaderboard comparison.
        
        Args:
            dry_run: If True, print actions but don't execute trades. If False, execute trades normally.
        
        Returns:
            TradeSummary with details of executed trades (or simulated trades in dry-run mode)
        """
        logger.info("Starting portfolio rebalancing")
        
        # Fetch current week (week-1) and previous week (week-2) leaderboards
        try:
            # Current week (week-1): previous Sunday
            current_week_mom_day = self.leaderboard_client._get_previous_sunday()
            current_week_symbols = self.leaderboard_client.get_top_symbols(top_n=5, mom_day=current_week_mom_day)
            logger.info(f"Current week (week-1) leaderboard top 5: {current_week_symbols}")
            
            # Previous week (week-2): Sunday from two weeks ago
            previous_week_mom_day = self.leaderboard_client._get_previous_week_sunday()
            previous_week_symbols = self.leaderboard_client.get_top_symbols(top_n=5, mom_day=previous_week_mom_day)
            logger.info(f"Previous week (week-2) leaderboard top 5: {previous_week_symbols}")
        except Exception as e:
            logger.error(f"Error fetching leaderboard: {e}")
            raise
        
        # Get current allocation
        try:
            current_allocations = self.broker.get_current_allocation()
            current_symbols = {alloc.symbol.upper() for alloc in current_allocations}
            logger.info(f"Current positions: {current_symbols}")
        except Exception as e:
            logger.error(f"Error getting current allocation: {e}")
            raise
        
        # Normalize symbols to uppercase
        current_week_symbols_upper = [s.upper() for s in current_week_symbols]
        previous_week_symbols_upper = [s.upper() for s in previous_week_symbols]
        previous_week_symbols_set = {s.upper() for s in previous_week_symbols}
        
        # Check if any stocks from previous week's LB exist in current positions
        positions_from_prev_week = current_symbols & previous_week_symbols_set
        
        # Get cash balance
        try:
            cash_balance = self.broker.get_account_cash()
            logger.info(f"Current cash balance: ${cash_balance}")
        except Exception as e:
            logger.error(f"Error getting account cash: {e}")
            raise
        
        # Case 1: No stocks from previous week's LB exist and 10k cash balance exists
        if not positions_from_prev_week and cash_balance >= 10000.0:
            logger.info("No stocks from previous week's LB exist and cash balance >= $10k. Entering trades for top 5 stocks using initial_capital.")
            return self._initial_allocation(current_week_symbols_upper, self.initial_capital, dry_run=dry_run)
        
        # Case 2: Compare top 5 stocks between LB-1 and LB
        # Sell stocks that were in last week's top 5 but aren't in this week's top 5
        # Buy stocks that entered this week's top 5
        logger.info("Comparing leaderboards and executing rebalancing...")
        return self._execute_week_over_week_rebalancing(
            current_allocations,
            current_week_symbols_upper,
            previous_week_symbols_upper,
            dry_run=dry_run
        )
    
    def _allocations_match(self, allocations: List[Allocation], target_symbols: List[str]) -> bool:
        """Check if current allocations match target symbols."""
        current_symbols = {alloc.symbol.upper() for alloc in allocations}
        target_set = {s.upper() for s in target_symbols}
        
        # Check if we have exactly the top 5 symbols
        return current_symbols == target_set and len(current_symbols) == 5
    
    def _initial_allocation(self, symbols: List[str], amount: Optional[float] = None, dry_run: bool = False) -> TradeSummary:
        """
        Perform initial allocation when portfolio is empty.
        
        Args:
            symbols: List of symbols to buy
            amount: Amount to allocate. If None, uses initial_capital.
            dry_run: If True, print actions but don't execute trades.
        """
        buys = []
        allocation_amount = amount if amount is not None else self.initial_capital
        # Round to 2 decimal places (Alpaca requires notional values to be limited to 2 decimal places)
        allocation_per_stock = round(allocation_amount / len(symbols), 2)
        
        if dry_run:
            logger.info(f"[DRY-RUN] Would divide ${allocation_amount} into {len(symbols)} stocks: ${allocation_per_stock} each")
        else:
            logger.info(f"Dividing ${allocation_amount} into {len(symbols)} stocks: ${allocation_per_stock} each")
        
        for symbol in symbols:
            if dry_run:
                buys.append({
                    "symbol": symbol,
                    "quantity": 0,  # Will be estimated
                    "cost": allocation_per_stock,
                })
                logger.info(f"[DRY-RUN] Would buy ${allocation_per_stock} of {symbol}")
            else:
                try:
                    success = self.broker.buy(symbol, allocation_per_stock)
                    if success:
                        buys.append({
                            "symbol": symbol,
                            "quantity": 0,  # Will be updated after getting positions
                            "cost": allocation_per_stock,
                        })
                        logger.info(f"Bought ${allocation_per_stock} of {symbol}")
                    else:
                        logger.warning(f"Failed to buy {symbol}")
                except Exception as e:
                    logger.error(f"Error buying {symbol}: {e}")
        
        # Get updated allocations (or current if dry-run)
        try:
            final_allocations = self.broker.get_current_allocation()
            # Update quantities in buys
            for buy in buys:
                for alloc in final_allocations:
                    if alloc.symbol.upper() == buy["symbol"].upper():
                        buy["quantity"] = alloc.quantity
                        break
        except Exception as e:
            logger.error(f"Error getting final allocations: {e}")
            final_allocations = []
        
        return self._create_summary(buys, [], final_allocations)
    
    def _execute_week_over_week_rebalancing(
        self,
        current_allocations: List[Allocation],
        current_week_symbols: List[str],
        previous_week_symbols: List[str],
        dry_run: bool = False,
    ) -> TradeSummary:
        """
        Execute rebalancing based on week-over-week leaderboard comparison.
        
        Sell stocks that were in last week's top 5 but aren't in this week's top 5.
        Buy stocks that entered this week's top 5.
        
        Args:
            current_allocations: Current portfolio positions
            current_week_symbols: Top 5 symbols from current week's leaderboard
            previous_week_symbols: Top 5 symbols from previous week's leaderboard
            dry_run: If True, print actions but don't execute trades.
        """
        current_symbols = {alloc.symbol.upper() for alloc in current_allocations}
        current_week_set = {s.upper() for s in current_week_symbols}
        previous_week_set = {s.upper() for s in previous_week_symbols}
        
        # Find symbols to sell: were in previous week's top 5 but not in current week's top 5
        # Only sell if we actually hold them
        symbols_to_sell = (previous_week_set - current_week_set) & current_symbols
        
        # Find symbols to buy: in current week's top 5 but not currently held
        symbols_to_buy = current_week_set - current_symbols
        
        sells = []
        buys = []
        
        # Sell positions that dropped out of top 5
        total_proceeds = 0.0
        for symbol in symbols_to_sell:
            allocation = next((a for a in current_allocations if a.symbol.upper() == symbol), None)
            if allocation:
                if dry_run:
                    sells.append({
                        "symbol": symbol,
                        "quantity": allocation.quantity,
                        "proceeds": allocation.market_value,
                    })
                    total_proceeds += allocation.market_value
                    logger.info(f"[DRY-RUN] Would sell {allocation.quantity} shares of {symbol} for ${allocation.market_value} (dropped out of top 5)")
                else:
                    try:
                        success = self.broker.sell(symbol, allocation.quantity)
                        if success:
                            sells.append({
                                "symbol": symbol,
                                "quantity": allocation.quantity,
                                "proceeds": allocation.market_value,
                            })
                            total_proceeds += allocation.market_value
                            logger.info(f"Sold {allocation.quantity} shares of {symbol} for ${allocation.market_value} (dropped out of top 5)")
                        else:
                            logger.warning(f"Failed to sell {symbol}")
                    except Exception as e:
                        logger.error(f"Error selling {symbol}: {e}")
        
        # Use only proceeds from sales to buy new stocks
        # Get current cash balance for logging purposes only
        try:
            current_cash = self.broker.get_account_cash()
            if dry_run:
                logger.info(f"Current cash balance: ${current_cash}")
                logger.info(f"Proceeds from sales: ${total_proceeds}")
            else:
                logger.info(f"Available cash: ${current_cash}")
        except Exception as e:
            logger.error(f"Error getting account cash: {e}")
        
        # Buy new positions that entered top 5 (equal weight) using only proceeds from sales
        if symbols_to_buy:
            if total_proceeds == 0:
                logger.warning(f"Symbols to buy: {symbols_to_buy}, but no proceeds from sales. Skipping purchases.")
            else:
                # Only use proceeds from sales, not the entire cash balance
                # Round to 2 decimal places (Alpaca requires notional values to be limited to 2 decimal places)
                allocation_per_stock = round(total_proceeds / len(symbols_to_buy), 2)
                if dry_run:
                    logger.info(f"[DRY-RUN] Would buy {len(symbols_to_buy)} new stocks with ${allocation_per_stock} each (using only proceeds from sales: ${total_proceeds})")
                else:
                    logger.info(f"Buying {len(symbols_to_buy)} new stocks with ${allocation_per_stock} each (using only proceeds from sales: ${total_proceeds})")
                
                for symbol in symbols_to_buy:
                    if dry_run:
                        buys.append({
                            "symbol": symbol,
                            "quantity": 0,  # Will be estimated
                            "cost": allocation_per_stock,
                        })
                        logger.info(f"[DRY-RUN] Would buy ${allocation_per_stock} of {symbol} (entered top 5)")
                    else:
                        try:
                            success = self.broker.buy(symbol, allocation_per_stock)
                            if success:
                                buys.append({
                                    "symbol": symbol,
                                    "quantity": 0,  # Will be updated
                                    "cost": allocation_per_stock,
                                })
                                logger.info(f"Bought ${allocation_per_stock} of {symbol} (entered top 5)")
                            else:
                                logger.warning(f"Failed to buy {symbol}")
                        except Exception as e:
                            logger.error(f"Error buying {symbol}: {e}")
        
        # Get final allocations (use current if dry-run, since no trades were executed)
        try:
            final_allocations = self.broker.get_current_allocation()
            # Update quantities in buys (only if not dry-run, since in dry-run we don't have actual quantities)
            if not dry_run:
                for buy in buys:
                    for alloc in final_allocations:
                        if alloc.symbol.upper() == buy["symbol"].upper():
                            buy["quantity"] = alloc.quantity
                            break
        except Exception as e:
            logger.error(f"Error getting final allocations: {e}")
            final_allocations = []
        
        if not sells and not buys:
            if dry_run:
                logger.info("[DRY-RUN] No rebalancing needed - all positions match leaderboard changes")
            else:
                logger.info("No rebalancing needed - all positions match leaderboard changes")
        
        return self._create_summary(buys, sells, final_allocations)
    
    def _create_summary(
        self,
        buys: List[dict],
        sells: List[dict],
        final_allocations: List[Allocation],
    ) -> TradeSummary:
        """Create trade summary."""
        total_cost = sum(buy.get("cost", 0) for buy in buys)
        total_proceeds = sum(sell.get("proceeds", 0) for sell in sells)
        portfolio_value = sum(alloc.market_value for alloc in final_allocations)
        
        summary = TradeSummary(
            buys=buys,
            sells=sells,
            total_cost=total_cost,
            total_proceeds=total_proceeds,
            final_allocations=final_allocations,
            portfolio_value=portfolio_value,
        )
        
        # Note: Email notification is handled in main.py after rebalancing completes
        # to have access to config for recipient address
        
        return summary
