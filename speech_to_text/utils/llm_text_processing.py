"""
LLM-based text processing utilities for the speech-to-text application.
Uses Ollama to improve transcription quality with language models.
"""

import logging
import ollama
from typing import Optional
from speech_to_text.utils.text_processing import TextProcessor

logger = logging.getLogger(__name__)

class LLMTextProcessor:
    """
    Enhanced text processor that uses LLMs (via Ollama) to correct transcription errors,
    fix spelling, and improve grammar in transcribed text.
    """
    
    def __init__(self, model_name: str = "mistral:latest", endpoint: str = "http://localhost:11434", 
                 fallback_processor: Optional[TextProcessor] = None):
        """
        Initialize the LLM text processor.
        
        Args:
            model_name: Name of the Ollama model to use (default: mistral:latest)
            endpoint: Ollama API endpoint (default: http://localhost:11434)
            fallback_processor: Fallback TextProcessor to use if LLM processing fails
        """
        self.model_name = model_name
        self.endpoint = endpoint
        self.ollama_client = ollama.Client(host=endpoint)
        self.fallback_processor = fallback_processor or TextProcessor()
        self.system_prompt = (
            "You are a helpful transcription correction assistant. " \
            "Your task is to correct any errors in transcribed text from speech recognition. " \
            "Fix grammar, spelling, punctuation, and sentence structure. " \
            "Maintain the original meaning and intent of the text. " \
            "Return ONLY the corrected text without explanations or additional commentary."
        )
        
        # Test connection on initialization
        self._test_ollama_connection()
    
    def _test_ollama_connection(self) -> bool:
        """
        Test the connection to the Ollama service.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Simple ping to check if Ollama is running
            self.ollama_client.list()
            logger.info(f"Successfully connected to Ollama at {self.endpoint}")
            return True
        except Exception as e:
            logger.warning(f"Failed to connect to Ollama: {str(e)}")
            logger.warning("LLMTextProcessor will fall back to basic text processing")
            return False
    
    def is_model_available(self, model_name: Optional[str] = None) -> bool:
        """
        Check if the specified model is available in Ollama.
        
        Args:
            model_name: Name of the model to check (defaults to self.model_name)
            
        Returns:
            True if model is available, False otherwise
        """
        try:
            model_to_check = model_name or self.model_name
            models = self.ollama_client.list()
            # print(models)  # Debugging line to check available models
            available_models = [model["model"] for model in models["models"]]
            is_available = model_to_check in available_models
            
            if not is_available:
                logger.warning(f"Model {model_to_check} is not available in Ollama. Available models: {available_models}")
            
            return is_available
        except Exception as e:
            logger.warning(f"Error checking model availability: {str(e)}")
            return False
    
    def update_model(self, model_name: str) -> None:
        """
        Update the model used by the processor.
        
        Args:
            model_name: New model name to use
        """
        self.model_name = model_name
        logger.info(f"LLMTextProcessor now using model: {model_name}")
    
    def process_with_timeout(self, text: str, timeout_seconds: float = 3.0) -> str:
        """
        Process text with timeout to prevent long waiting times.
        
        Args:
            text: Text to process
            timeout_seconds: Maximum time to wait for LLM response
            
        Returns:
            Processed text, or original text if timeout occurs
        """
        import threading
        result = {"processed": None}
        processing_done = threading.Event()
        
        def process_text_thread():
            try:
                result["processed"] = self._call_ollama(text)
                processing_done.set()
            except Exception as e:
                logger.error(f"Error in LLM processing thread: {str(e)}")
                processing_done.set()
        
        thread = threading.Thread(target=process_text_thread)
        thread.daemon = True
        thread.start()
        
        if not processing_done.wait(timeout=timeout_seconds):
            logger.warning(f"LLM processing timed out after {timeout_seconds}s, falling back to basic processing")
            return self.fallback_processor.post_process_text(text)
        
        if result["processed"] is None:
            logger.warning("LLM processing failed, falling back to basic processing")
            return self.fallback_processor.post_process_text(text)
        
        return result["processed"]
    
    def _call_ollama(self, text: str) -> str:
        """
        Call Ollama API to process the text.
        
        Args:
            text: Text to process
            
        Returns:
            Processed text from Ollama
        """
        try:
            user_prompt = f"Please correct this transcript: {text}"
            
            response = self.ollama_client.chat(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                stream=False,
                options={
                    "temperature": 0.1,  # Low temperature for more deterministic outputs
                    "num_predict": 500,  # Limit response length
                }
            )
            
            processed_text = response["message"]["content"].strip()
            
            # Remove quotes if the LLM included them in the response
            processed_text = processed_text.strip('"\'')
            
            logger.debug(f"Original: '{text}' -> Processed: '{processed_text}'")
            return processed_text
            
        except Exception as e:
            logger.error(f"Error calling Ollama: {str(e)}")
            return self.fallback_processor.post_process_text(text)
    
    def post_process_text(self, text: str) -> str:
        """
        Clean up transcription text using the LLM.
        
        Args:
            text: Raw transcribed text
            
        Returns:
            Processed text with improved formatting and readability
        """
        # Skip processing for very short texts
        if not text or len(text.strip()) < 2:
            return text.strip()
        
        # Apply basic processing first (minimal)
        basic_processed = text.strip()
        
        try:
            # Process with LLM
            return self.process_with_timeout(basic_processed)
        except Exception as e:
            logger.error(f"LLM processing failed: {str(e)}, falling back to basic processor")
            return self.fallback_processor.post_process_text(text)