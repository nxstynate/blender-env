from . import logger

class FontManager:
    _instance = None
    _is_initialized = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = FontManager()
        return cls._instance

    def __init__(self):
        if not FontManager._is_initialized:
            self.initialize()

    def initialize(self):
        """Initialize the font manager using Blender's native monospace font."""
        logger.info("Using Blender's native monospace font (ID 1)")
        FontManager._is_initialized = True

    def reinitialize(self):
        """Reinitialize the font manager."""
        FontManager._is_initialized = False
        self.initialize()

    @property
    def custom_font_id(self):
        """Get the monospace font ID (always 1)."""
        return 1

    def cleanup(self):
        """Clean up font resources."""
        FontManager._is_initialized = False

# Global accessor function
def get_font_id():
    """Get the font ID (always 1 for monospace font)."""
    return 1