import sys
from pathlib import Path
import os

# Adicionar o root do projecto ao sys.path para importar instagram_poster
root = Path(__file__).resolve().parent
sys.path.append(str(root))

from instagram_poster.reel_generator import mix_video_with_audio

def test_mix():
    # Criar um vídeo de teste de 2 segundos (preto) se não existir
    test_vid = root / "test_video.mp4"
    if not test_vid.exists():
        print("Criando vídeo de teste...")
        try:
            from moviepy import ColorClip
            clip = ColorClip(size=(640, 480), color=(0, 0, 0), duration=2)
            clip.write_videofile(str(test_vid), fps=30, logger=None)
        except Exception as e:
            print(f"Erro ao criar vídeo: {e}")
            return

    with open(test_vid, "rb") as f:
        video_bytes = f.read()

    # Usar uma música da biblioteca
    music_folder = root / "assets" / "music" / "MUSIC"
    tracks = list(music_folder.glob("*.mp3"))
    if not tracks:
        print("Nenhuma música encontrada!")
        return
    
    audio_path = str(tracks[0])
    print(f"Testando mix com: {audio_path}")
    
    try:
        mixed_bytes = mix_video_with_audio(video_bytes, audio_path)
        print(f"Sucesso! Tamanho original: {len(video_bytes)}, Tamanho final: {len(mixed_bytes)}")
        
        with open(root / "mixed_test_output.mp4", "wb") as f:
            f.write(mixed_bytes)
        print("Resultado gravado em mixed_test_output.mp4")
    except Exception as e:
        print(f"Erro no mix: {e}")

if __name__ == "__main__":
    test_mix()
