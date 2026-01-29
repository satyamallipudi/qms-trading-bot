"""SMTP email notifier implementation."""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Optional

from .email_notifier import EmailNotifier
from ..broker.models import TradeSummary, MultiPortfolioSummary

logger = logging.getLogger(__name__)


class SMTPNotifier(EmailNotifier):
    """SMTP email notifier using Python's smtplib."""
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: str,
        from_email: str,
    ):
        """
        Initialize SMTP notifier.
        
        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            smtp_username: SMTP username
            smtp_password: SMTP password
            from_email: From email address
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.from_email = from_email
    
    def _send_email(
        self,
        recipient: str,
        subject: str,
        text_content: str,
        html_content: str,
    ) -> bool:
        """Send email via SMTP."""
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_email
            msg["To"] = recipient
            
            part1 = MIMEText(text_content, "plain")
            part2 = MIMEText(html_content, "html")
            
            msg.attach(part1)
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Trade summary email sent to {recipient}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email via SMTP: {e}")
            return False
    
    def send_error_notification(
        self,
        recipient: str,
        error_message: str,
        context: Dict[str, Any] = None,
    ) -> bool:
        """Send error notification email via SMTP."""
        try:
            msg = MIMEText(f"Error in Trading Bot:\n\n{error_message}\n\nContext: {context or 'N/A'}")
            msg["Subject"] = "Trading Bot Error"
            msg["From"] = self.from_email
            msg["To"] = recipient
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Error notification email sent to {recipient}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending error email via SMTP: {e}")
            return False
