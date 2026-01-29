"""SendGrid email notifier implementation."""

import logging
from typing import List, Dict, Any, Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from .email_notifier import EmailNotifier
from ..broker.models import TradeSummary, MultiPortfolioSummary

logger = logging.getLogger(__name__)


class SendGridNotifier(EmailNotifier):
    """SendGrid email notifier."""
    
    def __init__(self, api_key: str, from_email: str):
        """
        Initialize SendGrid notifier.
        
        Args:
            api_key: SendGrid API key
            from_email: From email address
        """
        self.client = SendGridAPIClient(api_key)
        self.from_email = from_email
    
    def send_trade_summary(
        self,
        recipient: str,
        trade_summary,
        leaderboard_symbols: Optional[List[str]] = None,
        portfolio_leaderboards: Optional[Dict[str, List[str]]] = None,
    ) -> bool:
        """Send trade summary email via SendGrid."""
        try:
            html_content = self._format_trade_summary_html(trade_summary, leaderboard_symbols, portfolio_leaderboards)
            text_content = self._format_trade_summary_text(trade_summary, leaderboard_symbols, portfolio_leaderboards)
            
            subject = "Portfolio Rebalancing Summary"
            if isinstance(trade_summary, MultiPortfolioSummary):
                subject = "Multi-Portfolio Rebalancing Summary"
            
            message = Mail(
                from_email=self.from_email,
                to_emails=recipient,
                subject=subject,
                html_content=html_content,
                plain_text_content=text_content,
            )
            
            response = self.client.send(message)
            logger.info(f"Trade summary email sent to {recipient}. Status: {response.status_code}")
            return response.status_code in [200, 201, 202]
            
        except Exception as e:
            logger.error(f"Error sending email via SendGrid: {e}")
            return False
    
    def send_error_notification(
        self,
        recipient: str,
        error_message: str,
        context: Dict[str, Any] = None,
    ) -> bool:
        """Send error notification email via SendGrid."""
        try:
            content = f"Error in Trading Bot:\n\n{error_message}\n\nContext: {context or 'N/A'}"
            
            message = Mail(
                from_email=self.from_email,
                to_emails=recipient,
                subject="Trading Bot Error",
                plain_text_content=content,
            )
            
            response = self.client.send(message)
            logger.info(f"Error notification email sent to {recipient}. Status: {response.status_code}")
            return response.status_code in [200, 201, 202]
            
        except Exception as e:
            logger.error(f"Error sending error email via SendGrid: {e}")
            return False
