import threading
import time
import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime

class TestFlightMonitor:
    """Background monitor for TestFlight slot availability"""
    
    def __init__(self):
        self.thread = None
        self.running = False
        self.config = None
        self.already_alerted = False
        self.last_check = None
        self.last_result = None
        self.error_count = 0
        self.logs = []  # Store logs in memory
        
    def update_config(self, config):
        """Update monitor configuration"""
        self.config = config
        
    def is_running(self):
        """Check if monitor is currently running"""
        return self.running and self.thread and self.thread.is_alive()
    
    def start(self):
        """Start monitoring in background thread"""
        if self.is_running():
            return False
        
        if not self.config:
            raise Exception("No configuration available")
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        return True
    
    def stop(self):
        """Stop monitoring"""
        if not self.is_running():
            return False
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        return True
    
    def get_status(self):
        """Get current monitoring status"""
        return {
            'running': self.is_running(),
            'last_check': self.last_check,
            'last_result': self.last_result,
            'already_alerted': self.already_alerted,
            'error_count': self.error_count
        }
    
    def add_log(self, level, message):
        """Add a log entry"""
        log_entry = {
            'timestamp': datetime.utcnow(),
            'level': level,
            'message': message
        }
        self.logs.append(log_entry)
        # Keep only last 50 logs
        if len(self.logs) > 50:
            self.logs = self.logs[-50:]
    
    def get_logs(self):
        """Get recent log entries"""
        return list(reversed(self.logs))  # Most recent first
    
    def clear_logs(self):
        """Clear all log entries"""
        self.logs = []
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        logging.info("TestFlight monitoring started")
        
        while self.running:
            try:
                self.last_check = datetime.utcnow()
                slot_available = self._check_slot_availability()
                self.last_result = slot_available
                
                if slot_available:
                    if not self.already_alerted:
                        logging.info("Slot found! Sending Telegram alert...")
                        self._send_telegram_alert()
                        self.already_alerted = True
                        self.add_log('success', '🚨 TestFlight slot opened! Alert sent.')
                    else:
                        logging.info("Slot still open, alert already sent")
                        self.add_log('info', '✅ Slot still available (alert already sent)')
                else:
                    logging.info("Still full, checking again...")
                    self.add_log('info', '❌ TestFlight beta is still full')
                    self.already_alerted = False  # Reset if it goes back to full
                
                self.error_count = 0  # Reset error count on successful check
                
            except Exception as e:
                self.error_count += 1
                logging.error(f"Monitor error: {e}")
                self.add_log('error', f'Monitor error: {str(e)}')
                
                # Stop monitoring after too many consecutive errors
                if self.error_count >= 5:
                    logging.error("Too many consecutive errors, stopping monitor")
                    self.add_log('error', 'Too many consecutive errors, stopping monitor')
                    self.running = False
                    break
            
            # Wait for the configured interval
            if self.running and self.config:
                time.sleep(self.config['check_interval'])
        
        logging.info("TestFlight monitoring stopped")
    
    def _check_slot_availability(self):
        """Check if TestFlight slots are available"""
        if not self.config:
            return False
            
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(
                self.config['testflight_url'], 
                timeout=10,
                headers=headers
            )
            response.raise_for_status()
            
            # Check if the page indicates the beta is full
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for common indicators that the beta is full
            full_indicators = [
                "This beta is full.",
                "This beta isn't accepting any new testers right now.",
                "beta is full",
                "not accepting"
            ]
            
            page_text = response.text.lower()
            for indicator in full_indicators:
                if indicator.lower() in page_text:
                    return False
            
            # If none of the "full" indicators are found, assume slots are available
            return True
            
        except requests.RequestException as e:
            logging.error(f"Error checking TestFlight: {e}")
            raise Exception(f"Failed to check TestFlight URL: {str(e)}")
        except Exception as e:
            logging.error(f"Unexpected error checking TestFlight: {e}")
            raise
    
    def _send_telegram_alert(self):
        """Send Telegram alert when slot becomes available"""
        if not self.config:
            return False
            
        try:
            message = f"🚨 A TestFlight beta slot just opened! Join now:\n{self.config['testflight_url']}"
            
            url = f"https://api.telegram.org/bot{self.config['bot_token']}/sendMessage"
            params = {
                "chat_id": self.config['chat_id'],
                "text": message,
                "parse_mode": "HTML"
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            logging.info("Telegram alert sent successfully")
            
        except requests.RequestException as e:
            logging.error(f"Failed to send Telegram alert: {e}")
            raise Exception(f"Failed to send Telegram alert: {str(e)}")
        except Exception as e:
            logging.error(f"Unexpected error sending Telegram alert: {e}")
            raise
