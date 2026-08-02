#!/bin/zsh
stty cols ${COLS:-104} rows ${ROWS:-24} 2>/dev/null
clear
sleep 0.4

prompt="用 jobfindsme，根据 ~/Documents/resume.pdf 找上海和杭州的 AI 应用工程师岗位，20K以上，社招，正式。"
print -n -- "你 "
for ((i = 1; i <= ${#prompt}; i++)); do
  print -rn -- "${prompt[$i]}"
  sleep 0.035
done
print
sleep 0.9

print "正在连接 jobfindsme · 本地解析简历并双平台并行检索…"
sleep 1.1
print

python3 -B "$(dirname "$0")/drive_mcp.py" 2>/dev/null

sleep 1.6
