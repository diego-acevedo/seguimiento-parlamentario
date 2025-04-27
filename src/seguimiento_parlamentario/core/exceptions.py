class YouTubeVideoNotFoundError(Exception):
    """Exception raised when a YouTube video is not found in the API response."""
    
    def __init__(self, session_id: str, message: str = "Could not find YouTube video for session"):
        self.session_id = session_id
        self.message = f"{message}: {session_id}"
        super().__init__(self.message)

class VideoUrlNotFoundError(Exception):
    """Exception raised when a video url can't be retrieve from the website."""
    
    def __init__(self, session_id: str, message: str = "Could not find video url for session"):
        self.session_id = session_id
        self.message = f"{message}: {session_id}"
        super().__init__(self.message)