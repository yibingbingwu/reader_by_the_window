import argparse
import logging
import os.path
from pathlib import Path
from typing import Optional

import yaml

from engine_aws import AwsPolly
from engine_azure import azure_cogno_call, AzureBob

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

    src_key = conf['text_source']['invocation']
    assert conf[src_key], f"Missing value for key '{src_key}'"
    for c in conf['text_source']['choices']:
        if c != src_key:
            conf.pop(c, None)
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

    this_lang = APP_CONFIG['lang']['invocation']
    return APP_CONFIG['engines'][this_lang]['choices'][0]


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
        import trafilatura

        url = APP_CONFIG['url']
        downloaded = trafilatura.fetch_url(url)
        out_txt = trafilatura.extract(downloaded)
        logger.info('Successfully downloaded content from URL')

        with open(extracted_txt_fn, 'w') as fout:
            fout.write(out_txt)
        logger.info(f'Saved link content to text file at {extracted_txt_fn}')

    elif APP_CONFIG.get('pdf', None):
        import pdfplumber

        with pdfplumber.open(_parse_dir(APP_CONFIG['pdf'])) as pdf:
            for p in pdf.pages:
                out_txt += p.extract_text()
        logger.info('Successfully extracted contents from the PDF file')

        with open(extracted_txt_fn, 'w') as fout:
            fout.write(out_txt)
        logger.info(f'Saved PDF content to text file at {extracted_txt_fn}')

    else:
        pass

    use_eng = what_engine_to_use()
    if use_eng == 'aws':
        logger.info(f'Using AWS engine')
        eng = AwsPolly(APP_CONFIG)
        eng.convert(out_txt)

    elif use_eng == 'azure':
        logger.info(f'Using Azure engine')
        eng = AzureBob(APP_CONFIG)
        assert extracted_txt_fn and os.path.exists(
            extracted_txt_fn), "To use Azure Long Audio service, you need to save the text extraction first"
        eng.convert_long(extracted_txt_fn)

    else:
        assert False, f"Unknown Engine specification {use_eng}"
