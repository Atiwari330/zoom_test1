# File: cloud.py

import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
import assemblyai as aai

import utils
from utils.zoom import ZoomClient

# Load environment variables from .env
load_dotenv()

# Pull in credentials from your .env
ZOOM_ACCOUNT_ID = os.environ.get('ZOOM_ACCOUNT_ID')
ZOOM_CLIENT_ID = os.environ.get('ZOOM_CLIENT_ID')
ZOOM_CLIENT_SECRET = os.environ.get('ZOOM_CLIENT_SECRET')
aai.settings.api_key = os.environ.get('ASSEMBLYAI_API_KEY')

# Ensure all required environment variables are available
if not all([ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET, aai.settings.api_key]):
    raise RuntimeError(
        "Missing one or more required environment variables: "
        "ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET, ASSEMBLYAI_API_KEY"
    )

# Instantiate Zoom client
client = ZoomClient(
    account_id=ZOOM_ACCOUNT_ID,
    client_id=ZOOM_CLIENT_ID,
    client_secret=ZOOM_CLIENT_SECRET
)

# Create a multi-channel transcription config
config = aai.TranscriptionConfig(
    multichannel=True,
    # Optionally, you can specify other parameters:
    # word_boost=["therapist", "patient"],  # if you have specific domain terms
    # speakers_expected=2  # if you know there are exactly 2 channels
)
transcriber = aai.Transcriber(config=config)


def save_transcript_to_json(transcript_data, filename="transcript.json"):
    """
    Saves final transcript data to a local JSON file for demonstration purposes.
    In production, replace or extend this to save to your EHR or a secure database.
    """
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(transcript_data, f, ensure_ascii=False, indent=2)


def main():
    print("[INFO] Starting script to download Zoom recordings and transcribe with AssemblyAI.")

    # -------------------------------------------------
    # 1) FETCH TODAY'S RECORDINGS
    # -------------------------------------------------
    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    params = {'from': today_str}

    meets = client.get_recordings(params=params)
    if not meets.get("meetings"):
        print(f"[INFO] No recorded meetings found for {today_str}. Exiting.")
        return

    # Grab the first returned meeting's UUID
    meeting_uuid = meets["meetings"][0]["uuid"]
    print(f"[INFO] Downloading participant audio files for meeting UUID: {meeting_uuid}")

    # -------------------------------------------------
    # 2) DOWNLOAD PARTICIPANT FILES AND TRACK CHANNELS
    # -------------------------------------------------
    # We'll store a list: [(filepath, participantName), ...]
    # which matches the order in which we feed files to ffmpeg
    channel_map = []  # channel index -> participant name
    path = 'tmp'
    os.makedirs(path, exist_ok=True)

    # The Zoom client method itself writes each participant file to 'tmp' directory
    # We must replicate that logic here if we want to track the order
    response = client.get_meeting_recordings(meeting_uuid)
    participant_audio_files = response['participant_audio_files']

    for data in participant_audio_files:
        # Download each participant's file manually to keep the order
        participant_name = data['file_name'].split('-')[-1].strip()
        download_url = data['download_url']

        # 1) Build local filename
        channel_count = channel_map.count(participant_name) + 1
        file_label = f"{participant_name}_{channel_count}" if channel_count > 1 else participant_name
        local_filename = f"{file_label}.m4a"
        local_path = os.path.join(path, local_filename)

        print(f"[DEBUG] Downloading file for participant '{participant_name}' to {local_path}")
        r = client.auth_header  # just to re-auth if needed (unused variable warning is normal)

        # Actually do the download
        audio_response = requests.get(download_url, headers=client.auth_header)
        with open(local_path, 'wb') as f:
            f.write(audio_response.content)
        
        # Keep track of the participant name in the same order
        channel_map.append((local_filename, participant_name))

    print(f"[INFO] Downloaded {len(channel_map)} participant audio files.")

    # -------------------------------------------------
    # 3) COMBINE TRACKS INTO A SINGLE M4A
    # -------------------------------------------------
    combined_path = "combined_audio.m4a"
    if os.path.exists(combined_path):
        os.remove(combined_path)  # Remove if it exists to avoid FileExistsError
    utils.combine_tracks(filepath=combined_path, dir=path, safe=False)
    print(f"[INFO] Successfully merged audio into {combined_path}")

    # -------------------------------------------------
    # 4) TRANSCRIBE WITH ASSEMBLYAI
    # -------------------------------------------------
    print("[INFO] Sending combined audio to AssemblyAI for transcription...")
    transcript = transcriber.transcribe(combined_path)

    num_channels = transcript.json_response['audio_channels']
    print(f"[INFO] Number of channels in final transcript: {num_channels}")

    # -------------------------------------------------
    # 5) LABEL CHANNELS & PRINT RESULTS
    # -------------------------------------------------
    final_utterances = []
    for utt in transcript.utterances:
        # Convert channel to int in case it is a string
        ch_idx = int(utt.channel)

        # If there's a mismatch in the number of channels vs participants, handle gracefully
        if ch_idx < len(channel_map):
            participant_name = channel_map[ch_idx][1]
        else:
            participant_name = f"UnknownChannel{ch_idx}"

        labeled_utterance = {
            "participant": participant_name,
            "start_ms": utt.start,
            "end_ms": utt.end,
            "text": utt.text,
            "confidence": utt.confidence
        }
        final_utterances.append(labeled_utterance)

        # Print to console
        print(f"({participant_name}) {utt.text}")

    # -------------------------------------------------
    # 6) SAVE TRANSCRIPT DATA
    # -------------------------------------------------
    transcript_data = {
        "meeting_uuid": meeting_uuid,
        "transcribed_at": datetime.utcnow().isoformat(),
        "num_channels": num_channels,
        "utterances": final_utterances
    }
    save_transcript_to_json(transcript_data, filename="transcript.json")
    print("[INFO] Transcript successfully labeled and saved to transcript.json.")


if __name__ == "__main__":
    main()
