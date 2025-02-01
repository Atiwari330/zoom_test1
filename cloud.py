import os
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

# Instantiate Zoom client to interact with the Zoom API
client = ZoomClient(
    account_id=ZOOM_ACCOUNT_ID,
    client_id=ZOOM_CLIENT_ID,
    client_secret=ZOOM_CLIENT_SECRET
)

# Instantiate AssemblyAI transcriber with multichannel speech-to-text enabled
config = aai.TranscriptionConfig(multichannel=True)
transcriber = aai.Transcriber(config=config)

def main():
    # -------------------------------------------------
    # 1) FETCH ALL RECORDINGS FROM TODAY (UTC)
    # -------------------------------------------------
    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    params = {'from': today_str}

    # Example API call: GET /users/me/recordings?from=YYYY-MM-DD
    meets = client.get_recordings(params=params)

    # If no meetings are returned for today's date, exit gracefully
    if not meets.get("meetings"):
        print(f"No recorded meetings found for {today_str}.")
        return

    # Grab the first returned meeting's UUID
    meeting_uuid = meets["meetings"][0]["uuid"]
    print(f"Downloading participant audio files for meeting UUID: {meeting_uuid}")

    # -------------------------------------------------
    # 2) DOWNLOAD PARTICIPANT FILES
    # -------------------------------------------------
    client.download_participant_audio_files(meeting_uuid, path='tmp')

    # -------------------------------------------------
    # 3) COMBINE TRACKS INTO A SINGLE M4A
    # -------------------------------------------------
    path = "combined_audio.m4a"
    utils.combine_tracks(path=path, dir="tmp")

    # -------------------------------------------------
    # 4) TRANSCRIBE WITH ASSEMBLYAI
    # -------------------------------------------------
    transcript = transcriber.transcribe(path)

    # Print number of channels and each utterance
    print(f"Number of channels: {transcript.json_response['audio_channels']}")
    for utt in transcript.utterances:
        print(utt)

if __name__ == "__main__":
    main()
