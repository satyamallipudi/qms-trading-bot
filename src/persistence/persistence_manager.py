"""Persistence manager for tracking trades and ownership in Firebase Firestore."""

import os
import json
from datetime import datetime, timedelta, timedelta
from typing import Dict, List, Optional, Set, Union
from pathlib import Path

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    from google.cloud.firestore_v1.base_query import FieldFilter
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    FieldFilter = None

from .models import TradeRecord, OwnershipRecord, ExternalSaleRecord
from src.broker.models import Allocation
from typing import List as TypingList


class PersistenceManager:
    """Manages trade and ownership persistence in Firebase Firestore."""
    
    def __init__(self, project_id: str, credentials_path: Optional[str] = None, credentials_json: Optional[str] = None):
        """
        Initialize Firebase connection.
        
        Args:
            project_id: Firebase project ID
            credentials_path: Path to Firebase service account JSON file (optional if credentials_json is provided)
            credentials_json: Firebase service account JSON as string (optional if credentials_path is provided)
        """
        if not FIREBASE_AVAILABLE:
            raise ImportError("firebase-admin is not installed. Install it with: pip install firebase-admin")
        
        # Validate that at least one credential method is provided
        if not credentials_path and not credentials_json:
            raise ValueError("Either credentials_path or credentials_json must be provided")
        
        # Initialize Firebase Admin SDK
        if credentials_json:
            # Parse JSON string and create credentials from dict
            try:
                cred_dict = json.loads(credentials_json)
                cred = credentials.Certificate(cred_dict)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in credentials_json: {e}")
        else:
            # Use file path
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(f"Firebase credentials file not found: {credentials_path}")
            cred = credentials.Certificate(credentials_path)
        
        try:
            firebase_admin.initialize_app(cred, {'projectId': project_id})
        except ValueError:
            # App already initialized (e.g., in tests)
            pass
        
        self.db = firestore.client()
        self.project_id = project_id
    
    def record_trade(self, trade: TradeRecord) -> None:
        """Record a trade in Firestore."""
        collection = self.db.collection('trades')
        doc_ref = collection.document()
        doc_ref.set(trade.to_dict())
        
        # Update ownership record
        self._update_ownership(trade)
    
    def _update_ownership(self, trade: TradeRecord) -> None:
        """Update ownership record based on trade."""
        symbol = trade.symbol.upper()
        portfolio_name = trade.portfolio_name
        # Use composite key: {portfolio_name}_{symbol}
        doc_id = f"{portfolio_name}_{symbol}"
        ownership_ref = self.db.collection('ownership').document(doc_id)
        ownership_doc = ownership_ref.get()
        
        if trade.action == "BUY":
            # Calculate quantity from total cost and price if quantity is 0 or not provided
            if trade.quantity <= 0 and trade.price > 0:
                calculated_quantity = trade.total / trade.price
            else:
                calculated_quantity = trade.quantity
            
            if ownership_doc.exists:
                # Update existing ownership
                data = ownership_doc.to_dict()
                old_quantity = data.get('quantity', 0.0)
                old_cost = data.get('total_cost', 0.0)
                
                new_quantity = old_quantity + calculated_quantity
                new_cost = old_cost + trade.total
                
                ownership_ref.update({
                    'quantity': new_quantity,
                    'total_cost': new_cost,
                    'last_purchase_date': trade.timestamp,
                    'last_updated': trade.timestamp,
                })
            else:
                # Create new ownership record
                ownership_ref.set({
                    'symbol': symbol,
                    'portfolio_name': portfolio_name,
                    'quantity': calculated_quantity,
                    'total_cost': trade.total,
                    'first_purchase_date': trade.timestamp,
                    'last_purchase_date': trade.timestamp,
                    'last_updated': trade.timestamp,
                })
        
        elif trade.action == "SELL":
            if ownership_doc.exists:
                data = ownership_doc.to_dict()
                old_quantity = data.get('quantity', 0.0)
                old_cost = data.get('total_cost', 0.0)
                
                # Calculate cost basis proportionally
                if old_quantity > 0:
                    cost_per_share = old_cost / old_quantity
                    cost_of_sold = cost_per_share * trade.quantity
                    new_quantity = old_quantity - trade.quantity
                    new_cost = old_cost - cost_of_sold
                    
                    if new_quantity <= 0:
                        # All shares sold, delete ownership record
                        ownership_ref.delete()
                    else:
                        ownership_ref.update({
                            'quantity': new_quantity,
                            'total_cost': new_cost,
                            'last_updated': trade.timestamp,
                        })
    
    def get_owned_symbols(self, portfolio_name: str = "SP400") -> Set[str]:
        """Get set of symbols we own according to persistence for a specific portfolio."""
        ownership_ref = self.db.collection('ownership')
        # Use FieldFilter to avoid positional argument warning
        if FieldFilter:
            docs = ownership_ref.where(filter=FieldFilter('portfolio_name', '==', portfolio_name)).stream()
        else:
            # Fallback to positional arguments if FieldFilter not available
            docs = ownership_ref.where('portfolio_name', '==', portfolio_name).stream()
        
        owned_symbols = set()
        for doc in docs:
            data = doc.to_dict()
            quantity = data.get('quantity', 0.0)
            if quantity > 0:
                owned_symbols.add(data.get('symbol', '').upper())
        
        return owned_symbols
    
    def get_ownership_quantity(self, symbol: str, portfolio_name: str = "SP400") -> float:
        """Get owned quantity for a symbol in a specific portfolio."""
        symbol = symbol.upper()
        doc_id = f"{portfolio_name}_{symbol}"
        ownership_ref = self.db.collection('ownership').document(doc_id)
        ownership_doc = ownership_ref.get()
        
        if ownership_doc.exists:
            data = ownership_doc.to_dict()
            return data.get('quantity', 0.0)
        return 0.0
    
    def can_sell(self, symbol: str, quantity: float, portfolio_name: str = "SP400") -> bool:
        """Check if we can sell the requested quantity for a specific portfolio."""
        owned_quantity = self.get_ownership_quantity(symbol, portfolio_name)
        return owned_quantity >= quantity
    
    def get_total_tracked_ownership(self, symbol: str) -> float:
        """Get total tracked ownership across all portfolios for a symbol."""
        symbol = symbol.upper()
        ownership_ref = self.db.collection('ownership')
        if FieldFilter:
            docs = ownership_ref.where(filter=FieldFilter('symbol', '==', symbol)).stream()
        else:
            docs = ownership_ref.where('symbol', '==', symbol).stream()
        
        total_quantity = 0.0
        for doc in docs:
            data = doc.to_dict()
            quantity = data.get('quantity', 0.0)
            if quantity > 0:
                total_quantity += quantity
        
        return total_quantity
    
    def get_portfolio_fraction(self, symbol: str, portfolio_name: str) -> float:
        """Calculate portfolio's fraction of total tracked ownership for a symbol."""
        symbol = symbol.upper()
        portfolio_quantity = self.get_ownership_quantity(symbol, portfolio_name)
        total_quantity = self.get_total_tracked_ownership(symbol)
        
        if total_quantity == 0:
            return 0.0
        
        return portfolio_quantity / total_quantity
    
    def get_all_portfolios_owning_symbol(self, symbol: str) -> TypingList[str]:
        """Get list of portfolio names that own a symbol."""
        symbol = symbol.upper()
        ownership_ref = self.db.collection('ownership')
        if FieldFilter:
            docs = ownership_ref.where(filter=FieldFilter('symbol', '==', symbol)).stream()
        else:
            docs = ownership_ref.where('symbol', '==', symbol).stream()
        
        portfolios = []
        for doc in docs:
            data = doc.to_dict()
            quantity = data.get('quantity', 0.0)
            portfolio_name = data.get('portfolio_name', 'SP400')
            if quantity > 0 and portfolio_name not in portfolios:
                portfolios.append(portfolio_name)
        
        return portfolios
    
    def detect_external_sales(
        self,
        broker_allocations: List[Allocation],
        broker_transactions: Optional[List[dict]] = None,
        portfolio_name: str = "SP400"
    ) -> List[ExternalSaleRecord]:
        """Detect external sales by comparing DB ownership vs broker positions for a specific portfolio."""
        external_sales = []
        
        # Get DB ownership for this portfolio
        db_ownership: Dict[str, float] = {}
        ownership_ref = self.db.collection('ownership')
        if FieldFilter:
            docs = ownership_ref.where(filter=FieldFilter('portfolio_name', '==', portfolio_name)).stream()
        else:
            docs = ownership_ref.where('portfolio_name', '==', portfolio_name).stream()
        for doc in docs:
            data = doc.to_dict()
            symbol = data.get('symbol', '').upper()
            quantity = data.get('quantity', 0.0)
            if quantity > 0:
                db_ownership[symbol] = quantity
        
        # Get broker positions
        broker_positions: Dict[str, float] = {}
        for allocation in broker_allocations:
            symbol = allocation.symbol.upper()
            broker_positions[symbol] = allocation.quantity
        
        # Compare: if DB says we own more than broker has, external sale occurred
        for symbol, db_quantity in db_ownership.items():
            broker_quantity = broker_positions.get(symbol, 0.0)
            if db_quantity > broker_quantity:
                # Calculate how many bot-owned shares were sold
                # Strategy: Assume remaining shares (up to bot's purchase count) are bot-owned
                # This allows bot to continue managing remaining shares
                
                doc_id = f"{portfolio_name}_{symbol}"
                ownership_ref = self.db.collection('ownership').document(doc_id)
                ownership_doc = ownership_ref.get()
                if not ownership_doc.exists:
                    continue
                
                data = ownership_doc.to_dict()
                total_cost = data.get('total_cost', 0.0)
                cost_per_share = total_cost / db_quantity if db_quantity > 0 else 0.0
                
                if broker_quantity == 0:
                    # All bot-owned shares were sold (broker has none)
                    sold_quantity = db_quantity
                    estimated_proceeds = cost_per_share * sold_quantity
                    # Delete ownership record
                    ownership_ref.delete()
                elif broker_quantity < db_quantity:
                    # Some shares were sold externally
                    # Assume remaining shares (up to bot's purchase count) are bot-owned
                    sold_quantity = db_quantity - broker_quantity
                    estimated_proceeds = cost_per_share * sold_quantity
                    
                    # Update ownership: keep broker_quantity as bot-owned
                    # Adjust cost basis proportionally
                    remaining_cost = total_cost * (broker_quantity / db_quantity)
                    ownership_ref.update({
                        'quantity': broker_quantity,
                        'total_cost': remaining_cost,
                        'last_updated': datetime.now(),
                    })
                else:
                    # broker_quantity >= db_quantity (shouldn't happen, but handle gracefully)
                    continue
                
                external_sale = ExternalSaleRecord(
                    symbol=symbol,
                    quantity=sold_quantity,
                    estimated_proceeds=estimated_proceeds,
                    detected_date=datetime.now(),
                    portfolio_name=portfolio_name,
                )
                external_sales.append(external_sale)
                
                # Record external sale
                self._record_external_sale(external_sale)
        
        # Also check broker transactions if available
        if broker_transactions:
            external_sales.extend(self._detect_external_sales_from_transactions(broker_transactions))
        
        return external_sales
    
    def _detect_external_sales_from_transactions(self, transactions: List[dict]) -> List[ExternalSaleRecord]:
        """Detect external sales by comparing broker transactions with DB records."""
        external_sales = []
        
        # Get all DB trades
        db_trades: Set[str] = set()
        trades_ref = self.db.collection('trades')
        docs = trades_ref.stream()
        for doc in docs:
            data = doc.to_dict()
            trade_id = data.get('trade_id')
            if trade_id:
                db_trades.add(trade_id)
        
        # Check broker transactions
        for transaction in transactions:
            trade_id = transaction.get('id') or transaction.get('trade_id')
            action = transaction.get('side', '').upper() or transaction.get('action', '').upper()
            
            if action == "SELL" and trade_id and trade_id not in db_trades:
                # This is a sell transaction not in our DB
                symbol = transaction.get('symbol', '').upper()
                quantity = float(transaction.get('quantity', 0))
                price = float(transaction.get('price', 0))
                proceeds = quantity * price
                
                external_sale = ExternalSaleRecord(
                    symbol=symbol,
                    quantity=quantity,
                    estimated_proceeds=proceeds,
                    detected_date=datetime.now(),
                )
                external_sales.append(external_sale)
                self._record_external_sale(external_sale)
        
        return external_sales
    
    def _record_external_sale(self, sale: ExternalSaleRecord) -> None:
        """Record an external sale detection."""
        collection = self.db.collection('external_sales')
        doc_ref = collection.document()
        doc_ref.set(sale.to_dict())
    
    def get_unused_external_sale_proceeds(self, portfolio_name: str = "SP400") -> float:
        """Get total proceeds from external sales not yet used for reinvestment for a specific portfolio."""
        external_sales_ref = self.db.collection('external_sales')
        if FieldFilter:
            docs = external_sales_ref.where(filter=FieldFilter('used_for_reinvestment', '==', False)).where(filter=FieldFilter('portfolio_name', '==', portfolio_name)).stream()
        else:
            docs = external_sales_ref.where('used_for_reinvestment', '==', False).where('portfolio_name', '==', portfolio_name).stream()
        
        total_proceeds = 0.0
        for doc in docs:
            data = doc.to_dict()
            total_proceeds += data.get('estimated_proceeds', 0.0)
        
        return total_proceeds
    
    def mark_external_sales_used(self, amount: float, portfolio_name: str = "SP400") -> None:
        """Mark external sales as used for reinvestment for a specific portfolio."""
        external_sales_ref = self.db.collection('external_sales')
        if FieldFilter:
            docs = external_sales_ref.where(filter=FieldFilter('used_for_reinvestment', '==', False)).where(filter=FieldFilter('portfolio_name', '==', portfolio_name)).stream()
        else:
            docs = external_sales_ref.where('used_for_reinvestment', '==', False).where('portfolio_name', '==', portfolio_name).stream()
        
        remaining = amount
        for doc in docs:
            if remaining <= 0:
                break
            
            data = doc.to_dict()
            proceeds = data.get('estimated_proceeds', 0.0)
            
            if proceeds <= remaining:
                # Mark this sale as fully used
                doc.reference.update({
                    'used_for_reinvestment': True,
                    'reinvestment_date': datetime.now(),
                })
                remaining -= proceeds
            else:
                # Partial use - would need to split records, but for simplicity mark as used
                doc.reference.update({
                    'used_for_reinvestment': True,
                    'reinvestment_date': datetime.now(),
                })
                remaining = 0
    
    def reconcile_with_broker_history(self, broker_trades: List[dict]) -> dict:
        """
        Reconcile Firestore trade records with broker trade history.
        
        Args:
            broker_trades: List of trade dicts from broker with keys:
                symbol, action, quantity, price, total, timestamp, trade_id
        
        Returns:
            Dictionary with reconciliation results:
            {
                'updated': int,  # Number of trades updated
                'missing': int,   # Number of broker trades not in Firestore
                'unfilled': int   # Number of Firestore trades not filled in broker
            }
        """
        if not broker_trades:
            return {'updated': 0, 'missing': 0, 'unfilled': 0}
        
        # Get all Firestore trades from recent period for this portfolio
        trades_ref = self.db.collection('trades')
        # Get trades from last 7 days (adjust as needed)
        cutoff_date = datetime.now() - timedelta(days=7)
        
        db_trades = {}
        db_trades_by_id = {}
        # Note: reconcile_with_broker_history doesn't have portfolio_name parameter yet
        # For now, filter by portfolio_name if provided in broker_trades
        if FieldFilter:
            query = trades_ref.where(filter=FieldFilter('timestamp', '>=', cutoff_date))
        else:
            query = trades_ref.where('timestamp', '>=', cutoff_date)
        
        for doc in query.stream():
            data = doc.to_dict()
            trade_id = data.get('trade_id')
            symbol = data.get('symbol', '').upper()
            action = data.get('action', '').upper()
            timestamp = data.get('timestamp')
            doc_portfolio = data.get('portfolio_name', 'SP400')
            
            # Create key for matching
            key = f"{symbol}_{action}_{timestamp}"
            db_trades[key] = {
                'doc_id': doc.id,
                'data': data,
                'matched': False
            }
            
            if trade_id:
                db_trades_by_id[trade_id] = {
                    'doc_id': doc.id,
                    'data': data,
                    'matched': False
                }
        
        # Match broker trades with Firestore records
        updated_count = 0
        missing_count = 0
        
        for broker_trade in broker_trades:
            symbol = broker_trade.get('symbol', '').upper()
            action = broker_trade.get('action', '').upper()
            trade_id = broker_trade.get('trade_id')
            broker_quantity = broker_trade.get('quantity', 0.0)
            broker_price = broker_trade.get('price', 0.0)
            broker_total = broker_trade.get('total', 0.0)
            broker_timestamp = broker_trade.get('timestamp')
            
            # Try to match by trade_id first
            matched = False
            if trade_id and trade_id in db_trades_by_id:
                db_trade = db_trades_by_id[trade_id]
                matched = True
            else:
                # Try to match by symbol, action, and timestamp (within 1 hour)
                for key, db_trade in db_trades.items():
                    if db_trade['matched']:
                        continue
                    
                    db_data = db_trade['data']
                    db_symbol = db_data.get('symbol', '').upper()
                    db_action = db_data.get('action', '').upper()
                    db_timestamp = db_data.get('timestamp')
                    
                    if (db_symbol == symbol and db_action == action and 
                        broker_timestamp and db_timestamp):
                        # Check if timestamps are within 1 hour
                        # Handle both datetime objects and Firestore Timestamp objects
                        if hasattr(db_timestamp, 'timestamp'):
                            db_ts = db_timestamp.timestamp()
                        elif isinstance(db_timestamp, datetime):
                            db_ts = db_timestamp.timestamp()
                        else:
                            continue
                        
                        if isinstance(broker_timestamp, datetime):
                            broker_ts = broker_timestamp.timestamp()
                        else:
                            continue
                        
                        time_diff = abs(broker_ts - db_ts)
                        if time_diff < 3600:  # 1 hour
                            matched = True
                            break
            
            if matched:
                # Update Firestore record with actual fill data
                db_data = db_trade['data']
                doc_id = db_trade['doc_id']
                
                # Check if update is needed
                needs_update = False
                if abs(db_data.get('quantity', 0) - broker_quantity) > 0.01:
                    needs_update = True
                if abs(db_data.get('price', 0) - broker_price) > 0.01:
                    needs_update = True
                if abs(db_data.get('total', 0) - broker_total) > 0.01:
                    needs_update = True
                
                if needs_update:
                    doc_ref = trades_ref.document(doc_id)
                    doc_ref.update({
                        'quantity': broker_quantity,
                        'price': broker_price,
                        'total': broker_total,
                        'reconciled_at': datetime.now(),
                        'trade_id': trade_id or db_data.get('trade_id'),
                    })
                    
                    # Update ownership if quantity changed
                    if db_data.get('action') == 'BUY' or db_data.get('action') == 'SELL':
                        # Recalculate ownership - this is complex, so we'll just log it
                        # In production, you might want to recalculate ownership from all trades
                        pass
                    
                    updated_count += 1
                
                db_trade['matched'] = True
            else:
                # Broker trade not found in Firestore - might be external trade
                missing_count += 1
        
        # Find Firestore trades that weren't matched (unfilled orders)
        unfilled_count = 0
        for db_trade in db_trades.values():
            if not db_trade['matched']:
                # Check if this trade is recent (within last 24 hours)
                db_timestamp = db_trade['data'].get('timestamp')
                if db_timestamp:
                    # Handle Firestore Timestamp objects
                    if hasattr(db_timestamp, 'timestamp'):
                        db_ts = db_timestamp.timestamp()
                    elif isinstance(db_timestamp, datetime):
                        db_ts = db_timestamp.timestamp()
                    else:
                        continue
                    
                    now_ts = datetime.now().timestamp()
                    time_diff = now_ts - db_ts
                    if time_diff < 86400:  # 24 hours
                        # Mark as potentially unfilled
                        doc_ref = trades_ref.document(db_trade['doc_id'])
                        doc_ref.update({
                            'reconciliation_status': 'unfilled',
                            'reconciled_at': datetime.now(),
                        })
                        unfilled_count += 1
        
        return {
            'updated': updated_count,
            'missing': missing_count,
            'unfilled': unfilled_count
        }
