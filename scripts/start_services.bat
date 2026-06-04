@echo off
echo Starting Redis...
start "Redis" "C:\Program Files\Redis\redis-server.exe" "D:\Redis\redis.conf"

echo Starting PostgreSQL...
"C:\Program Files\PostgreSQL\15\bin\pg_ctl.exe" -D "D:\PostgreSQL\15\data" -l "D:\PostgreSQL\15\data\pg.log" start

echo Services started.
echo Redis: localhost:6379
echo PostgreSQL: localhost:5432
pause
