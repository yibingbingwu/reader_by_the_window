import argparse
import logging
import os.path
import sys
from pathlib import Path
from typing import Optional

import chinese_converter
import yaml

from engine_aws import AwsPolly
from engine_azure import AzureBob

logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)

APP_CONFIG: Optional[dict] = None


def _parse_dir(in_val: str) -> str:
    if in_val.startswith('~' + os.path.sep):
        in_val = str(Path.home()) + in_val[1:]
    return os.path.realpath(in_val)


def process_config(cfg_fn: str) -> dict:
    conf = yaml.safe_load(Path(cfg_fn).read_text())
    assert conf['text_source']['invocation'] in conf['text_source']['choices'], "Missing a valid Text Source"
    assert conf['lang']['invocation'] in conf['lang']['choices'], "Missing a valid Language choice"

    this_lang = conf['lang']['invocation']
    lang_prefix = this_lang.split('-')[0]
    assert conf['engines'][lang_prefix], "Missing or mis-defined Language for this run. Or cannot find matching Engine"
    conf.pop('lang', None)
    conf['lang'] = this_lang

    src_key = conf['text_source']['invocation']
    assert conf[src_key], f"Missing value for key '{src_key}'"
    for c in conf['text_source']['choices']:
        if c != src_key:
            conf.pop(c, None)

    if conf['text_source'].get('inspect_output', False):
        conf['inspect_extract_txt'] = True

    conf.pop('text_source', None)

    output_dict = conf['output']
    assert output_dict['directory'], 'Missing output directory'
    Path(output_dict['directory']).mkdir(parents=True, exist_ok=True)

    assert output_dict['invocation']['theme-word'], 'Missing a generic name to describe this invocation'
    conf['invocation-theme-word'] = output_dict['invocation']['theme-word']
    conf['output_extracted_txt_fn'] = _parse_dir(output_dict['extracted_text_dir']) + os.sep + \
                                      output_dict['invocation']['theme-word'] + '.extracted.txt'
    conf['output_audio_fn'] = _parse_dir(output_dict['directory']) + os.sep + \
                              output_dict['invocation']['theme-word'] + '.mp3'
    conf.pop('output', None)

    return conf


def what_engine_to_use():
    if APP_CONFIG.get('engines').get('invocation', None):
        return APP_CONFIG['engines']['invocation']

    this_lang = APP_CONFIG['lang']
    return APP_CONFIG['engines'][this_lang]['choices'][0]


def clean_after_pdf_extract(in_text: str) -> str:
    # Cleaning some known edge cases:
    cleaned_txt = ''
    txt_len = len(in_text)
    for ci in range(txt_len):
        c = in_text[ci]
        if c == '\f':
            continue

        if c == '\n':
            # Skip the first line return only
            if ci < txt_len - 1 and in_text[ci + 1] == '\n':
                cleaned_txt += '\n'
            elif cleaned_txt[-1] == '\n':
                continue
            else:
                cleaned_txt += ' '
            continue

        cleaned_txt += c

    return cleaned_txt


def extract_from_url(url: str, out_fn: str) -> str:
    import trafilatura

    downloaded = trafilatura.fetch_url(url)
    retval = trafilatura.extract(downloaded)
    logger.info('Successfully downloaded content from URL')

    if APP_CONFIG['lang'].startswith('chinese'):
        # The python extraction package defaults to traditional:
        retval = chinese_converter.to_simplified(retval)

    with open(out_fn, 'w') as fout:
        fout.write(retval)
    logger.info(f'Saved link content to text file at {out_fn}')

    return retval


def extract_from_local_pdf(in_file: str, out_fn: str) -> str:
    from pdfminer.high_level import extract_text

    raw_txt = extract_text(pdf_file=in_file)
    # with open(out_fn + '.raw', 'w') as fout:
    #     fout.write(raw_txt)

    retval = clean_after_pdf_extract(raw_txt)
    logger.info('Successfully extracted contents from the PDF file')

    with open(out_fn, 'w') as fout:
        fout.write(retval)
    logger.info(f'Saved PDF content to text file at {out_fn}')

    return retval


if __name__ == '__main__':
    logging.basicConfig(
        format="%(asctime)s  %(levelname)s %(message)s", level=logging.INFO
    )
    cli_parser = argparse.ArgumentParser(
        description="Generate audio file based on input"
    )
    cli_parser.add_argument('-c', '--cfg', dest='cfg_yml', required=True)
    cli_opts = cli_parser.parse_args()

    logger.info('Program Starts')
    APP_CONFIG = process_config(cli_opts.cfg_yml)

    out_txt = ''
    extracted_txt_fn = APP_CONFIG['output_extracted_txt_fn']
    if APP_CONFIG.get('url', None):
        out_txt = extract_from_url(url=APP_CONFIG['url'], out_fn=extracted_txt_fn)

    elif APP_CONFIG.get('pdf', None):
        out_txt = extract_from_local_pdf(in_file=_parse_dir(APP_CONFIG['pdf']), out_fn=extracted_txt_fn)

    elif APP_CONFIG.get('txt', None):
        src_fn = APP_CONFIG['txt']
        APP_CONFIG['output_extracted_txt_fn'] = src_fn
        out_txt = Path(_parse_dir(src_fn)).read_text()
        logger.info(f'Picked up text file from {src_fn}')

    else:
        assert False, "Unknown Text Source type: " + APP_CONFIG.get('txt')

    if APP_CONFIG.get('inspect_extract_txt', False):
        logger.info(f"\nBecause you spec-ed 'inspect_output: True', "
                    f"stopping the program so you can inspect the output file: \n{extracted_txt_fn}\n")
        sys.exit(0)

    use_eng = what_engine_to_use()
    if use_eng == 'aws':
        logger.info(f'Using AWS engine')
        eng = AwsPolly(APP_CONFIG)
        eng.convert(out_txt)

    elif use_eng == 'azure':
        logger.info(f'Using Azure engine')
        eng = AzureBob(APP_CONFIG)
        eng.convert(out_txt)
        # assert extracted_txt_fn and os.path.exists(
        #     extracted_txt_fn), "To use Azure Long Audio service, you need to save the text extraction first"
        # eng.convert_long(extracted_txt_fn)

    else:
        assert False, f"Unknown Engine specification {use_eng}"
