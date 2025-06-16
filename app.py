import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Import monitor after app is configured
from monitor import TestFlightMonitor

# Global monitor instance
monitor = TestFlightMonitor()

@app.route('/')
def index():
    """Main dashboard page"""
    config = session.get('config', {})
    status = monitor.get_status()
    logs = monitor.get_logs()
    
    return render_template('index.html', 
                         config=config, 
                         status=status, 
                         logs=logs,
                         is_monitoring=monitor.is_running())

@app.route('/configure', methods=['POST'])
def configure():
    """Configure monitoring settings"""
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
        
        # Save configuration in session
        config = {
            'bot_token': bot_token,
            'chat_id': chat_id,
            'testflight_url': testflight_url,
            'check_interval': check_interval
        }
        session['config'] = config
        
        # Update monitor configuration
        monitor.update_config(config)
        
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
    try:
        config = session.get('config')
        if not config:
            flash('Please configure the monitor first', 'error')
            return redirect(url_for('index'))
        
        if monitor.start():
            flash('Monitoring started!', 'success')
            monitor.add_log('info', 'Monitoring started')
        else:
            flash('Monitoring is already running', 'warning')
            
    except Exception as e:
        flash(f'Error starting monitor: {str(e)}', 'error')
        app.logger.error(f"Start monitoring error: {e}")
    
    return redirect(url_for('index'))

@app.route('/stop')
def stop_monitoring():
    """Stop the monitoring process"""
    try:
        if monitor.stop():
            flash('Monitoring stopped!', 'info')
            monitor.add_log('info', 'Monitoring stopped')
        else:
            flash('Monitoring is not running', 'warning')
            
    except Exception as e:
        flash(f'Error stopping monitor: {str(e)}', 'error')
        app.logger.error(f"Stop monitoring error: {e}")
    
    return redirect(url_for('index'))

@app.route('/clear_logs')
def clear_logs():
    """Clear all monitoring logs"""
    try:
        monitor.clear_logs()
        flash('Logs cleared successfully!', 'success')
    except Exception as e:
        flash(f'Error clearing logs: {str(e)}', 'error')
        app.logger.error(f"Clear logs error: {e}")
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
