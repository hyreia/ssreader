# Kokoro Story Reader

A lightweight text-to-speech pipeline for turning Markdown-formatted stories into organized narration files using [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M).

The primary goal is to generate **raw, editable narration** for short stories, audiobooks, narrated videos, and similar projects.

Rather than producing only one large audio file, the program can render each line separately and organize the resulting files by story section. Those files can then be merged into complete section-length audio files when desired.

## Python Version

This project is developed and tested using Python 3.12.

Some Kokoro and PyTorch dependencies may not work correctly on older or newer Python versions. If you experience installation problems, Python 3.12 is the recommended version.

## Features

- Kokoro TTS narration
- Markdown story input
- Automatic organization by story title and sections
- Individual WAV/MP3/etc. files for each line
- Combined section audio files
- Render-only mode
- Merge-only mode
- Render a specific section
- Test arbitrary text without a story file
- Configurable narration speed
- Configurable Kokoro voice
- Voice blending
- Pronunciation guide support
- Inline rendering markup
- Automatic dialogue detection and gain adjustment
- Automatic pauses between lines
- Longer breaks between sections when requested
- Easy re-rendering of individual lines with `--read`

## How It Works

A Markdown story is treated as the source document.

A level-one Markdown header (`#`) is used as the story title and becomes the root output folder.

Additional Markdown headers (`##`, `###`, etc.) are treated as sections and become subfolders.

For example:

```text
# The Collection

## Act I — The Things People Forget

I started working at Disposition Services in March.

The job was simple.

## Act II — The Files

The next morning, I read another file.

## Act III — The Collection

The next morning, I started looking for the boxes.

## Act IV — The Exit

“Stop screaming.”
````

produces a structure similar to:

```text
The Collection/
├── Act I — The Things People Forget/
│   ├── 0001_I started working at Disposition Services in March.mp3
│   ├── 0002_The job was simple.mp3
│   └── ...
├── Act I — The Things People Forget.mp3
│
├── Act II — The Files/
│   ├── 0003_The next morning I read another file.mp3
│   └── ...
├── Act II — The Files.mp3
│
├── Act III — The Collection/
│   └── ...
└── Act IV — The Exit/
    └── ...
```

The individual files provide a convenient editing source, while the merged files provide a ready-to-listen-to version of each section.

Filenames are based on the line number followed by the beginning of the source text. Unsafe filename characters are removed and filenames are limited to 100 characters.

## Installation

Install Python 3.12 and the required Kokoro, PyTorch, NumPy, SoundFile, SoundDevice, Requests, and related dependencies.

The program uses the Kokoro model:

```text
hexgrad/Kokoro-82M
```

The Kokoro model and its dependencies may require additional platform-specific installation steps.

Once the dependencies are installed, run the program with Python:

```bash
python ssreader.py
```

## Basic Usage

Render a Markdown story:

```bash
python ssreader.py story.md
```

The default voice is:

```text
af_nicole,af_bella
```

for personal tastes and the default narration speed is `1.2` (because nicole is slow.)

The program renders individual lines and, unless `--nomerge` is specified, creates a merged audio file for each section.

## Selecting a Voice

Use `--voice` or `-v`:

```bash
python ssreader.py story.md --voice af_nicole
```

Kokoro voices can also be blended by separating them with commas:

```bash
python ssreader.py story.md --voice af_nicole,af_bella
```

To retrieve the voices currently available from the Kokoro model:

```bash
python ssreader.py --voice_list
```

The program will query the Kokoro model repository and print the available voice names.

## Changing Narration Speed

Use `--speed` or `-s`:

```bash
python ssreader.py story.md --speed 1.1
```

The default speed is `1.2`.

## Output Format

Use `--format` or `-f`:

```bash
python ssreader.py story.md --format wav
```

The default output format is:

```text
mp3
```

The program passes the requested format to SoundFile, so the supported formats depend on the SoundFile/libsndfile installation.

## Rendering a Specific Section

Use `--section` or `-c`:

```bash
python ssreader.py story.md --section "Act III — The Collection"
```

Only the specified section will be rendered.

This is useful when revising a story and needing to regenerate only one act rather than the entire story.

## Render Without Merging

Use `--nomerge` or `-n`:

```bash
python ssreader.py story.md --nomerge
```

This renders the individual line files but does not create the combined section files.

This is useful when generating source audio for later editing.

## Merge Existing Files

Use `--mergeonly` or `-m` to skip TTS generation and merge audio files that already exist:

```bash
python ssreader.py --mergeonly --story "The Collection"
```

To merge only one section:

```bash
python ssreader.py --mergeonly --story "The Collection" --section "Act III — The Collection"
```

Existing audio files in the section folder are sorted alphanumerically before being concatenated.

This makes it possible to replace or edit individual line files and then rebuild the complete section without rerunning Kokoro.

`--mergeonly` and `--nomerge` cannot be used together.

## Rendering Test Text

Use `--read` or `-r` to render arbitrary text without creating a story:

```bash
python ssreader.py --read "The lights went out."

