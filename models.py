from datetime import datetime
from app import db

class MonitorConfig(db.Model):
    """Configuration settings for the TestFlight monitor"""
    id = db.Column(db.Integer, primary_key=True)
    bot_token = db.Column(db.String(200), nullable=False)
    chat_id = db.Column(db.String(50), nullable=False)
    testflight_url = db.Column(db.String(500), nullable=False)
    check_interval = db.Column(db.Integer, default=60)  # seconds
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @classmethod
    def get_current(cls):
        """Get the current configuration (latest one)"""
        return cls.query.order_by(cls.updated_at.desc()).first()

class MonitorLog(db.Model):
    """Log entries for monitoring activity"""
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    level = db.Column(db.String(20), nullable=False)  # info, success, warning, error
    message = db.Column(db.Text, nullable=False)
    
    @classmethod
    def add_log(cls, level, message):
        """Add a new log entry"""
        log = cls(level=level, message=message)
        db.session.add(log)
        db.session.commit()
        return log
    
    @classmethod
    def get_recent(cls, limit=50):
        """Get recent log entries"""
        return cls.query.order_by(cls.timestamp.desc()).limit(limit).all()
    
    @classmethod
    def clear_all(cls):
        """Clear all log entries"""
        cls.query.delete()
        db.session.commit()
    
    def get_bootstrap_class(self):
        """Get Bootstrap alert class for the log level"""
        level_map = {
            'info': 'alert-info',
            'success': 'alert-success',
            'warning': 'alert-warning',
            'error': 'alert-danger'
        }
        return level_map.get(self.level, 'alert-secondary')
    
    def get_icon(self):
        """Get icon for the log level"""
        icon_map = {
            'info': 'ℹ️',
            'success': '✅',
            'warning': '⚠️',
            'error': '❌'
        }
        return icon_map.get(self.level, 'ℹ️')
