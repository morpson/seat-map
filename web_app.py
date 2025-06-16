import os
import logging
import threading
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Global monitoring state
monitor_thread = None
monitor_running = False
monitor_config = {}
monitor_logs = []
last_check = None
last_result = None
already_alerted = False
error_count = 0

def add_log(level, message):
    """Add a log entry"""
    global monitor_logs
    log_entry = {
        'timestamp': datetime.utcnow(),
        'level': level,
        'message': message
    }
    monitor_logs.append(log_entry)
    # Keep only last 50 logs
    if len(monitor_logs) > 50:
        monitor_logs = monitor_logs[-50:]

def is_slot_open(testflight_url):
    """Check if TestFlight slots are available"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        res = requests.get(testflight_url, timeout=10, headers=headers)
        res.raise_for_status()
        return "This beta is full." not in res.text
    except Exception as e:
        logging.error(f"Error checking TestFlight: {e}")
        raise

def send_telegram_alert(bot_token, chat_id, testflight_url):
    """Send Telegram alert when slot becomes available"""
    try:
        message = f"🚨 A TestFlight beta slot just opened! Join now:\n{testflight_url}"
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        params = {"chat_id": chat_id, "text": message}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        logging.info("Telegram alert sent successfully")
    except Exception as e:
        logging.error(f"Failed to send Telegram alert: {e}")
        raise

def monitor_loop():
    """Main monitoring loop"""
    global monitor_running, monitor_config, last_check, last_result, already_alerted, error_count
    
    logging.info("TestFlight monitoring started")
    add_log('info', 'Monitoring started')
    
    while monitor_running:
        try:
            last_check = datetime.utcnow()
            slot_available = is_slot_open(monitor_config['testflight_url'])
            last_result = slot_available
            
            if slot_available:
                if not already_alerted:
                    logging.info("Slot found! Sending Telegram alert...")
                    send_telegram_alert(
                        monitor_config['bot_token'], 
                        monitor_config['chat_id'], 
                        monitor_config['testflight_url']
                    )
                    already_alerted = True
                    add_log('success', '🚨 TestFlight slot opened! Alert sent.')
                else:
                    logging.info("Slot still open, alert already sent")
                    add_log('info', '✅ Slot still available (alert already sent)')
            else:
                logging.info("Still full, checking again...")
                add_log('info', '❌ TestFlight beta is still full')
                already_alerted = False  # Reset if it goes back to full
            
            error_count = 0  # Reset error count on successful check
            
        except Exception as e:
            error_count += 1
            logging.error(f"Monitor error: {e}")
            add_log('error', f'Monitor error: {str(e)}')
            
            # Stop monitoring after too many consecutive errors
            if error_count >= 5:
                logging.error("Too many consecutive errors, stopping monitor")
                add_log('error', 'Too many consecutive errors, stopping monitor')
                monitor_running = False
                break
        
        # Wait for the configured interval
        if monitor_running:
            time.sleep(monitor_config.get('check_interval', 60))
    
    logging.info("TestFlight monitoring stopped")
    add_log('info', 'Monitoring stopped')

@app.route('/')
def index():
    """Main dashboard page"""
    status = {
        'running': monitor_running,
        'last_check': last_check,
        'last_result': last_result,
        'already_alerted': already_alerted,
        'error_count': error_count
    }
    
    logs = list(reversed(monitor_logs))  # Most recent first
    
    return render_template('index.html', 
                         config=monitor_config, 
                         status=status, 
                         logs=logs,
                         is_monitoring=monitor_running)

@app.route('/configure', methods=['POST'])
def configure():
    """Configure monitoring settings"""
    global monitor_config
    
    try:
        bot_token = request.form.get('bot_token', '').strip()
        chat_id = request.form.get('chat_id', '').strip()
        testflight_url = request.form.get('testflight_url', '').strip()
        check_interval = int(request.form.get('check_interval', 60))
        
        if not all([bot_token, chat_id, testflight_url]):
            flash('All fields are required!', 'error')
            return redirect(url_for('index'))
        
        # Validate URL
        if 'testflight.apple.com' not in testflight_url:
            flash('Please enter a valid TestFlight URL', 'error')
            return redirect(url_for('index'))
        
        # Save configuration
        monitor_config = {
            'bot_token': bot_token,
            'chat_id': chat_id,
            'testflight_url': testflight_url,
            'check_interval': check_interval
        }
        
        flash('Configuration saved successfully!', 'success')
        
    except ValueError:
        flash('Check interval must be a valid number', 'error')
    except Exception as e:
        flash(f'Error saving configuration: {str(e)}', 'error')
        app.logger.error(f"Configuration error: {e}")
    
    return redirect(url_for('index'))

@app.route('/start')
def start_monitoring():
    """Start the monitoring process"""
    global monitor_thread, monitor_running
    
    try:
        if not monitor_config:
            flash('Please configure the monitor first', 'error')
            return redirect(url_for('index'))
        
        if monitor_running:
            flash('Monitoring is already running', 'warning')
            return redirect(url_for('index'))
        
        monitor_running = True
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        
        flash('Monitoring started!', 'success')
        
    except Exception as e:
        flash(f'Error starting monitor: {str(e)}', 'error')
        app.logger.error(f"Start monitoring error: {e}")
    
    return redirect(url_for('index'))

@app.route('/stop')
def stop_monitoring():
    """Stop the monitoring process"""
    global monitor_running
    
    try:
        if not monitor_running:
            flash('Monitoring is not running', 'warning')
            return redirect(url_for('index'))
        
        monitor_running = False
        flash('Monitoring stopped!', 'info')
        
    except Exception as e:
        flash(f'Error stopping monitor: {str(e)}', 'error')
        app.logger.error(f"Stop monitoring error: {e}")
    
    return redirect(url_for('index'))

@app.route('/clear_logs')
def clear_logs():
    """Clear all monitoring logs"""
    global monitor_logs
    
    try:
        monitor_logs = []
        flash('Logs cleared successfully!', 'success')
    except Exception as e:
        flash(f'Error clearing logs: {str(e)}', 'error')
        app.logger.error(f"Clear logs error: {e}")
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)