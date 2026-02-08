import bpy
import time
import inspect
from enum import Enum

class LogLevel(Enum):
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4

class Logger:
    """
    Structured logging system for Light Wrangler addon.
    Provides clear, detailed, and concise reports in the terminal.
    """
    _instance = None
    _log_level = LogLevel.CRITICAL
    _indent_level = 0
    _start_time = None
    _section_times = {}
    _current_section = None
    _addon_name = "Light Wrangler"
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = Logger()
        return cls._instance
    
    def __init__(self):
        self._start_time = time.time()
    
    def set_log_level(self, level):
        """Set the minimum log level to display."""
        if isinstance(level, LogLevel):
            self._log_level = level
        elif isinstance(level, str):
            level = level.upper()
            for log_level in LogLevel:
                if log_level.name == level:
                    self._log_level = log_level
                    break
    
    def _format_message(self, message, level):
        """Format the log message with appropriate prefixes and indentation."""
        indent = "  " * self._indent_level
        prefix = f"[{self._addon_name}] [{level.name}]"
        
        # Add timing information for INFO level and above
        if level.value >= LogLevel.INFO.value:
            elapsed = time.time() - self._start_time
            timing = f"[{elapsed:.3f}s]"
            prefix = f"{prefix} {timing}"
        
        return f"{prefix} {indent}{message}"
    
    def _log(self, message, level):
        """Internal logging method."""
        if level.value >= self._log_level.value:
            formatted_message = self._format_message(message, level)
            print(formatted_message)
    
    def debug(self, message):
        """Log a debug message."""
        self._log(message, LogLevel.DEBUG)
    
    def info(self, message):
        """Log an info message."""
        self._log(message, LogLevel.INFO)
    
    def warning(self, message):
        """Log a warning message."""
        self._log(message, LogLevel.WARNING)
    
    def error(self, message):
        """Log an error message."""
        self._log(message, LogLevel.ERROR)
    
    def critical(self, message):
        """Log a critical message."""
        self._log(message, LogLevel.CRITICAL)
    
    def start_section(self, section_name):
        """Start a new logging section with indentation."""
        self._current_section = section_name
        self._section_times[section_name] = time.time()
        self._log(f"Starting {section_name}...", LogLevel.INFO)
        self._indent_level += 1
    
    def end_section(self, section_name=None):
        """End the current logging section and report time taken."""
        if section_name is None:
            section_name = self._current_section
        
        if section_name in self._section_times:
            self._indent_level = max(0, self._indent_level - 1)
            elapsed = time.time() - self._section_times[section_name]
            self._log(f"Completed {section_name} in {elapsed:.3f}s", LogLevel.INFO)
            del self._section_times[section_name]
            self._current_section = None
    
    def log_operation(self, operation, item_name, success=True, error=None):
        """Log an operation with consistent formatting."""
        status = "✓" if success else "✗"
        message = f"{operation} {item_name} {status}"
        
        if success:
            self.debug(message)
        else:
            self.error(f"{message}: {error}")
            
    def log_registration(self, class_name, success=True, error=None):
        """Log class registration with consistent formatting."""
        self.log_operation("Registered", class_name, success, error)
    
    def log_unregistration(self, class_name, success=True, error=None):
        """Log class unregistration with consistent formatting."""
        self.log_operation("Unregistered", class_name, success, error)

# Convenience functions
def get_logger():
    """Get the logger instance."""
    return Logger.get_instance()

def debug(message):
    """Log a debug message."""
    get_logger().debug(message)

def info(message):
    """Log an info message."""
    get_logger().info(message)

def warning(message):
    """Log a warning message."""
    get_logger().warning(message)

def error(message):
    """Log an error message."""
    get_logger().error(message)

def critical(message):
    """Log a critical message."""
    get_logger().critical(message)

def start_section(section_name):
    """Start a new logging section."""
    get_logger().start_section(section_name)

def end_section(section_name=None):
    """End the current logging section."""
    get_logger().end_section(section_name)

def log_registration(class_name, success=True, error=None):
    """Log class registration."""
    get_logger().log_registration(class_name, success, error)

def log_unregistration(class_name, success=True, error=None):
    """Log class unregistration."""
    get_logger().log_unregistration(class_name, success, error) 