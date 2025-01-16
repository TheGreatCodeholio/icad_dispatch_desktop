#!/bin/bash
kill -9 $1
echo $1
bash ${2}/icad.sh &
