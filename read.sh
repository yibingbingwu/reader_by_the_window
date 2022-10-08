#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

source $HOME/.ssh/speech.env
export PYTHONLIB=$PYTHONLIB:$PWD/src

python ${SCRIPT_DIR}/src/main.py -c ${SCRIPT_DIR}/my.yml
