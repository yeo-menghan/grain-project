# allocator/ai/openai_client.py
"""OpenAI API client"""
import json
import re
from typing import Dict, Any, Optional, Tuple
from openai import OpenAI
from allocator.config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_TEMPERATURE
from allocator.ai.token_tracker import TokenUsage


class OpenAIClient:
    """Wrapper for OpenAI API calls"""
    
    def __init__(self, api_key: str = OPENAI_API_KEY, 
                 model: str = OPENAI_MODEL,
                 temperature: float = OPENAI_TEMPERATURE):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
    
    def generate_allocation(self, prompt: str) -> Tuple[Optional[Dict[str, Any]], Optional[TokenUsage]]:
        """
        Generate allocation using OpenAI API
        Returns (allocation_dict, token_usage)
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert logistics optimizer. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )
            
            # Extract token usage
            usage = response.usage
            token_usage = TokenUsage(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                model=self.model
            )
            
            content = response.choices[0].message.content
            
            # Try to parse the JSON
            try:
                allocation = json.loads(content)
                return allocation, token_usage
            except json.JSONDecodeError as e:
                print(f"⚠️  JSON parsing error: {e}")
                print(f"   Attempting to fix malformed JSON...")
                
                # Try to fix common JSON issues
                fixed_content = self._attempt_json_fix(content)
                if fixed_content:
                    try:
                        allocation = json.loads(fixed_content)
                        return allocation, token_usage
                    except json.JSONDecodeError:
                        pass
                
                # If fixing fails, return a minimal valid structure
                print(f"❌ Could not parse or fix JSON response")
                print(f"   Returning empty allocation...")
                return {
                    "allocations": {},
                    "reasoning": {},
                    "warnings": ["Failed to parse AI response - returning empty allocation"]
                }, token_usage
        
        except Exception as e:
            print(f"❌ Error calling OpenAI API: {e}")
            # Return empty allocation instead of crashing
            return {
                "allocations": {},
                "reasoning": {},
                "warnings": [f"API error: {str(e)}"]
            }, None
    
    def _attempt_json_fix(self, content: str) -> Optional[str]:
        """Attempt to fix common JSON formatting issues"""
        try:
            # Remove any text before the first {
            match = re.search(r'\{', content)
            if match:
                content = content[match.start():]
            
            # Remove any text after the last }
            match = re.search(r'\}[^}]*$', content)
            if match:
                content = content[:match.end()]
            
            # Try to fix unterminated strings by finding the last valid }
            # and truncating there
            brace_count = 0
            last_valid_pos = -1
            
            for i, char in enumerate(content):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        last_valid_pos = i + 1
            
            if last_valid_pos > 0:
                content = content[:last_valid_pos]
            
            return content
            
        except Exception:
            return None