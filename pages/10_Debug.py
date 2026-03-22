import streamlit as st
import sys
import os
from pathlib import Path

st.title("Debug Environment")

st.write("### Python Path")
st.code("\n".join(sys.path))

st.write("### Working Directory")
st.code(os.getcwd())

st.write("### Instagram Poster Module")
try:
    import instagram_poster
    st.write(f"Location: {instagram_poster.__file__}")
    
    st.write("### Reel Generator Module")
    from instagram_poster import reel_generator
    st.write(f"Location: {reel_generator.__file__}")
    st.write(f"Attributes: {dir(reel_generator)}")
    
    if hasattr(reel_generator, 'mix_video_with_audio'):
        st.success("mix_video_with_audio found!")
    else:
        st.error("mix_video_with_audio NOT found in loaded module.")
        
    st.write("### File Content (last 100 lines)")
    with open(reel_generator.__file__, "r") as f:
        lines = f.readlines()
        st.code("".join(lines[-100:]))
        
except Exception as e:
    st.error(f"Error: {e}")
    import traceback
    st.code(traceback.format_exc())
