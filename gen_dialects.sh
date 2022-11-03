#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR

dialets="河南 普通 四川 山东 台湾 广东 陕西"
for d in $dialets
do
  date +"[%D %T] Generating output file for $d"
  perl -pi -e "s/invocation:\s+chinese-.*/invocation: chinese-$d/;s/theme-word:\s*([^\s|\.]+).*/theme-word: \$1.$d/" my.yml
#  cat my.yml
  ./read.sh
  date +"[%D %T] Done"
done