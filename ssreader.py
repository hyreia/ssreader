import argparse
import requests
import re
import sounddevice as sd
import os

print("Importing Kokoro and other dependencies (this could take several seconds)...")

from kokoro import KPipeline
import warnings
warnings.filterwarnings(
    "ignore",
    message="dropout option adds dropout after all but last recurrent layer"
)
warnings.filterwarnings(
    "ignore",
    message="`torch.nn.utils.weight_norm` is deprecated"
)
import numpy as np
import soundfile as sf

import re

def clean_filename(filename: str, replace_with: str = "") -> str:
    # Matches \ / : * ? " < > | and control characters (0-31)
    forbidden_chars = r'[\\/:#*?"<>\n|\x00-\x1f]'
    cleaned = re.sub(forbidden_chars, replace_with, filename)

    # Shorten to 100 characters max
    return cleaned[:100]

def get_available_voices_list() -> list[str]:
    url = "https://huggingface.co/api/models/hexgrad/Kokoro-82M"
    data = requests.get(url).json()
    voices = []

    for item in data["siblings"]:
        name: str = item["rfilename"]

        if name.startswith("voices/"):
            voice_name = name.removeprefix("voices/").removesuffix(".pt")
            voices.append(voice_name)
    return voices



def load_pronunciation_guide(filename: str) -> dict:
    guide = {}
    
    print("Loading guide...")
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith(("#",";")):
                key,value = line.split("=",1)
                key = key.strip()
                value = value.strip()
                #value = f"[{key}](/{value}/)"
                print(f"{key} is {value}")
                guide[key] = value
            #else, ignore this line
            
            
    return guide


def apply_pronunciation_guide(text: str, pronunciation_guide: dict = None) -> str:
    if pronunciation_guide is None: return text
    for key,value in pronunciation_guide.items():
        if key in text:
            pattern = rf"\b{re.escape(key)}\b"
            replacement = lambda m: f"[{m.group(0)}](/{value}/)"
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text


def merge_section_files(root_folder: str, only_section: str = None, file_format: str = "wav"):
    # check root_folder exists
    if not os.path.exists(root_folder):
        raise ValueError(f"Root folder {root_folder} does not exist")
    for subfolder in os.listdir(root_folder):
        if only_section and subfolder != only_section:
            continue
        if os.path.isdir(f"{root_folder}/{subfolder}"):
            # get the name of all of audio files in subfolder (ends in file_format)
            audio_files = [f for f in os.listdir(f"{root_folder}/{subfolder}") if f.endswith(f"{file_format}")]
            # sort alphanumerically
            audio_files.sort()
            # merge audio files into one file
            audio_arrays = []

            for audio_file in audio_files:
                audio, sample_rate = sf.read(
                    f"{root_folder}/{subfolder}/{audio_file}"
                )
                audio_arrays.append(audio)

            full_section_audio = np.concatenate(audio_arrays)

            sf.write(
                f"{root_folder}/{subfolder}.{file_format}",
                full_section_audio,
                24000
            )

def parse_markup(line: str, render_details: dict):
    
    while True:
        line = line.lstrip()

        # Voice
        match = re.match(r"<voice\s+([^>]+)>", line)
        if match:
            render_details["voice"] = match.group(1).strip()
            line = line[match.end():]
            continue

        # Speed
        match = re.match(r"<speed\s+([0-9]*\.?[0-9]+)>", line)
        if match:
            render_details["speed"] = float(match.group(1))
            line = line[match.end():]
            continue

        # Gain
        match = re.match(r"<gain\s+([0-9]*\.?[0-9]+)>", line)
        if match:
            render_details["gain"] = float(match.group(1))
            line = line[match.end():]
            continue
        
        # Pause
        match = re.match(r"<pause\s+([0-9]*\.?[0-9]+)>", line)
        if match:
            render_details["pause"] = float(match.group(1))
            line = line[match.end():]
            continue

        # Break
        match = re.match(r"<break>", line)
        if match:
            # we want to insert a break before the next line
            render_details["is_inserting_linebreak"] = True
            line = line[match.end():]
            continue
        # Reset
        match = re.match(r"<reset>", line)
        if match:
            render_details["is_resetting_render"] = True
            line = line[match.end():]
            continue

        # No more markup at the beginning
        break

    return line, render_details

def is_starting_with_a_quote(line: str) -> tuple[bool, str, str | None]:
    # Find the first quotation mark
    first_quote = line.find('"')

    # No quotation mark at all
    if first_quote == -1:
        return False, line, None

    # Quotation mark is at the beginning
    if first_quote == 0:
        # Find the closing quotation mark
        second_quote = line.find('"', 1)

        # No closing quotation mark
        if second_quote == -1:
            # Treat the whole thing as normal text
            return False, line, None

        # Everything through the closing quote
        quoted_text = line[:second_quote + 1]

        # Everything after the closing quote
        leftover = line[second_quote + 1:].lstrip()

        return True, quoted_text, leftover

    # Quotation mark is somewhere in the middle
    else:
        # Everything before the quotation mark
        non_quoted_text = line[:first_quote].rstrip()

        # The quote and everything after it
        leftover = line[first_quote:]

        return False, non_quoted_text, leftover

