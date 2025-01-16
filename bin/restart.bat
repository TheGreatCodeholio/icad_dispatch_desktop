set arg1=%1
set arg2=%2

taskkill /PID %arg1% /F
START %arg2%\icad_td.exe