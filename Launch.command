#!/bin/zsh
cd "${0:A:h}"
python3 launch.py
if [[ $? -ne 0 ]]; then
  echo "Launch stopped. Review the message above."
  read -k 1 "?Press any key to close."
fi

