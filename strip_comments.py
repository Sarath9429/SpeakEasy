import sys
import re
import os

def strip_python_comments(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove full line comments
    content = re.sub(r'^\s*#.*?\n', '', content, flags=re.MULTILINE)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Stripped comments from {filepath}")

def strip_js_comments(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove full line // comments
    content = re.sub(r'^\s*//.*?\n', '', content, flags=re.MULTILINE)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Stripped comments from {filepath}")

if __name__ == '__main__':
    strip_python_comments(r'd:\SynthSpeak\server.py')
    strip_python_comments(r'd:\SynthSpeak\visual_pipeline.py')
    strip_js_comments(r'd:\SynthSpeak\app.js')