```

Specify an output filename with `--output`:

```bash
python ssreader.py \
    --read "The lights went out." \
    --output test
```

The same voice, speed, pronunciation guide, and output format options can be used with test text.

The older `--test_text` / `-t` option provides the same functionality.

For example:

```bash
python ssreader.py \
    --read "Kevin stood beside the loading door." \
    --voice af_nicole,af_bella \
    --speed 1.1 \
    --output kevin_test
```

This is particularly useful for testing pronunciation, voices, or alternate readings without rerendering an entire story.

## Pronunciation Guides

A pronunciation guide can be supplied with `--pronunciation_guide` or `-p`:

```bash
python ssreader.py story.md --pronunciation_guide pronunciation.txt
```

The guide uses a simple `word=pronunciation` format:

```text
Kokoro=koh-KOR-oh
Karen=CARE-en
resume=rez-oo-may
```

Lines beginning with `#` or `;` are ignored.

Whitespace around the word and pronunciation is removed.

Pronunciation replacements are applied as whole-word, case-insensitive matches.

For example:

```text
Karen walked into the room.
```

with:

```text
Karen=CARE-en
```

will cause the pronunciation guide to be applied to `Karen` before the text is sent to Kokoro.

## Inline Markup

The reader supports lightweight inline markup at the beginning of a line.

Multiple markup tags may appear consecutively:

```text
<voice af_nicole><speed 1.1><gain 2>The room was silent.
```

Markup is processed until the beginning of the line no longer contains a recognized tag.

### Voice

Change the Kokoro voice:

```text
<voice af_nicole>Hello.
```

Voice blending is supported:

```text
<voice af_nicole,af_bella>Hello.
```

### Speed

Change the narration speed:

```text
<speed 1.1>This sentence is spoken slightly faster.
```

### Gain

Change the audio gain in decibels:

```text
<gain 2>This sentence is louder.
```

The gain value is converted to an audio multiplier after Kokoro generates the speech.

### Pause

Set the pause before a line:

```text
<pause 0.5>This line gets a longer pause.
```

The default pause is 0.2 seconds.

### Break

Insert a longer break before the line:

```text
<break>The next scene begins here.
```

The default break length is 4 seconds.

### Reset

Reset rendering settings to the original voice, speed, gain, and pause:

```text
<reset>Return to the default narration settings.
```

## Automatic Dialogue Detection

The reader also detects quotation marks and automatically adjusts dialogue.

For example:

```text
She shook her head. "No."
```

is treated as two audio segments:

```text
She shook her head.
"No."
```

The narration and dialogue can therefore use different gain and pause settings.

Quoted text receives the dialogue gain automatically.

This also works when dialogue begins a line:

```text
"This is what I mean," she said.
```

The quoted portion is rendered as dialogue and the remaining narration is rendered separately.

This allows dialogue to be emphasized without requiring markup around every spoken line.

## Combining Markup and Dialogue

Markup can be used together with automatic quotation detection.

For example:

```text
<voice af_nicole>She walked into the room. "Hello?"
```

The markup changes the active rendering settings before the text is processed, after which the quotation detection handles the dialogue portion.

## Suggested Workflow

The intended workflow is to treat individual line files somewhat like compiled object files.

### 1. Write the story

Write the story as Markdown:

```text
# My Story

## Act I

The story begins here.

## Act II

Things get worse.
```

