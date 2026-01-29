"""AWS SES email notifier implementation."""

import logging
from typing import List, Dict, Any, Optional, Union
import boto3
from botocore.exceptions import ClientError

from .email_notifier import EmailNotifier
from ..broker.models import TradeSummary, MultiPortfolioSummary

logger = logging.getLogger(__name__)


class SESNotifier(EmailNotifier):
    """AWS SES email notifier."""
    
    def __init__(
        self,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        from_email: str,
    ):
        """
        Initialize SES notifier.
        
        Args:
            region: AWS region
            access_key_id: AWS access key ID
            secret_access_key: AWS secret access key
            from_email: From email address
        """
        self.ses_client = boto3.client(
            "ses",
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )
        self.from_email = from_email
    
    def _send_email(
        self,
        recipient: str,
        subject: str,
        text_content: str,
        html_content: str,
    ) -> bool:
        """Send email via AWS SES."""
        try:
            response = self.ses_client.send_email(
                Source=self.from_email,
                Destination={"ToAddresses": [recipient]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": text_content, "Charset": "UTF-8"},
                        "Html": {"Data": html_content, "Charset": "UTF-8"},
                    },
                },
            )
            
            logger.info(f"Trade summary email sent to {recipient}. MessageId: {response['MessageId']}")
            return True
            
        except ClientError as e:
            logger.error(f"Error sending email via SES: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email via SES: {e}")
            return False
    
    def send_error_notification(
        self,
        recipient: str,
        error_message: str,
        context: Dict[str, Any] = None,
    ) -> bool:
        """Send error notification email via AWS SES."""
        try:
            content = f"Error in Trading Bot:\n\n{error_message}\n\nContext: {context or 'N/A'}"
            
            response = self.ses_client.send_email(
                Source=self.from_email,
                Destination={"ToAddresses": [recipient]},
                Message={
                    "Subject": {"Data": "Trading Bot Error", "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": content, "Charset": "UTF-8"}},
                },
            )
            
            logger.info(f"Error notification email sent to {recipient}. MessageId: {response['MessageId']}")
            return True
            
        except ClientError as e:
            logger.error(f"Error sending error email via SES: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending error email via SES: {e}")
            return False
