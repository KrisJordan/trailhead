# Run all development servers via a process manager like `honcho`
# 
# Start all subprocesses with `honcho start`
# Stop with Ctrl+C
#
# For more information, see: https://honcho.readthedocs.io/en/latest/index.html#what-are-procfiles

proxy: caddy run
server: cd demo && trailhead --reload
client: cd client && npm run dev
compst: python3 -m http.server 2100 --directory turtle