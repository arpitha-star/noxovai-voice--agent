import os
import shutil
import zipfile

source_dir = r"C:\Users\ARPITHA\.gemini\antigravity\scratch\nexovai-voice-agent"
targets = [
    r"C:\Users\ARPITHA\OneDrive\Desktop\nexovai-voice-agent.zip",
    r"C:\Users\ARPITHA\Downloads\nexovai-voice-agent.zip",
    r"C:\Users\ARPITHA\.gemini\antigravity\scratch\nexovai-voice-agent.zip",
    r"C:\Users\ARPITHA\.gemini\antigravity\brain\3ababd09-0a7e-4a67-b14e-12bc115a9538\nexovai-voice-agent.zip"
]

temp_zip = r"C:\Users\ARPITHA\.gemini\antigravity\scratch\nexovai-voice-agent-temp.zip"

exclude_dirs = {".git", "__pycache__", ".venv", "venv", ".idea", ".vscode"}
exclude_files = {".DS_Store", "nexovai-voice-agent.zip", "nexovai-voice-agent-temp.zip"}

with zipfile.ZipFile(temp_zip, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(source_dir):
        # Exclude directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if file in exclude_files or file.endswith(".pyc"):
                continue
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, source_dir)
            # Add top-level folder name inside zip
            archive_name = os.path.join("nexovai-voice-agent", rel_path)
            zf.write(full_path, archive_name)

print("Temp zip created successfully.")

for t in targets:
    try:
        os.makedirs(os.path.dirname(t), exist_ok=True)
        shutil.copy2(temp_zip, t)
        print(f"Copied to: {t}")
    except Exception as e:
        print(f"Failed to copy to {t}: {e}")

if os.path.exists(temp_zip):
    os.remove(temp_zip)

print("All zip archives updated successfully!")