def render_story(pipeline: KPipeline, open_file, voice: str, speed=1.10, file_format: str= "wav", pronunciation_guide=None, is_merging: bool = True,
                 only_section: str = None) -> bool:
    
    DEFAULT_PAUSE = 0.2
    BREAK_LENGTH = 4.0
    DEFAULT_GAIN = 1
    DIALOGUE_GAIN = 1.75
    
    line_number: int = 0
    root_folder_name = None
    subfolder_name = None
    
    section_audio = []
    
    line_render_details = {
        "voice": voice,
        "speed": speed,
        "is_resetting_render": False,
        "is_inserting_linebreak": False,
        "pause": DEFAULT_PAUSE,
        "gain": DEFAULT_GAIN
    }
    
    has_found_markup_tag: bool = False
    tag: str = None
    
    # leftover text from previous line, like if we have to be louder for dialogue and finish something afterwards
    
    leftover_line = ""
    line = None
    
    while True:
        if leftover_line:
            line = leftover_line
        else:
            line = open_file.readline()
            
        if not line:
            break
        
        line, line_render_details = parse_markup(line, line_render_details)
        
        #detect quotation marks    
        is_a_quote, text, leftover = is_starting_with_a_quote(line)
        
        if is_a_quote:
            line_render_details["gain"] = DIALOGUE_GAIN
            line_render_details["pause"] = 0.1
        else:
            line_render_details["pause"] = DEFAULT_PAUSE

        # slight bug/note: if you reset and then change things on the same line, everything else gets ignored but the reset
        # just put them on the next line
        if line_render_details["is_resetting_render"]:
            line_render_details = {
            "voice": voice,
            "speed": speed,
            "is_resetting_render": False,
            "is_inserting_linebreak": False,
            "pause": DEFAULT_PAUSE,
            "gain": DEFAULT_GAIN
        }
        
        # does the line start with a markdown header besides a title?
        if line.startswith("# "):
            # it's a title, set root folder name
            root_folder_name = line.lstrip("# ").strip()
        else:
            # get filename, first 100 characters of the line and remove forbidden characters
            filename = clean_filename(line, "")
            if line.startswith("#") and not line.startswith("# "):
                
                # write out subfolder audio if not empty
                if section_audio:
                    # merge section audio into one file
                    if is_merging:
                        full_section_audio = np.concatenate(section_audio)
                        sf.write(f"{root_folder_name}/{subfolder_name}.{file_format}", full_section_audio, 24000)
                        full_section_audio = []
                        section_audio = []
                
                # not a title, it's a header, start a new subfolder
                # extract subfolder name by stripping all # and whitespace from the beginning
                subfolder_name = line.lstrip("# ").strip()
                # create the subfolder if it doesn't exist
                os.makedirs(f"{root_folder_name}/{subfolder_name}", exist_ok=True)
                # notice we're still creating the audio for the header, we want it to read the header name
            
            # check line isn't empty
            if not line.strip():
                continue
            line_number += 1
            line_number_formatted = f"{line_number:04d}"
            
            # line?
            if only_section and subfolder_name != only_section:
                continue
            
            line = line.lstrip("# ").strip()
            proper_line = apply_pronunciation_guide(line, pronunciation_guide=pronunciation_guide)
            generator = pipeline(proper_line, voice=line_render_details["voice"], speed=line_render_details["speed"])
            line_audio = []            
            
            if line_render_details["is_inserting_linebreak"]:
                line_audio.append(np.zeros(int(24000 * BREAK_LENGTH)))
                line_render_details["is_inserting_linebreak"] = False
            elif line_render_details["pause"]:
                line_audio.append(np.zeros(int(24000 * line_render_details["pause"])))
                
            # adjust gain according to line_render_details
            gain = 10 ** (line_render_details["gain"] / 20)
                            
            for i, (gs, ps, audio) in enumerate(generator):
                audio = audio * gain
                line_audio.append(audio)

            full_line_audio = np.concatenate(line_audio)
            

            
            
            full_line_audio *= line_render_details["gain"]
            
            if is_a_quote:
                # set it back
                line_render_details["gain"] = DEFAULT_GAIN
            
            section_audio.append(full_line_audio)
            
            if root_folder_name and subfolder_name:
                print(f"{line_number_formatted}: {proper_line} as {line_number_formatted}_{filename}.{file_format}")
                sf.write(f"{root_folder_name}/{subfolder_name}/{line_number_formatted}_{filename}.{file_format}", full_line_audio, 24000)
            
            elif root_folder_name and not subfolder_name:
                sf.write(f"{root_folder_name}/{line_number_formatted}_{filename}.{file_format}", full_line_audio, 24000)
            
            else:
                sf.write(f"{line_number_formatted}_{filename}.{file_format}", full_line_audio, 24000)
                
            full_line_audio = []
            section_audio = []
    #final section audio
    if is_merging:        
        if section_audio:
            full_section_audio = np.concatenate(section_audio)
            if subfolder_name:
                sf.write(f"{root_folder_name}/{subfolder_name}.{file_format}", full_section_audio, 24000)
            else:
                sf.write(f"{root_folder_name}/{root_folder_name}.{file_format}", full_section_audio, 24000)

    section_audio = None
    full_section_audio = None

    return True
    
