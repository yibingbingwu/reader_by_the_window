# Text to Speech Program

## Requirements:
1. Python 3.9+
2. Install requirements.txt
3. Add a `~/.ssh/speech.env` file that contains:
   - AWS (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
   - Azure (SPEECH_KEY)

## First time ever
- Create a `my.yml` at root, by copying `src/sample_cfg.yml` file
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