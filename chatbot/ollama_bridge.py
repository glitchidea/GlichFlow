#!/usr/bin/env python3
"""
Ollama API Bridge Script

Bu script, Docker container'ı ve host makine arasında Ollama API'ye erişim için 
bir köprü görevi görür.

Kullanım:
    python ollama_bridge.py generate "Merhaba, nasılsın?"
    python ollama_bridge.py chat "Merhaba, nasılsın?"
"""

import sys
import os
import subprocess
import json
import tempfile
import requests

# Ollama API endpoints to try
API_ENDPOINTS = [
    "http://host.docker.internal:11434",
    "http://localhost:11434",
    "http://172.17.0.1:11434",
    "http://host.gateway.docker.internal:11434",
]

def try_api_request(prompt, mode="generate", model="llama3:8b"):
    """Try API request to different endpoints"""
    for endpoint in API_ENDPOINTS:
        url = f"{endpoint}/api/{mode}"
        try:
            if mode == "generate":
                payload = {
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                }
            else:  # chat mode
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                }
            
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                return data.get('response') if mode == "generate" else data.get('message', {}).get('content')
        except Exception as e:
            continue
    
    return None

def cli_fallback(prompt, model="llama3:8b"):
    """Fallback to CLI if API doesn't work"""
    try:
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
            f.write(prompt)
            prompt_file = f.name
        
        cmd = ["ollama", "run", model, "-f", prompt_file]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        # Clean up temp file
        try:
            os.unlink(prompt_file)
        except:
            pass
            
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        pass
        
    return None

def main():
    if len(sys.argv) < 3:
        print("Usage: python ollama_bridge.py [generate|chat] \"Your prompt here\"")
        sys.exit(1)
    
    mode = sys.argv[1]
    prompt = sys.argv[2]
    model = sys.argv[3] if len(sys.argv) > 3 else "llama3:8b"
    
    if mode not in ["generate", "chat"]:
        print("Mode must be either 'generate' or 'chat'")
        sys.exit(1)
    
    # Try API request first
    response = try_api_request(prompt, mode, model)
    
    # Fallback to CLI if API failed
    if not response:
        response = cli_fallback(prompt, model)
    
    # If all methods failed, return error
    if not response:
        print(json.dumps({"error": "Failed to communicate with Ollama"}))
        sys.exit(1)
    
    # Return the response
    print(json.dumps({"response": response}))

if __name__ == "__main__":
    main() 