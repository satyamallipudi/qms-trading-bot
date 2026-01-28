"""Main application entry point."""

import logging
import signal
import sys
from typing import Optional
from datetime import datetime
import pytz

from .config import get_config
from .broker import create_broker
from .leaderboard import LeaderboardClient
from .notifications import create_email_notifier
from .trading import Rebalancer
from .scheduler import create_scheduler
from .api import create_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class TradingBot:
    """Main trading bot application."""
    
    def __init__(self):
        """Initialize the trading bot."""
        self.config = get_config()
        self.broker = None
        self.leaderboard_client = None
        self.email_notifier = None
        self.rebalancer = None
        self.scheduler = None
        self.app = None
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}. Shutting down...")
        self.shutdown()
        sys.exit(0)
    
    def initialize(self):
        """Initialize all components."""
        logger.info("Initializing trading bot...")
        
        # Initialize broker
        try:
            self.broker = create_broker()
            logger.info(f"Initialized broker: {self.config.broker.broker_type}")
        except Exception as e:
            logger.error(f"Error initializing broker: {e}")
            raise
        
        # Initialize leaderboard client
        try:
            self.leaderboard_client = LeaderboardClient(
                api_url=self.config.leaderboard_api_url,
                api_token=self.config.leaderboard_api_token,
            )
            logger.info("Initialized leaderboard client")
        except Exception as e:
            logger.error(f"Error initializing leaderboard client: {e}")
            raise
        
        # Initialize email notifier
        self.email_notifier = create_email_notifier()
        if self.email_notifier:
            logger.info(f"Initialized email notifier: {self.config.email.provider}")
        else:
            logger.info("Email notifications disabled")
        
        # Initialize rebalancer
        self.rebalancer = Rebalancer(
            broker=self.broker,
            leaderboard_client=self.leaderboard_client,
            initial_capital=self.config.initial_capital,
            email_notifier=self.email_notifier,
        )
        logger.info("Initialized rebalancer")
        
        # Initialize scheduler based on mode
        if self.config.scheduler.mode == "internal":
            self.scheduler = create_scheduler(job_function=self._execute_rebalancing)
            logger.info(f"Initialized internal scheduler with cron: {self.config.scheduler.cron_schedule}")
        else:
            # External scheduler mode - create webhook app
            self.app = create_app(
                job_function=self._execute_rebalancing,
                webhook_secret=self.config.scheduler.webhook_secret,
            )
            logger.info(f"Initialized webhook endpoint on port {self.config.scheduler.webhook_port}")
    
    def _is_market_open_time(self) -> bool:
        """
        Check if current time is 9:30 AM Eastern Time (market open).
        This ensures timezone-aware scheduling works correctly with DST.
        Allows a 5-minute window (9:28-9:33 AM) to account for scheduling delays.
        
        Returns:
            True if it's around 9:30 AM ET on Monday, False otherwise
        """
        # Get current time in Eastern Time
        eastern = pytz.timezone('America/New_York')
        now_et = datetime.now(eastern)
        
        # Check if it's Monday
        is_monday = now_et.weekday() == 0  # Monday is 0
        
        if not is_monday:
            logger.info(
                f"Skipping execution - not Monday. "
                f"Current ET time: {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')}, "
                f"Day: {now_et.strftime('%A')}"
            )
            return False
        
        # Check if it's within 5 minutes of 9:30 AM (9:28-9:33 AM)
        # This accounts for potential GitHub Actions scheduling delays
        current_minute = now_et.hour * 60 + now_et.minute
        target_minute = 9 * 60 + 30  # 9:30 AM
        time_diff = abs(current_minute - target_minute)
        
        if time_diff <= 5:  # Within 5 minutes of 9:30 AM
            logger.info(
                f"Market open time confirmed: {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')} "
                f"(within {time_diff} minutes of 9:30 AM ET)"
            )
            return True
        
        logger.info(
            f"Skipping execution - not market open time. "
            f"Current ET time: {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')}, "
            f"Expected: Monday 9:30 AM ET (±5 min)"
        )
        return False
    
    def _execute_rebalancing(self):
        """Execute rebalancing (wrapper for scheduler/webhook)."""
        # Timezone-aware check: only execute at 9:30 AM Eastern Time
        # This handles DST automatically since we check the actual ET time
        if not self._is_market_open_time():
            logger.info("Not executing rebalancing - not at market open time (9:30 AM ET)")
            return None
        
        try:
            logger.info("Executing rebalancing...")
            summary = self.rebalancer.rebalance()
            logger.info(f"Rebalancing completed. Portfolio value: ${summary.portfolio_value:.2f}")
            
            # Send email notification if enabled
            if self.email_notifier and self.config.email.recipient:
                try:
                    leaderboard_symbols = self.leaderboard_client.get_top_symbols(top_n=5)
                    self.email_notifier.send_trade_summary(
                        recipient=self.config.email.recipient,
                        trade_summary=summary,
                        leaderboard_symbols=leaderboard_symbols,
                    )
                except Exception as email_error:
                    logger.error(f"Error sending email notification: {email_error}")
            
            return summary
        except Exception as e:
            logger.error(f"Error during rebalancing: {e}")
            # Send error notification if email is enabled
            if self.email_notifier and self.config.email.recipient:
                try:
                    self.email_notifier.send_error_notification(
                        recipient=self.config.email.recipient,
                        error_message=str(e),
                        context={"component": "rebalancer"},
                    )
                except Exception as email_error:
                    logger.error(f"Error sending error notification: {email_error}")
            raise
    
    def run(self):
        """Run the trading bot."""
        self.initialize()
        
        logger.info("=" * 60)
        logger.info("Trading Bot Started")
        logger.info(f"Broker: {self.config.broker.broker_type}")
        logger.info(f"Scheduler Mode: {self.config.scheduler.mode}")
        logger.info(f"Email: {'Enabled' if self.email_notifier else 'Disabled'}")
        logger.info("=" * 60)
        
        if self.config.scheduler.mode == "internal":
            # Run with internal scheduler
            try:
                self.scheduler.start()
            except KeyboardInterrupt:
                logger.info("Shutting down...")
                self.shutdown()
        else:
            # Run with webhook endpoint
            try:
                self.app.run(
                    host="0.0.0.0",
                    port=self.config.scheduler.webhook_port,
                    debug=False,
                )
            except KeyboardInterrupt:
                logger.info("Shutting down...")
                self.shutdown()
    
    def shutdown(self):
        """Shutdown the trading bot."""
        logger.info("Shutting down trading bot...")
        if self.scheduler:
            self.scheduler.shutdown()


def main():
    """Main entry point."""
    bot = TradingBot()
    bot.run()


if __name__ == "__main__":
    main()
