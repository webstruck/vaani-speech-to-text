"""
Text processing utilities for the speech-to-text application.
"""

import re
import logging

logger = logging.getLogger(__name__)

class TextProcessor:
    """Processes transcribed text for better readability."""
    
    def __init__(self):
        """Initialize the text processor."""
        # Common English filler words and sounds
        self.filler_words = [
            r'\bum+\b', r'\buh+\b', r'\ber+\b', r'\bah+\b', r'\bhm+\b',
            r'\byou know\b', r'\blike\b(?=\s+\w+)', r'\bactually\b', r'\bbasically\b'
        ]
        
        # Common English recognition errors and fixes
        self.common_fixes = {
            r'\bi see\b': 'I see',
            r'\bi am\b': 'I am',
            r'\bi\'m\b': 'I\'m',
            r'\bi\'ll\b': 'I\'ll',
            r'\bi\'ve\b': 'I\'ve',
            r'\bi\'d\b': 'I\'d',
            r'\bwe\'re\b': 'we\'re',
            r'\byou\'re\b': 'you\'re',
            r'\bthey\'re\b': 'they\'re',
            r'\bwont\b': 'won\'t',
            r'\bcant\b': 'can\'t',
            r'\bdont\b': 'don\'t',
        }
    
    def post_process_text(self, text):
        """
        Clean up transcription text for better readability in English.
        
        Args:
            text: Raw transcribed text
            
        Returns:
            Processed text with improved formatting and readability
        """
        # Convert to lowercase for processing
        text = text.strip()
        
        if not text:
            return text
        
        # Remove common English filler words and sounds
        for word in self.filler_words:
            text = re.sub(word, '', text)
        
        # Fix common English recognition errors 
        for pattern, replacement in self.common_fixes.items():
            text = re.sub(pattern, replacement, text)
        
        # Remove repeated words (common in speech recognition)
        text = re.sub(r'\b(\w+)( \1\b)+', r'\1', text)
        
        # Fix spacing issues
        text = re.sub(r'\s+', ' ', text)
        
        # Always capitalize first letter (hardcoded behavior)
        if len(text) > 0:
            text = text[0].upper() + text[1:]
        
        # Always add period if missing end punctuation (hardcoded behavior)
        if text and not text[-1] in ['.', '!', '?']:
            text = text + '.'
                
        return text