### 2. Render the story

```bash
python ssreader.py story.md
```

### 3. Listen to individual lines

The output folder contains separate audio files for each line.

This makes it easy to identify lines that need another take.

### 4. Re-render individual lines

Use `--read` to generate a replacement:

```bash
python ssreader.py \
    --read "The corrected version of this sentence." \
    --output replacement
```

A pronunciation guide, voice, speed, and other supported options can be supplied while testing.

### 5. Replace the problematic file

Replace the original line audio with the new take.

### 6. Merge the section

```bash
python ssreader.py \
    --mergeonly \
    --story "My Story" \
    --section "Act I"
```

The existing individual files are combined in numerical order.

This avoids rerendering the entire story whenever a single line needs to be changed.

## Why Individual Files?

Generating narration one line at a time provides several advantages for later production:

* Individual lines can be replaced without rerendering the entire story.
* Audio can be edited on a line-by-line basis.
* Individual lines can be adjusted for timing or volume.
* External sound effects and ambience can be synchronized more easily.
* Sections can be rebuilt after individual files are changed.
* The merged narration can serve as a convenient listening copy.

The project is therefore intended to be a **raw narration generator**, rather than a complete audiobook or video production system.

## Markdown Support

Markdown support is intentionally lightweight.

The current implementation uses headers to identify the story title and sections. It does not attempt to fully render Markdown.

A line beginning with:

```text
# 
```

is treated as the story title.

Other Markdown headers beginning with `#` are treated as section headers.

The header text is also spoken as part of the generated narration.

Other Markdown syntax is currently treated as ordinary text.

## Command-Line Reference

| Option                        | Description                                                   |
| ----------------------------- | ------------------------------------------------------------- |
| `filename`                    | Markdown input file                                           |
| `-v`, `--voice`               | Kokoro voice to use                                           |
| `-vl`, `--voice_list`         | List available Kokoro voices                                  |
| `-s`, `--speed`               | Narration speed                                               |
| `-f`, `--format`              | Output audio format                                           |
| `-o`, `--output`              | Output filename for test/read mode                            |
| `-p`, `--pronunciation_guide` | Pronunciation guide file                                      |
| `-c`, `--section`             | Render or merge only a specified section                      |
| `-n`, `--nomerge`             | Render individual files without merging                       |
| `-m`, `--mergeonly`           | Merge existing audio files without rendering                  |
| `-r`, `--read`                | Render supplied text instead of a story                       |
| `-t`, `--test_text`           | Alternative test-text option                                  |
| `-st`, `--story`              | Story/output folder name, primarily used with merge-only mode |

## Example

A complete example:

```bash
python ssreader.py \
    "The Collection.md" \
    --voice af_nicole,af_bella \
    --speed 1.1 \
    --pronunciation_guide pronunciation.txt
```

To regenerate only Act III:

```bash
python ssreader.py \
    "The Collection.md" \
    --section "Act III — The Collection"
```

To render only the individual line files:

```bash
python ssreader.py \
    "The Collection.md" \
    --nomerge
```

To rebuild an existing section after replacing individual files:

```bash
python ssreader.py \
    --mergeonly \
    --story "The Collection" \
    --section "Act III — The Collection"
```

## Project Status

This project is currently focused on **raw narration generation**.

It intentionally does not attempt to handle the later stages of audiobook or narrated-video production such as:

* ambience
* sound effects
* music
* stingers
* final audio mixing
* subtitles
* video editing
* visual effects

Those can be handled separately using the generated individual audio files and merged narration.

The goal is to keep the text-to-speech stage simple, reproducible, and easy to revise.

## License

No license has currently been specified for this project.

```

One thing I deliberately **didn't** put in there is a made-up installation command or dependency version list. Your source imports Kokoro, PyTorch-related Kokoro dependencies, NumPy, SoundFile, SoundDevice, Requests, etc., but the source itself doesn't specify pinned versions or an installation mechanism. So I left that section accurate rather than inventing a `requirements.txt` that may not match your environment. :contentReference[oaicite:1]{index=1}

Also, I kept the README focused on what the program **is now** rather than what we might eventually make it. That's probably the right GitHub README for this point in the project's life.
```
