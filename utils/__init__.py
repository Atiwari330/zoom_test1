import os
import subprocess

def combine_tracks(filepath="combined_audio.m4a", dir="tmp", safe=True):
    if safe and os.path.exists(filepath):
        raise FileExistsError(f"The file '{filepath}' already exists.")
        
    input_files = [os.path.join(dir, file) for file in os.listdir(dir) if file.endswith('.m4a')]
    if not input_files:
        raise ValueError("No input files found in the 'tmp' directory.")

    input_args = []
    amerge_inputs = []

    for idx, file in enumerate(input_files):
        input_args.extend(["-i", file])
        amerge_inputs.append(f"[{idx}:a]")

    amerge_filter = f"{''.join(amerge_inputs)}amerge=inputs={len(input_files)}[out]"

    ffmpeg_command = [
        "ffmpeg",
        "-y" if not safe else "-n",  # overwrite (-y) or not (-n)
        *input_args,
        "-filter_complex", amerge_filter,
        "-map", "[out]",
        "-ac", str(len(input_files)),
        filepath
    ]

    try:
        subprocess.run(ffmpeg_command, check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        error_message = e.stderr.decode() if e.stderr else f"No detailed error message available. Raw error: {str(e)}"
        raise RuntimeError(f"FFmpeg error: {error_message}") from e
