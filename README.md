# Text to Speech Program

## Requirements:
1. Python 3.9+
2. Install requirements.txt
3. Add a `~/.ssh/speech.env` file that contains:
   - AWS (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
   - Azure (SPEECH_KEY)

## First time ever
- Create a `my.yml` at root, by copying `my.yml.sample` file
- Edit the my.yml file, 
  - Search for key `invocation:`
  - These are the equivelant of CLI options
  - For example, `text_source` has several under `choices`
  - The key `invocation` needs to pick one of those values as this run param
  - Same goes for all other not commented out `inocation` instances
  - For options under `engines`:
    - If you left them blank, they will use the defaults

## How to run
- Run `read.sh`

<div style="page-break-after: always"></div>

## Sample steps

### Convert web PDF to audio
1. Open a Terminal, run:
   - `conda activate py310`, use this shell for the rest
   - `cd workarea/reader_by_the_window/`
2. Download PDF to `/Users/ywu/Downloads/my_input.pdf`
3. Open `my.yml` to set the following values:
   - text_source/invocation -> **pdf**
   - text_source/inspect_output -> **True**
4. Save `my.yml` file, then run:
    - `./read.sh`
    - It should say something like:
    - ```Because you spec-ed 'inspect_output: True', stopping the program so you can inspect the output file:/private/tmp/lisas_output.extracted.txt```
5. Open the `/tmp/my_output.extracted.txt` file, manually edit the content, e.g.
    - Remove all the white spaces
    - Add white spaces to English words
    - Add line breaks or merge broken lines. Every space, every new line character will cause the reading to pause
6. Once done, edit the `my.yml` file again
    - text_source/invocation -> **txt**
    - text_source/inspect_output -> **False**
7. Run `./read.sh` again to generate a test
    - The output should be here: `/Users/ywu/Desktop/my_output.mp3`
8. Change settings in `my.yml` when necessary, e.g.
   - Adjust speed, for example: azure/speed
   - Once changed, you need to run the `./read.sh` script again to generate a new file
   - Repeat until you are satisfied with the output
9. [Optional] Run `./gen_dialects.sh`
   - You should find the output files under `~/Desktop`
