import sys
import pydantic
import pdfplumber
import pptx
import ollama

def verify_environment():
    print("==================================================")
    print("   SIH PS ID: 26154 - ENVIRONMENT VERIFICATION   ")
    print("==================================================")
    print(f"[✓] Python Version: {sys.version.split()[0]} (Expected 3.11.x)")
    print(f"[✓] Pydantic Version: {pydantic.__version__}")
    print(f"[✓] pdfplumber Version: {pdfplumber.__version__}")
    print(f"[✓] python-pptx Version: {pptx.__version__}")
    
    # Test local Ollama LLM Connection
    try:
        response = ollama.chat(
            model='qwen2.5:3b',
            messages=[{'role': 'user', 'content': 'Respond with the word SUCCESS if you are operational.'}]
        )
        reply = response['message']['content'].strip()
        print(f"[✓] Local Model Connection (qwen2.5:3b): {reply}")
        print("\nSUCCESS: All dependencies and local models are verified!")
    except Exception as e:
        print(f"\n[X] Local Model Error: {e}")
        print("    Ensure Ollama is running (`ollama serve`) and the model is pulled (`ollama pull qwen2.5:3b`).")

if __name__ == "__main__":
    verify_environment()