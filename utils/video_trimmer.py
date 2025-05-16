import re
import shlex
import subprocess
import os
import paramiko


def _clean_filename(filename):
    """
    Cleans filename and removes all special characters

    :param filename: name of the file
    :return cleaned_file: SSH name of the file with removed special characters
    """

    # Replace all non-alphanumeric characters in the base with underscores
    cleaned_file = re.sub(r"[^\w]", "_", filename)

    # Replace multiple consecutive underscores with a single underscore in the base
    cleaned_file = re.sub(r"__+", "_", cleaned_file)

    return cleaned_file


def trim_video(start, end, input_path, output_path):
    """
    Trim mp4 video and save locally or via SSH.

    :param start: from which second to trim
    :param end: to which second to trim
    :param input_path: path to the input video
    :param output_path: path to save the trimmed video
    """

    command = [
        "ffmpeg",
        "-y",
        "-ss",
        start,
        "-to",
        end,
        "-i",
        input_path,
        "-c",
        "copy",
        output_path,
    ]
    command_str = " ".join(command)
    print(f"Running: {command_str}")

    subprocess.run(command, check=True)


def trim_videos_from_folder(
        source_video_output_path, video_clips_output_path, video_clips
):
    """
    Trim all mp4 videos from specified folder locally or via SSH.

    :param source_video_output_path: Where to find the videos
    :param video_clips_output_path: Where to save the trimmed videos
    :param video_clips: JSON with configuration of how to trim the videos
    :return names_list: metadata needed to map input and output videos
    """

    os.makedirs(video_clips_output_path, exist_ok=True)

    names_list = []
    # Iterate through the JSON
    for video_file, ranges_string in video_clips.items():
        input_path = os.path.join(source_video_output_path, video_file)
        input_path = shlex.quote(input_path)
        if not os.path.isfile(input_path):
            print(f"Video not found: {input_path}")
            continue

        ranges = ranges_string.split(";")
        for idx, time_range in enumerate(ranges):
            start, end = time_range.strip().split("-")
            video_file_base = os.path.splitext(video_file)[0]
            video_file_extension = os.path.splitext(video_file)[1]
            video_file_cleaned = _clean_filename(video_file_base)
            output_name = f"{video_file_cleaned}_trim_{start[-2:]}_{end[-2:]}{video_file_extension}"
            output_path = f"{video_clips_output_path}{output_name}"
            trim_video(
                start=start,
                end=end,
                input_path=input_path,
                output_path=output_path,
            )
            names_list.append(
                {
                    "azure_input_filename": video_file,
                    "azure_output_filename": output_name,
                    "extension": video_file_extension,
                    "time_range": time_range,
                    "start_second": int(start[-2:]),
                    "end_second": int(end[-2:]),
                }
            )

    return names_list
