import sys
from pathlib import Path

# Add root to path
root = Path(__file__).resolve().parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

print(f"Python path: {sys.path}")

try:
    from instagram_poster import config
    print(f"Module 'instagram_poster.config' loaded from: {config.__file__}")
    
    attrs = dir(config)
    print(f"Has get_text_provider: {'get_text_provider' in attrs}")
    print(f"Has get_nvidia_api_key: {'get_nvidia_api_key' in attrs}")
    
    # List first 200 attributes
    print(f"Some attributes: {attrs[:50]}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
