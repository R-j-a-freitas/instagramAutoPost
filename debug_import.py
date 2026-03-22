import sys
from pathlib import Path

# Adicionar o diretório raiz ao path
root = Path(__file__).resolve().parent
sys.path.append(str(root))

try:
    from instagram_poster import reel_generator
    print(f"Module loaded: {reel_generator.__file__}")
    print(f"Has mix_video_with_audio: {hasattr(reel_generator, 'mix_video_with_audio')}")
    print(f"Has repeat_video: {hasattr(reel_generator, 'repeat_video')}")
    
    from instagram_poster.reel_generator import mix_video_with_audio
    print("Direct import successful!")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