def test_voice(text: str ="When the sunlight strikes raindrops in the air, they act as a prism and form a rainbow. \
                The rainbow is a division of white light into many beautiful colors. ", 
                voice: str = "af_heart,af_nicole,", speed: float = 1.15, pronunciation_guide=None,
                filename: str = "output", file_format: str = "mp3",
                story_name: str = None,
                section_name: str = None
                ):
    text = text.replace("...","…")
    text = apply_pronunciation_guide(text, pronunciation_guide=pronunciation_guide)
    print("Starting Kokoro pipeline test...")
    # pick language: 'a' = American English, 'b' = British English
    pipeline = KPipeline(
        lang_code='a',
        repo_id='hexgrad/Kokoro-82M'
    )
    
    print("Generating audio for test, standby...")
    generator = pipeline(text, voice=voice, speed=speed)
    audio_pieces = []
    for i, (gs, ps, audio) in enumerate(generator):
        audio_pieces.append(audio)
        sd.play(audio, samplerate=24000)
        sd.wait()
    
    print("Combining audio pieces...")
    full_audio = np.concatenate(audio_pieces)
    print(f"File created: {filename}.{file_format}")
    
    if story_name:
        if section_name:
            sf.write(f"{story_name}/{section_name}/{filename}.{file_format}", full_audio, 24000)
        else:
            sf.write(f"{story_name}/{filename}.{file_format}", full_audio, 24000)
    else:
        sf.write(f"{filename}.{file_format}", full_audio, 24000)

def main():

    
    # CLI 
    parser = argparse.ArgumentParser(description="Converts an AO3 URL into an audiobook with Kokoro TTS. Caches downloads and downloads only new chapters on rerun.")
    parser.add_argument("filename", nargs="?", help="md format")
    

    parser.add_argument("-c", "--section", type=str, help="only section to read/merge", default=None)
    
    parser.add_argument("-n", "--nomerge", help="only render lines, don't merge into section files", action="store_true")
    parser.add_argument("-m", "--mergeonly", help="no rendering, just merge pre-existing files", action="store_true")
    
    parser.add_argument("-f", "--format", type=str, help="File format for output, supports everything soundfile does", default="mp3")
    
    parser.add_argument("-o", "--output", help="filename output", default=None)
    parser.add_argument("-p", "--pronunciation_guide", help="path to pronunciation guide file", default=None)
    
    parser.add_argument("-s", "--speed", type=float,
                        help="Set the speed of the narration, 1.2 by default", default=1.2)
    parser.add_argument("-t", "--test_text", type=str, help="Test a sample text, -v -s and -p and -o can also be used to test those. Plays and saves to file", default=None)
    
    parser.add_argument("-st", "--story", type=str, help="Name of story/folder", default=None)
    
    #identical to test_text, but clearer when combined with --story and --section
    parser.add_argument("-r", "--read", type=str, help="Test a sample text, -v -s and -p and -o can also be used to test those. Plays and saves to file", default=None)
    
    parser.add_argument("-v", "--voice", help="Kokoro voice to use for rendering", default="af_nicole,af_bella")
    parser.add_argument("-vl", "--voice_list", help="list voices available from huggingface.co", action="store_true")

    args = parser.parse_args()
    
    if args.mergeonly and args.nomerge:
        print("Error: Both --mergeonly and --nomerge cannot be specified simultaneously: what are you trying to do?")
        return
    
    pronunciation_guide = load_pronunciation_guide(args.pronunciation_guide) if args.pronunciation_guide is not None else None
    
    # voice list
    if args.voice_list:
        voices = get_available_voices_list()
        print("Voices available from huggingface.co:")
        for v in voices:
            print("\tvoice: ", v)      
        print("Voices can also be blended by separating them by a comma like 'af_heart,af_nicole'")
        return
    
    # test mode
    if args.test_text is not None or args.read is not None:
        if args.test_text is None:
            args.test_text = args.read
        if args.output is None:
            args.output = "test"
        args.output = clean_filename(f"{args.output}")
        test_voice(args.test_text, 
                   args.voice, 
                   args.speed, 
                   pronunciation_guide=pronunciation_guide, 
                   file_format=args.format, 
                   filename=args.output)
        return

    if args.mergeonly:
        merge_section_files(args.story, args.section, args.format)
        return

    if args.filename is None:
        print("Error: No input file specified. (.md preferred)")
        return
    
    with open(args.filename, "r", encoding="utf-8") as open_file:
            

        # Regular behavior
        print(f"Creating kokoro pipeline for {args.filename} rendering...")
        pipeline = KPipeline(
            lang_code='a',
            repo_id='hexgrad/Kokoro-82M'
        )
    
        render_story(pipeline, open_file,
            voice=args.voice, 
            speed=args.speed, 
            file_format=args.format, 
            pronunciation_guide=pronunciation_guide, is_merging = not args.nomerge, only_section=args.section)
        
    print("Done.")

if __name__ == "__main__":
    main()