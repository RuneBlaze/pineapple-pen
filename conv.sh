#!/bin/zsh

# Check if ffmpeg and ImageMagick are installed
if ! command -v ffmpeg &> /dev/null; then
  echo "ffmpeg could not be found. Please install ffmpeg to use this script."
  exit 1
fi

if ! command -v magick &> /dev/null; then
  echo "ImageMagick (magick) could not be found. Please install ImageMagick to use this script."
  exit 1
fi

# Check if an argument is provided
if [ $# -eq 0 ]; then
  echo "Usage: $0 <file.webp>"
  exit 1
fi

# Get the input .webp file from the argument
image_file="$1"

# Check if the provided file exists and is a .webp file
if [[ ! -f $image_file || ${image_file##*.} != "webp" ]]; then
  echo "The provided file does not exist or is not a .webp file."
  exit 1
fi

# Get the filename without extension
filename="${image_file%.*}"

# Corresponding .wav file
audio_file="${filename}.wav"

# Check if the corresponding .wav file exists
if [[ -e $audio_file ]]; then
  echo "Extracting frames from $image_file..."
  python "scripts/to_frames.py" "$image_file" "${filename}_frame%04d.png"
  
  echo "Combining frames and $audio_file into ${filename}.mp4..."
  ffmpeg -r 30 -i "${filename}_frame%04d.png" -i "$audio_file" -vf "scale=1280:720" -c:v libx264 -pix_fmt yuv420p -c:a aac -b:a 320k -shortest "${filename}.mp4"
  
  # Clean up the extracted frames
  rm "${filename}_frame"*.png
  
  echo "Conversion complete: ${filename}.mp4"
else
  echo "Corresponding .wav file for $image_file not found. Exiting..."
  exit 1
fi
